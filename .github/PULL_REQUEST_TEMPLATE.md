## Description

<!-- Brief summary of the changes. Link to related issues with "Closes #123". -->

## Type of change

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to change)
- [ ] 📚 Documentation update
- [ ] 🔧 Refactor / chore (no functional change)

## Security checklist

> PGO handles PII, encrypted evidence, and tamper-evident audit trails. Every PR must pass this checklist.

- [ ] **No PII in code/comments/tests**: No real names, emails, addresses, or personal URLs.
- [ ] **No secrets committed**: No API keys, tokens, passwords, or encryption keys in source.
- [ ] **PII guards preserved**: If touching `pii_guard.py`, `vault.py`, or models — redaction/hashing still works.
- [ ] **Audit chain intact**: If touching `state.py` or `audit.py` — hash chain integrity is preserved.
- [ ] **Vault encryption safe**: If touching `vault.py` — encryption/decryption roundtrip verified.
- [ ] **Tests added/updated**: New behavior has corresponding tests. Existing tests still pass.
- [ ] **No `|| true` masking failures**: CI steps should fail on real errors.

## Testing

<!-- How was this tested? -->

```bash
pytest tests/ -v --tb=short
ruff check src/ tests/
mypy src/pgo/ --ignore-missing-imports
```

## Additional notes

<!-- Anything reviewers should know? -->
