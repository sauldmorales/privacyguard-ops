# Security Policy

## Supported versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a vulnerability

**DO NOT open a public GitHub Issue for security vulnerabilities.**

Instead, please report them responsibly:

1. **Email**: Report via [GitHub Security Advisories](https://github.com/sauldmorales/privacyguard-ops/security/advisories) (preferred) or contact the maintainer directly.
2. **Subject**: `[SECURITY] <short description>`
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You should receive an acknowledgment within **48 hours**. We aim to provide a fix or mitigation within **7 days** for critical issues.

## Scope

The following are in scope:

- Tamper-evident chain bypass or integrity failures
- PII leakage in logs, exports, or error messages
- Vault encryption/decryption weaknesses
- Dependency vulnerabilities (cryptography, pydantic, etc.)
- Secret exposure in CI/CD pipelines or artifacts
- Authentication/authorization flaws (future versions)

## Out of scope

- Denial-of-service on local-only CLI
- Issues requiring physical access to the host
- Social engineering attacks

## Disclosure policy

- We follow **coordinated disclosure**: fixes are developed privately and released before public disclosure.
- Credit is given to reporters (unless they prefer anonymity).
- We aim for a **90-day** disclosure timeline from report to public fix.

## Security design principles

PGO follows these security principles by design:

1. **Local-first**: No data leaves the machine unless the user explicitly exports.
2. **No credentials stored**: BYOS (Bring Your Own Session) — PGO never handles portal passwords.
3. **PII guards**: All free-text fields pass through HMAC tokenisation and regex redaction before storage. Logs are scrubbed by a structlog PII processor.
4. **Append-only audit trail**: Events are hash-chained (notes included in hash); SQLite triggers block UPDATE/DELETE at the DB engine level.
5. **Encrypted evidence vault**: Evidence at rest uses **AES-256-GCM** (AEAD) with **PBKDF2-HMAC-SHA256** key derivation (600,000 iterations, per-file random salt).
6. **Minimal dependencies**: Only well-maintained, audited libraries. Supply chain hardened with hash-pinned lockfile and SHA-pinned GitHub Actions.
