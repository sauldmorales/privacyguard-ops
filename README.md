# PrivacyGuard Ops (PGO)

## AI-Orchestrated Development (Design → Audit → Implementation)

This project was built using a structured, multi-LLM workflow to enforce separation of concerns across the software lifecycle. Each model was isolated and assigned a specific responsibility to reduce design drift, improve audit coverage, and drive defensive, enterprise-grade implementation.

### Gemini — Macro Architecture + Hardening Strategy (Strict Audit Framework)

Gemini provided the high-level system design direction and introduced the hardening/audit strategy used as a backbone for the security posture.

**Primary contributions:**

* Defined the macro architecture constraints and expected enterprise-grade posture.
* Proposed a strict hardening audit concept (what to harden, where to expect failure, and how to reason about systemic risk).
* Highlighted structural failure vectors early (before implementation changes).

### ChatGPT — Deep Modular Security Audit (Module-by-Module)

ChatGPT expanded Gemini's hardening concept into a full, granular audit across modules, translating broad security intent into concrete engineering actions.

**Primary contributions:**

* Performed an exhaustive module-by-module review (logic boundaries, coupling, failure modes).
* Converted the hardening strategy into actionable corrective paths (preventive/detective/corrective controls per module where applicable).
* Identified implementation risks that typically appear only during real-world operations (configuration drift, unsafe defaults, error propagation).

### Claude — Defensive Implementation + Code Corrections

Claude executed the implementation fixes and code-level hardening based on the audited direction.

**Primary contributions:**

* Applied defensive coding practices (stronger typing, safer flows, better error handling patterns where needed).
* Implemented corrections directly in the codebase to align behavior with the audited architecture.
* Improved code stability by reducing brittle paths and tightening failure handling to prevent uncontrolled propagation.

**Quality gates used:** static review + module-level audit + implementation fixes aligned to a strict hardening strategy.

---

## Overview

PGO is a local-first opt-out auditing tool for data brokers. It guides BYOS (Bring Your Own Session) workflows, stores encrypted evidence (redacted screenshots/PDFs), and produces an append-only, tamper-evident audit trail (hash-chained event log) to support verification and resurfacing detection.

PGO does not remove data automatically. It audits your opt-out actions with reproducible proof and integrity checks.

---

## Why this exists

Data brokers often confirm "removal" without giving you a trustworthy, reproducible proof. Information can also reappear over time (resurfacing). PGO converts a messy manual process into a structured, auditable workflow:

* A state machine per broker (so you always know what's done and what's pending)
* Evidence captured and protected (redaction + encryption + hashing)
* Integrity checks (append-only event log + hash chain + optional signature)
* Re-checks to detect resurfacing

---

## What PGO does (v0.1 scope)

### Core capabilities

* **Manifest-driven BYOS workflows:** guided steps per broker. You do the interactive portal actions yourself.
* **State machine:** `discovered → confirmed → submitted → pending → verified / resurfaced`
* **Evidence vault (local):**

  * redact (basic) → hash → encrypt (AES-256-GCM + PBKDF2)
  * atomic write (temp → fsync → rename) — crash-safe, no corrupt files
  * store timestamp + integrity hash
* **Append-only event log (SQLite):**

  * every transition emits an immutable event
  * events are linked by `prev_hash` (tamper-evident chain)
* **Audit export (JSON/CSV):**

  * exports a canonical event envelope
  * verifies chain integrity and detects tampering
  * optional HMAC signature (local key)
* **PII guards:**

  * no clear-text PII in logs/exports by design
  * hashing/tokenization + redaction in any free-text fields

### Non-goals (explicit)

* No stealth scraping, no CAPTCHA bypass, no anti-bot evasion
* No automated form submission, no storing of portal credentials
* No guarantee of permanent deletion (PGO provides evidence + auditing only)
* No hosted backend in v0.1 (local-first only)

---

## Operational definition: "Proof of deletion"

PGO uses an operational (auditable) definition rather than legal certainty:

* **Primary signal (Tier A):** absence on the broker's public-facing page (BYOS revisit of the confirmed URL).
* **Verified:** absence confirmed across multiple checks (e.g., 2–3 checks over 30 days).
* **Resurfaced:** previously absent data is detected again on the same public page.

SERP-based signals (search engine results) are secondary only, because they're noisy (caches, delays, personalization).

---

## Threat model (short, realistic)

### Defends against

* Accidental edits and inconsistent record-keeping
* Detectable tampering of the audit trail (chain breaks / hash mismatch)
* PII leaks in exports/log output (guarded + tested)

### Does NOT defend against

* A fully compromised host where an attacker can rewrite history and recompute hashes
* Absolute legal proof against a hostile third party (no external timestamp anchoring in v0.1)

PGO is designed for operational auditing and reproducible evidence under normal use, not courtroom-grade non-repudiation.

---

## Project layout (src-layout)

```
privacyguard-ops/
  src/pgo/
    __init__.py
    cli.py
    manifest.py         # manifest loading + validation
    core/
      __init__.py
      audit.py           # export + verification (chain + optional HMAC)
      db.py              # SQLite connection + append-only triggers
      errors.py          # typed domain exceptions
      logging.py         # structlog pipeline + PII redaction
      models.py          # Pydantic models + enums
      paths.py           # repo root resolver
      repository.py      # findings CRUD + input validation
      settings.py        # Pydantic v2 settings (env + path resolution)
      state.py           # state machine + event emitter
    modules/
      __init__.py
      vault.py           # evidence vault (redact/hash/encrypt/atomic write)
      pii_guard.py       # redaction + hashing helpers
  manifests/
    brokers_manifest.yaml
  tests/
    unit/
    integration/
  README.md
  pyproject.toml
  .gitignore
```

### Runtime directories (created at first run)

These directories are created automatically with `0o700` permissions and kept outside version control:

```
vault/      # encrypted evidence storage
data/       # local SQLite database + runtime state
reports/    # generated audit reports
exports/    # exported audit envelopes (JSON/CSV)
```

---

## Install (dev)

**Requirements:** Python 3.12+

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

---

## Quickstart

```bash
pgo --help
pgo status
```

As features are implemented, the workflow will follow:

```bash
pgo scan --query "site:broker.com John Doe"
pgo confirm --broker broker.com --url "https://broker.com/profile/..."
pgo optout --broker broker.com
pgo verify --due
pgo export --audit --format json
```

---

## CLI commands (v0.1)

* `pgo scan` — discover candidates (CSE or manual inputs)
* `pgo add-url` — add a known public profile URL manually
* `pgo confirm` — confirm an item as "yours" (BYOS) + capture evidence
* `pgo optout` — guided submission steps (BYOS) + capture submission proof
* `pgo verify` — scheduled re-checks (Tier A primary)
* `pgo status` — show per-broker state + last check
* `pgo export --audit` — export append-only event log + verify integrity
* `pgo wipe` — wipe local case data + vault (user initiated)

In early development, some commands may be stubs. The goal is to keep the CLI installable and runnable end-to-end as we build.

---

## Audit log integrity (append-only + hash chain)

PGO uses an append-only event log enforced at the database level:

* Every transition emits an event row.
* SQLite triggers physically block `UPDATE` and `DELETE` on the events table — the append-only guarantee is enforced by the DB engine, not just application logic.
* Each event stores:

  * `entry_hash = SHA-256(canonical_event_blob)` — includes event fields and notes
  * `prev_hash = entry_hash(previous_event)`

Export produces an envelope with entries ordered by sequence and can include:

* optional HMAC signature using a local key (env var or prompt)

### Why this matters

* DB-level enforcement: even direct SQL access cannot modify or delete events
* Detects silent edits (chain mismatch if triggers are bypassed externally)
* Notes are included in the hash chain — changing a note breaks the chain
* Provides reproducible evidence for audits and internal review

---

## Privacy & storage

* Local-only by default
* No clear-text PII should be stored in exports/logs
* Evidence is stored encrypted in the vault; exports contain hashes/timestamps only

### Local state location

Local runtime data and evidence are kept outside Git (e.g., `vault/`, `data/`, `reports/`, `exports/`). The `.gitignore` is hardened to block: secrets/credentials, databases, logs, browser/session state (Playwright/Selenium), binary evidence (screenshots/PDFs/HARs), and automation artifacts. Only synthetic examples and schemas belong in version control.

---

## Security posture

* Local-first by default; no background data exfiltration.
* No credentials stored or auto-submitted (BYOS only).
* **Encryption:** AES-256-GCM (AEAD) with PBKDF2-HMAC-SHA256 key derivation (600,000 iterations, per-file random salt/nonce).
* **Atomic writes (CWE-362):** evidence is written to a temp file → `fsync` → `os.replace` (atomic rename). On crash/interrupt the target is either the previous version or absent — never a corrupt partial write.
* **Evidence size limit (CWE-400):** `store_evidence()` rejects inputs > 50 MB as an operational guardrail. This is a documented design constraint; the one-shot `AESGCM.encrypt()` API requires the full plaintext in memory. Streaming GCM (v3 wire format) is the planned path for large-evidence support.
* **Path traversal defence:** all vault paths are resolved and verified against the vault root (`_safe_vault_path`).
* HMAC-SHA256 PII tokenization (keyed — resistant to dictionary/rainbow attacks).
* Append-only DB triggers prevent modification or deletion of audit events at the SQLite engine level.
* PII redaction processor in structlog pipeline — personal data is scrubbed from all log output automatically.
* Directory hardening — runtime directories (`vault/`, `data/`, `reports/`, `exports/`) created with `0o700` permissions (owner-only access). Evidence files are `0o600`.
* **Input validation:** repository layer rejects SQL injection patterns, path traversal, and `javascript:` URIs at the boundary.
* **`.gitignore` hardened:** blocks secrets, databases, browser/session artifacts, binary evidence, captures, HAR files, and automation state from ever reaching version control.
* CI hardened: GitHub Actions pinned by full commit SHA; SBOM (CycloneDX) generated on every push; dependency audit via pip-audit; secret scanning via Gitleaks.
* Clear separation between code, local state, and generated outputs.

---

## Tests

```bash
pytest -q
```

Minimum test categories (v0.1):

* state transitions (no invalid jumps)
* audit integrity (tamper detection + chain verification)
* PII leak detection (regex scanning exports/log text)
* vault encryption/decryption correctness
* atomic write safety (no temp residue, crash-safe overwrite)
* path traversal defence (finding_id / filename escape blocked)
* input validation (SQL injection, path traversal, empty inputs rejected)

---

## Roadmap (post v0.1)

* Expand broker manifest coverage
* Improve redaction strategy
* Optional external timestamp anchoring (for stronger non-repudiation)

---

## Disclaimer

This tool is for operational auditing and evidence collection. It is not legal advice, and it does not guarantee deletion outcomes. You are responsible for complying with local laws and broker terms when performing opt-out actions.
