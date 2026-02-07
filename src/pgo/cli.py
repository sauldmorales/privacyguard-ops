"""PrivacyGuard Ops CLI — presentation layer.

Thin adapter: all business logic lives in core / application layers.
The CLI only maps user intents to domain calls and formats output.
"""

from __future__ import annotations

from pathlib import Path

import structlog
import typer
from rich import print

from pgo.core.errors import ManifestInvalid, ManifestNotFound, PGOError, RepoRootNotFound
from pgo.core.logging import configure_logging
from pgo.core.settings import Settings
from pgo.manifest import load_brokers_manifest

logger = structlog.get_logger()

app = typer.Typer(help="PrivacyGuard Ops — local-first opt-out auditing CLI.")


# ── Callback (runs before every command) ────────────────────
@app.callback(invoke_without_command=True)
def _main_callback(
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


# ── Commands ────────────────────────────────────────────────
@app.command()
def status(ctx: typer.Context) -> None:
    """Show current system status and directory health."""
    s = _settings(ctx)

    print("[bold]PrivacyGuard Ops[/bold]  v0.1.0")
    print(f"  Repo root   : {s.repo_root}")
    print(f"  Manifest    : {s.manifest_path}  {'[green]OK[/green]' if s.manifest_path.exists() else '[red]MISSING[/red]'}")

    dirs: list[tuple[str, Path | None]] = [
        ("Vault", s.vault_dir), ("Data", s.data_dir),
        ("Reports", s.reports_dir), ("Exports", s.exports_dir),
    ]
    for label, d in dirs:
        if d is None:
            print(f"  {label:<12}: [red]NOT CONFIGURED[/red]")
            continue
        print(f"  {label:<12}: {d}  {'[green]OK[/green]' if d.exists() else '[yellow]MISSING[/yellow]'}")

    logger.info("status_checked", repo_root=str(s.repo_root))


@app.command()
def init(ctx: typer.Context) -> None:
    """Create local-state directories (vault, data, reports, exports)."""
    s = _settings(ctx)
    s.ensure_dirs()
    print("[green]Local directories initialised.[/green]")
    logger.info("dirs_initialised", repo_root=str(s.repo_root))


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


# ── Entrypoint ──────────────────────────────────────────────
def main() -> None:  # noqa: D103
    app()
