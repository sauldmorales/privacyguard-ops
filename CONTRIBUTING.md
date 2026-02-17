# Contributing to PrivacyGuard-Ops

Thank you for your interest in contributing! PGO is a privacy-focused auditing tool, so contributions must follow strict security and privacy guidelines.

## ⚠️ Security-first rules

1. **Never commit real PII**: No real names, emails, phone numbers, addresses, or personal URLs — not in code, tests, comments, commit messages, or issues. Use placeholders like `user@example.com`, `John Doe`, `[REDACTED]`.

2. **Never commit secrets**: No API keys, tokens, passwords, encryption keys, or `.env` files. The `.gitignore` blocks most patterns, but you are responsible for verifying.

3. **Security vulnerabilities**: Report privately via [SECURITY.md](SECURITY.md) — **never** in a public issue.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

## Before submitting a PR

### Run the full check suite

```bash
# Lint
ruff check src/ tests/

# Type check
mypy src/pgo/ --ignore-missing-imports

# Tests
pytest tests/ -v --tb=short
```

### Pre-commit hooks (recommended)

```bash
pip install pre-commit
pre-commit install
```

This will automatically run secret scanning, linting, and formatting on every commit.

### PR checklist

Every PR must address the [security checklist](/.github/PULL_REQUEST_TEMPLATE.md):

- [ ] No PII in code/comments/tests
- [ ] No secrets committed
- [ ] PII guards preserved (if touching redaction/hashing)
- [ ] Audit chain intact (if touching state/events)
- [ ] Vault encryption safe (if touching vault)
- [ ] Tests added/updated
- [ ] CI passes (lint + typecheck + tests)

## Code style

- **Formatter/linter**: `ruff` (configured in `pyproject.toml`)
- **Type hints**: Required for all public functions
- **Imports**: Use absolute imports from `pgo.*`
- **Tests**: Mirror `src/` structure in `tests/unit/`

## Commit messages

Follow conventional commits:

```
feat: add broker resurfacing detection
fix: prevent PII leak in export envelope
test: add vault roundtrip encryption test
docs: update threat model section
ci: add secret scanning to workflow
deps: bump cryptography to 43.x
```

## Questions?

Open a discussion or reach out to the maintainer.
