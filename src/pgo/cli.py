"""PrivacyGuard Ops CLI — presentation layer.

Thin adapter: all business logic lives in core / application layers.
The CLI only maps user intents to domain calls and formats output.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import structlog
import typer
from rich import print
from rich.table import Table

from pgo.core.audit import append as audit_append
from pgo.core.audit import export_audit, verify_chain
from pgo.core.db import open_db
from pgo.core.errors import (
    AuditChainBroken,
    ManifestInvalid,
    ManifestNotFound,
    PGOError,
    RepoRootNotFound,
    StateTransitionInvalid,
)
from pgo.core.logging import configure_logging
from pgo.core.repository import create_finding, list_findings, transition_finding
from pgo.core.settings import Settings
from pgo.manifest import load_brokers_manifest
from pgo.core.models import FindingStatus
from pgo.core.state import TransitionEvent

logger = structlog.get_logger()

app = typer.Typer(help="PrivacyGuard Ops — local-first opt-out auditing CLI.")


# ── Callback (runs before every command) ────────────────────
@app.callback(invoke_without_command=True)
def _main_callback(  # pyright: ignore[reportUnusedFunction]
    ctx: typer.Context,
    log_level: str = typer.Option("INFO", "--log-level", envvar="PGO_LOG_LEVEL", help="Log level."),
    log_json: bool = typer.Option(True, "--log-json/--log-text", envvar="PGO_LOG_JSON", help="JSON or human logs."),
) -> None:
    """Configure logging + settings, then store in context for sub-commands."""
    configure_logging(level=log_level, json_output=log_json)
    try:
        settings = Settings(log_level=log_level, log_json=log_json)
    except RepoRootNotFound:
        print("[red]ERROR:[/red] could not find repo root (pyproject.toml not found in parents).")
        raise typer.Exit(code=2)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings

    # If no sub-command given, show help.
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())


def _settings(ctx: typer.Context) -> Settings:
    return ctx.obj["settings"]


def _db(ctx: typer.Context) -> sqlite3.Connection:
    """Return an open DB connection, caching it in the context."""
    if "db" not in ctx.obj:
        s = _settings(ctx)
        s.ensure_dirs()
        ctx.obj["db"] = open_db(s.db_path)
    return ctx.obj["db"]


# ── Commands ────────────────────────────────────────────────
@app.command()
def status(ctx: typer.Context) -> None:
    """Show current system status and directory health."""
    s = _settings(ctx)

    print("[bold]PrivacyGuard Ops[/bold]  v0.1.0")
    print(f"  Repo root   : {s.repo_root}")
    print(f"  Manifest    : {s.manifest_path}  {'[green]OK[/green]' if s.manifest_path.exists() else '[red]MISSING[/red]'}")
    print(f"  Database    : {s.db_path}  {'[green]OK[/green]' if s.db_path.exists() else '[yellow]NOT CREATED[/yellow]'}")

    dirs: list[tuple[str, Path | None]] = [
        ("Vault", s.vault_dir), ("Data", s.data_dir),
        ("Reports", s.reports_dir), ("Exports", s.exports_dir),
    ]
    for label, d in dirs:
        if d is None:
            print(f"  {label:<12}: [red]NOT CONFIGURED[/red]")
            continue
        print(f"  {label:<12}: {d}  {'[green]OK[/green]' if d.exists() else '[yellow]MISSING[/yellow]'}")

    # Show finding counts if DB exists.
    if s.db_path.exists():
        conn = _db(ctx)
        findings = list_findings(conn)
        by_status: dict[str, int] = {}
        for f in findings:
            by_status[f.status.value] = by_status.get(f.status.value, 0) + 1
        if findings:
            print(f"\n  Findings    : {len(findings)} total")
            for st, count in sorted(by_status.items()):
                print(f"    {st:<14}: {count}")
        else:
            print("\n  Findings    : 0 (run [bold]pgo add[/bold] to start tracking)")

    logger.info("status_checked", repo_root=str(s.repo_root))


@app.command()
def init(ctx: typer.Context) -> None:
    """Initialise PGO: create directories and database."""
    s = _settings(ctx)
    s.ensure_dirs()
    _db(ctx)  # creates the DB and schema
    print("[green]PGO initialised.[/green]  Directories + database ready.")
    logger.info("pgo_initialised", repo_root=str(s.repo_root), db=str(s.db_path))


@app.command()
def plan(ctx: typer.Context) -> None:
    """Load broker manifest and display the plan (brokers + steps)."""
    s = _settings(ctx)
    try:
        brokers = load_brokers_manifest(s.manifest_path)
    except (ManifestNotFound, ManifestInvalid) as exc:
        print(f"[red]ERROR:[/red] {exc}")
        raise typer.Exit(code=1)

    print(f"[bold]Broker plan[/bold]  ({len(brokers)} brokers)")
    for b in brokers:
        print(f"  • {b.name}  {b.url or ''}")
    logger.info("plan_loaded", broker_count=len(brokers))


@app.command(name="manifest-validate")
def manifest_validate(
    ctx: typer.Context,
    manifest: Path = typer.Option(
        None,
        "--manifest",
        help="Path to brokers manifest YAML (relative to repo root unless absolute).",
    ),
) -> None:
    """Validate the brokers manifest schema."""
    s = _settings(ctx)
    manifest_path = manifest if manifest else s.manifest_path
    if not manifest_path.is_absolute():
        assert s.repo_root is not None  # guaranteed by model_validator
        manifest_path = (s.repo_root / manifest_path).resolve()

    try:
        brokers = load_brokers_manifest(manifest_path)
    except (ManifestNotFound, ManifestInvalid, PGOError) as exc:
        print(f"[red]ERROR:[/red] {exc}")
        raise typer.Exit(code=1)

    print(f"[green]OK[/green] manifest valid: {manifest_path} ({len(brokers)} brokers)")


# ── Finding management ──────────────────────────────────────
@app.command()
def add(
    ctx: typer.Context,
    finding_id: str = typer.Argument(help="Unique identifier for this finding."),
    broker: str = typer.Option(..., "--broker", "-b", help="Name of the data broker."),
    url: str = typer.Option(None, "--url", "-u", help="Broker profile URL."),
) -> None:
    """Add a new finding (broker profile) in DISCOVERED state."""
    conn = _db(ctx)
    try:
        f = create_finding(conn, finding_id=finding_id, broker_name=broker, url=url)
    except sqlite3.IntegrityError:
        print(f"[red]ERROR:[/red] Finding '{finding_id}' already exists.")
        raise typer.Exit(code=1)

    # Audit the creation as a transition from none → discovered.
    event = TransitionEvent(
        finding_id=f.finding_id,
        from_status=FindingStatus.DISCOVERED,
        to_status=FindingStatus.DISCOVERED,
        at_utc=f.created_utc,
    )
    audit_append(conn, event, notes="Finding created")

    print(f"[green]Added:[/green] {f.finding_id} — {f.broker_name}  [{f.status.value}]")


@app.command()
def findings(ctx: typer.Context) -> None:
    """List all tracked findings."""
    conn = _db(ctx)
    rows = list_findings(conn)

    if not rows:
        print("[yellow]No findings yet.[/yellow] Run [bold]pgo add[/bold] to start.")
        return

    table = Table(title="Findings", show_lines=False)
    table.add_column("ID", style="bold")
    table.add_column("Broker")
    table.add_column("Status")
    table.add_column("URL")
    table.add_column("Updated")
    for f in rows:
        color = {
            "discovered": "white",
            "confirmed": "cyan",
            "submitted": "yellow",
            "pending": "yellow",
            "verified": "green",
            "resurfaced": "red",
        }.get(f.status.value, "white")
        table.add_row(f.finding_id, f.broker_name, f"[{color}]{f.status.value}[/{color}]", f.url or "", f.updated_utc)

    print(table)


@app.command(name="transition")
def transition_cmd(
    ctx: typer.Context,
    finding_id: str = typer.Argument(help="Finding ID to transition."),
    to: str = typer.Option(..., "--to", "-t", help="Target status (confirmed, submitted, pending, verified, resurfaced)."),
    notes: str = typer.Option("", "--notes", "-n", help="Audit note for this transition."),
) -> None:
    """Move a finding to a new status (with audit trail)."""
    # Validate target status.
    try:
        to_status = FindingStatus(to.lower())
    except ValueError:
        valid = ", ".join(s.value for s in FindingStatus)
        print(f"[red]ERROR:[/red] Invalid status '{to}'. Valid: {valid}")
        raise typer.Exit(code=1)

    conn = _db(ctx)
    try:
        event = transition_finding(conn, finding_id, to_status)
    except KeyError:
        print(f"[red]ERROR:[/red] Finding '{finding_id}' not found.")
        raise typer.Exit(code=1)
    except StateTransitionInvalid as exc:
        print(f"[red]ERROR:[/red] {exc}")
        raise typer.Exit(code=1)

    # Record in audit chain.
    entry_hash = audit_append(conn, event, notes=notes)

    print(
        f"[green]Transitioned:[/green] {finding_id}  "
        f"{event.from_status.value} → {event.to_status.value}  "
        f"hash={entry_hash[:12]}…"
    )


@app.command(name="verify-chain")
def verify_chain_cmd(ctx: typer.Context) -> None:
    """Verify the integrity of the audit chain (tamper detection)."""
    conn = _db(ctx)
    try:
        count = verify_chain(conn)
    except AuditChainBroken as exc:
        print(f"[red bold]INTEGRITY FAILURE:[/red bold] {exc}")
        raise typer.Exit(code=1)

    print(f"[green]Chain OK[/green] — {count} events verified, no tampering detected.")


@app.command(name="export-audit")
def export_audit_cmd(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path (default: exports/audit.json)."),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Verify chain before exporting."),
) -> None:
    """Export the full audit trail to JSON."""
    s = _settings(ctx)
    conn = _db(ctx)

    # Optionally verify first.
    if verify:
        try:
            verify_chain(conn)
        except AuditChainBroken as exc:
            print(f"[red bold]INTEGRITY FAILURE:[/red bold] {exc}")
            print("[yellow]Export aborted. Use --no-verify to force.[/yellow]")
            raise typer.Exit(code=1)

    events = export_audit(conn)

    if output is None:
        assert s.exports_dir is not None
        s.exports_dir.mkdir(parents=True, exist_ok=True)
        output = s.exports_dir / "audit.json"

    output.write_text(json.dumps(events, indent=2, default=str), encoding="utf-8")
    print(f"[green]Exported[/green] {len(events)} events → {output}")


# ── BYOS workflow commands (stubs — v0.1) ───────────────────
@app.command()
def scan(
    ctx: typer.Context,
    query: str = typer.Argument(help="Search query (e.g. 'site:broker.com John Doe')."),
) -> None:
    """Discover candidates (CSE or manual inputs). [stub]"""
    _ = _settings(ctx)
    print(f"[yellow]scan[/yellow] is not yet implemented. Query: {query}")
    print("This will search for broker profiles matching your query.")
    raise typer.Exit(code=0)


@app.command(name="add-url")
def add_url(
    ctx: typer.Context,
    url: str = typer.Argument(help="Public profile URL to add."),
    broker: str = typer.Option(..., "--broker", "-b", help="Name of the data broker."),
    finding_id: str = typer.Option(None, "--id", help="Custom finding ID (auto-generated if omitted)."),
) -> None:
    """Add a known public profile URL manually. [stub]"""
    _ = _settings(ctx)
    print(f"[yellow]add-url[/yellow] is not yet fully implemented.")
    print(f"  Broker: {broker}")
    print(f"  URL   : {url}")
    print("Use [bold]pgo add[/bold] for the current working implementation.")
    raise typer.Exit(code=0)


@app.command()
def confirm(
    ctx: typer.Context,
    finding_id: str = typer.Argument(help="Finding ID to confirm."),
    notes: str = typer.Option("", "--notes", "-n", help="Confirmation notes."),
) -> None:
    """Confirm an item as 'yours' (BYOS) + capture evidence. [stub]"""
    conn = _db(ctx)
    try:
        event = transition_finding(conn, finding_id, FindingStatus.CONFIRMED)
    except KeyError:
        print(f"[red]ERROR:[/red] Finding '{finding_id}' not found.")
        raise typer.Exit(code=1)
    except StateTransitionInvalid as exc:
        print(f"[red]ERROR:[/red] {exc}")
        raise typer.Exit(code=1)

    entry_hash = audit_append(conn, event, notes=notes)
    print(
        f"[green]Confirmed:[/green] {finding_id}  "
        f"{event.from_status.value} → {event.to_status.value}  "
        f"hash={entry_hash[:12]}…"
    )
    print("[yellow]Evidence capture not yet implemented.[/yellow]")


@app.command()
def optout(
    ctx: typer.Context,
    finding_id: str = typer.Argument(help="Finding ID to submit opt-out for."),
    notes: str = typer.Option("", "--notes", "-n", help="Submission notes."),
) -> None:
    """Guided opt-out submission steps (BYOS) + capture proof. [stub]"""
    conn = _db(ctx)
    try:
        event = transition_finding(conn, finding_id, FindingStatus.SUBMITTED)
    except KeyError:
        print(f"[red]ERROR:[/red] Finding '{finding_id}' not found.")
        raise typer.Exit(code=1)
    except StateTransitionInvalid as exc:
        print(f"[red]ERROR:[/red] {exc}")
        raise typer.Exit(code=1)

    entry_hash = audit_append(conn, event, notes=notes)
    print(
        f"[green]Opt-out submitted:[/green] {finding_id}  "
        f"{event.from_status.value} → {event.to_status.value}  "
        f"hash={entry_hash[:12]}…"
    )
    print("[yellow]Submission proof capture not yet implemented.[/yellow]")


@app.command(name="verify")
def verify_cmd(
    ctx: typer.Context,
    finding_id: str = typer.Option(None, "--finding", "-f", help="Specific finding to verify."),
    due: bool = typer.Option(False, "--due", help="Show only findings due for re-check."),
) -> None:
    """Scheduled re-checks (Tier A primary signal). [stub]"""
    _ = _settings(ctx)
    if due:
        print("[yellow]--due filtering is not yet implemented.[/yellow]")
    if finding_id:
        print(f"[yellow]verify[/yellow] for finding '{finding_id}' is not yet implemented.")
    else:
        print("[yellow]verify[/yellow] (batch re-check) is not yet implemented.")
    print("This will re-visit broker pages to detect resurfacing.")
    raise typer.Exit(code=0)


@app.command()
def wipe(
    ctx: typer.Context,
    confirm_wipe: bool = typer.Option(False, "--yes", help="Skip confirmation prompt."),
) -> None:
    """Wipe local case data + vault (user initiated). [stub]"""
    s = _settings(ctx)
    if not confirm_wipe:
        print("[red bold]WARNING:[/red bold] This will delete ALL local data (DB + vault).")
        print("Run with --yes to confirm.")
        raise typer.Exit(code=1)

    # TODO: implement actual wipe of vault_dir, data_dir, reports_dir, exports_dir
    print("[yellow]wipe[/yellow] is not yet fully implemented.")
    print(f"  Would delete: {s.data_dir}, {s.vault_dir}")
    raise typer.Exit(code=0)


# ── Entrypoint ──────────────────────────────────────────────
def main() -> None:  # noqa: D103
    app()
