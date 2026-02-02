# PrivacyGuard Ops (PGO)

**PGO** is a **local-first opt-out auditing tool** for data brokers. It guides **BYOS (Bring Your Own Session)** workflows, stores **encrypted evidence** (redacted screenshots/PDFs), and produces an **append-only, tamper-evident audit trail** (hash-chained event log) to support verification and resurfacing detection.

> PGO does **not** remove data automatically. It audits *your* opt-out actions with reproducible proof and integrity checks.

---

## Why this exists
Data brokers often confirm “removal” without giving you a trustworthy, reproducible proof. Information can also reappear over time (resurfacing). PGO converts a messy manual process into a structured, auditable workflow:
- A state machine per broker (so you always know what’s done and what’s pending)
- Evidence captured and protected (redaction + encryption + hashing)
- Integrity checks (append-only event log + hash chain + optional signature)
- Re-checks to detect resurfacing

---

## What PGO does (v0.1 scope)
### Core capabilities
- **Manifest-driven BYOS workflows**: guided steps per broker. You do the interactive portal actions yourself.
- **State machine**: `discovered → confirmed → submitted → pending → verified / resurfaced`
- **Evidence vault (local)**:
	- redact (basic) → hash → encrypt
	- store timestamp + integrity hash
- **Append-only event log (SQLite)**:
	- every transition emits an immutable event
	- events are linked by `prev_hash` (tamper-evident chain)
- **Audit export (JSON/CSV)**:
	- exports a canonical event envelope
	- verifies chain integrity and detects tampering
	- optional HMAC signature (local key)
- **PII guards**:
	- no clear-text PII in logs/exports by design
	- hashing/tokenization + redaction in any free-text fields

### Non-goals (explicit)
- No stealth scraping, no CAPTCHA bypass, no anti-bot evasion
- No automated form submission, no storing of portal credentials
- No guarantee of permanent deletion (PGO provides evidence + auditing only)
- No hosted backend in v0.1 (local-first only)

---

## Operational definition: “Proof of deletion”
PGO uses an operational (auditable) definition rather than legal certainty:

- **Primary signal (Tier A)**: absence on the broker’s public-facing page (BYOS revisit of the confirmed URL).
- **Verified**: absence confirmed across multiple checks (e.g., **2–3 checks over 30 days**).
- **Resurfaced**: previously absent data is detected again on the same public page.

> SERP-based signals (search engine results) are secondary only, because they’re noisy (caches, delays, personalization).

---

## Threat model (short, realistic)
### Defends against
- Accidental edits and inconsistent record-keeping
- Detectable tampering of the audit trail (chain breaks / hash mismatch)
- PII leaks in exports/log output (guarded + tested)

### Does NOT defend against
- A fully compromised host where an attacker can rewrite history and recompute hashes
- Absolute legal proof against a hostile third party (no external timestamp anchoring in v0.1)

PGO is designed for **operational auditing** and reproducible evidence under normal use, not courtroom-grade non-repudiation.

---

## Project layout (src-layout)
```
privacyguard-ops/
src/pgo/
**init**.py
cli.py
core/
**init**.py
state.py        # state machine + event emitter
models.py       # Pydantic models + enums
audit.py        # export + verification (chain + optional HMAC)
modules/
**init**.py
vault.py        # evidence vault (redact/hash/encrypt)
pii_guard.py    # redaction + hashing helpers
manifests/
brokers_manifest.yaml
reports/
tests/
unit/
integration/
README.md
pyproject.toml
.gitignore

```

---

## Install (dev)
Requirements: Python **3.12+**

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
* `pgo confirm` — confirm an item as “yours” (BYOS) + capture evidence
* `pgo optout` — guided submission steps (BYOS) + capture submission proof
* `pgo verify` — scheduled re-checks (Tier A primary)
* `pgo status` — show per-broker state + last check
* `pgo export --audit` — export append-only event log + verify integrity
* `pgo wipe` — wipe local case data + vault (user initiated)

> In early development, some commands may be stubs. The goal is to keep the CLI installable and runnable end-to-end as we build.

---

## Audit log integrity (append-only + hash chain)

PGO uses an append-only event log design:

* Every transition emits an event row (no updates/deletes)
* Each event stores:

	* `entry_hash = SHA-256(canonical_event_blob)`
	* `prev_hash = entry_hash(previous_event)`
* Export produces an envelope with entries ordered by sequence and can include:

	* optional HMAC signature using a local key (env var or prompt)

### Why this matters

* Detects silent edits inside SQLite (chain mismatch)
* Provides reproducible evidence for audits and internal review

---

## Privacy & storage

* Local-only by default
* No clear-text PII should be stored in exports/logs
* Evidence is stored encrypted in the vault; exports contain hashes/timestamps only

## Local state location

Local runtime data and evidence are kept outside Git (e.g., `vault/`, `data/`, `reports/`, `exports/`). This keeps sensitive or generated artifacts from leaking into version control.

## Security posture (short)

* Local-first by default; no background data exfiltration.
* No credentials stored or auto-submitted (BYOS only).
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

---

## Roadmap (post v0.1)

* Expand broker manifest coverage
* Improve redaction strategy
* Optional external timestamp anchoring (for stronger non-repudiation)

---

## Disclaimer

This tool is for operational auditing and evidence collection. It is not legal advice, and it does not guarantee deletion outcomes. You are responsible for complying with local laws and broker terms when performing opt-out actions.
