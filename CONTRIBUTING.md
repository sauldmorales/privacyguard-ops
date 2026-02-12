# Contributing to PrivacyGuard Ops (PGO)

Thank you for your interest in contributing to PrivacyGuard Ops! This document provides guidelines for contributing to the project.

---

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Git Workflow](#git-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Security](#security)

---

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the project and community
- Show empathy towards other community members

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- Git
- A GitHub account

### Initial Setup

1. **Fork the repository** on GitHub

2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/privacyguard-ops.git
   cd privacyguard-ops
   ```

3. **Add upstream remote:**
   ```bash
   git remote add upstream https://github.com/sauldmorales/privacyguard-ops.git
   ```

4. **Set up development environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -U pip
   pip install -e ".[dev]"
   ```

5. **Verify installation:**
   ```bash
   pgo --help
   pytest -q
   ```

---

## Development Workflow

### 1. Stay Synchronized

Before starting work, sync with the upstream repository:

```bash
git checkout main
git fetch upstream
git merge upstream/main
git push origin main
```

### 2. Create a Feature Branch

Always create a new branch for your work:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features or enhancements
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Adding or updating tests
- `chore/` - Maintenance tasks

### 3. Make Your Changes

- Write clear, concise commit messages
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed

### 4. Test Your Changes

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_state.py

# Run with coverage
pytest --cov=pgo tests/

# Type checking
mypy src/pgo

# Linting
ruff check src/ tests/
```

### 5. Commit Your Changes

Follow conventional commit messages:

```bash
git add .
git commit -m "feat: add new audit export format"
# or
git commit -m "fix: resolve PII leak in log output"
# or
git commit -m "docs: update installation instructions"
```

### 6. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 7. Create a Pull Request

- Go to your fork on GitHub
- Click "New Pull Request"
- Select your feature branch
- Fill out the PR template with details
- Link any related issues

---

## Git Workflow

### Branch Strategy

- `main` - Production-ready code
- `feature/*` - New features
- `fix/*` - Bug fixes
- `release/*` - Release preparation branches

### Advanced Git Commands

For detailed information on advanced Git commands and workflows, see our comprehensive guide:

**[📖 Advanced Git Commands Guide](docs/git-commands.md)**

This guide covers:
- `git stash` - Temporarily save changes
- `git cherry-pick` - Apply specific commits
- `git revert` - Safely undo commits
- `git reset` - Rewrite local history

### Common Scenarios

#### Scenario 1: Switching branches with uncommitted changes

```bash
# Save your work temporarily
git stash save "WIP: working on audit export"

# Switch branches
git checkout another-branch

# Do your work...

# Return to original branch
git checkout feature/audit-export
git stash pop
```

#### Scenario 2: Fixing commit on wrong branch

```bash
# You committed to main instead of a feature branch
git log --oneline  # Note the commit hash

# Create feature branch with your changes
git branch feature/my-work

# Reset main to match upstream
git checkout main
git reset --hard upstream/main

# Continue work on feature branch
git checkout feature/my-work
```

#### Scenario 3: Applying a hotfix to multiple branches

```bash
# Create hotfix
git checkout -b hotfix/security-fix main
# ... make fix and commit ...

# Apply to release branch
git checkout release/v0.1
git cherry-pick <commit-hash>

# Apply to main
git checkout main
git cherry-pick <commit-hash>
```

### Working with Stash

When working with local test data or evidence files:

```bash
# Stash everything including untracked files
git stash -u

# Or stash with a message
git stash save "Local test evidence files"

# List stashes
git stash list

# Apply and keep stash
git stash apply

# Apply and remove stash
git stash pop
```

### Keeping History Clean

Before submitting a PR, clean up your commit history:

```bash
# Squash last 3 commits
git reset --soft HEAD~3
git commit -m "feat: implement comprehensive audit export feature"

# Or use interactive rebase
git rebase -i HEAD~3
```

**⚠️ Warning:** Only rewrite history on branches that haven't been pushed or are only yours!

---

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 100 characters
- Use meaningful variable and function names

### Code Structure

- Keep functions focused and single-purpose
- Use Pydantic models for data validation
- Write docstrings for public APIs
- Include type annotations

### Example:

```python
from typing import Optional
from pydantic import BaseModel


class AuditEvent(BaseModel):
    """Represents an immutable audit log event.
    
    Attributes:
        event_id: Unique identifier for the event
        timestamp: ISO 8601 timestamp
        event_type: Type of state transition
        prev_hash: Hash of the previous event in chain
    """
    event_id: str
    timestamp: str
    event_type: str
    prev_hash: Optional[str] = None
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of canonical event representation."""
        # Implementation
        pass
```

### Linting and Formatting

We use:
- **Ruff** for linting and formatting
- **MyPy** for type checking
- **Pytest** for testing

Run checks before committing:

```bash
# Format code
ruff format src/ tests/

# Check for issues
ruff check src/ tests/

# Type check
mypy src/pgo

# Run all checks
ruff check src/ tests/ && mypy src/pgo && pytest
```

---

## Testing

### Test Structure

```
tests/
├── unit/           # Unit tests for individual components
└── integration/    # Integration tests for workflows
```

### Writing Tests

- Test file names: `test_*.py`
- Test function names: `test_*`
- Use fixtures for setup/teardown
- Test both success and failure cases
- Include edge cases

### Example Test:

```python
import pytest
from pgo.core.state import StateMachine, BrokerState


def test_state_transition_valid():
    """Test valid state transition."""
    sm = StateMachine()
    result = sm.transition(
        from_state=BrokerState.DISCOVERED,
        to_state=BrokerState.CONFIRMED
    )
    assert result.success is True
    assert result.new_state == BrokerState.CONFIRMED


def test_state_transition_invalid():
    """Test invalid state transition is rejected."""
    sm = StateMachine()
    with pytest.raises(ValueError):
        sm.transition(
            from_state=BrokerState.DISCOVERED,
            to_state=BrokerState.VERIFIED  # Invalid jump
        )
```

### Test Categories

1. **State transitions** - Verify state machine logic
2. **Audit integrity** - Test hash chain and tamper detection
3. **PII guards** - Ensure no PII leaks in exports
4. **Vault operations** - Test encryption/decryption
5. **Evidence handling** - Test redaction and storage

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_audit.py

# Specific test
pytest tests/unit/test_audit.py::test_chain_integrity

# With coverage
pytest --cov=pgo --cov-report=html tests/

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

---

## Pull Request Process

### Before Submitting

1. **Ensure all tests pass:**
   ```bash
   pytest
   ```

2. **Check code quality:**
   ```bash
   ruff check src/ tests/
   mypy src/pgo
   ```

3. **Update documentation:**
   - Update docstrings
   - Update README.md if needed
   - Update relevant docs in `docs/`

4. **Clean commit history:**
   - Squash "WIP" commits
   - Write clear commit messages
   - Use conventional commit format

### PR Template

When creating a PR, include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Testing

## Testing
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings introduced
- [ ] No PII leaks in logs/exports
```

### Review Process

1. Automated checks will run on your PR
2. A maintainer will review your code
3. Address any feedback or requested changes
4. Once approved, a maintainer will merge your PR

### Addressing Feedback

```bash
# Make changes based on feedback
git add .
git commit -m "address review feedback: improve error handling"
git push origin feature/your-feature

# If asked to squash commits
git reset --soft HEAD~3
git commit -m "feat: complete feature implementation"
git push --force-with-lease origin feature/your-feature
```

---

## Security

### Security-First Development

PrivacyGuard Ops handles sensitive data. Security is paramount:

1. **Never commit secrets:**
   - API keys
   - Passwords
   - Encryption keys
   - Test data with real PII

2. **Use `.gitignore`:**
   - Evidence files stay in `vault/` (ignored)
   - Databases stay in `data/` (ignored)
   - Logs stay in `reports/` (ignored)

3. **PII Protection:**
   - Never log clear-text PII
   - Use hashing/tokenization
   - Test exports for PII leaks
   - Use redaction helpers

4. **Input Validation:**
   - Use Pydantic models
   - Validate all user inputs
   - Sanitize file paths
   - Escape output for logs/exports

### Reporting Security Issues

**DO NOT** open a public issue for security vulnerabilities.

Instead:
1. Email the maintainer directly (see README.md)
2. Provide detailed description
3. Include steps to reproduce
4. Wait for response before disclosure

### Security Testing

```bash
# Check for known vulnerabilities
pip install safety
safety check

# Static security analysis
pip install bandit
bandit -r src/pgo

# Check for hardcoded secrets
pip install detect-secrets
detect-secrets scan
```

---

## Development Tips

### Local Testing with Evidence

```bash
# Create test evidence in vault/
echo "test evidence" > vault/test_evidence.txt

# Work with code, evidence is ignored by git
git status  # vault/test_evidence.txt not shown

# Stash if switching branches (just in case)
git stash -u
```

### Debugging

```bash
# Run with verbose logging
pgo --verbose status

# Run Python debugger
python -m pdb -c continue -m pgo.cli status

# Or use IDE debugger with breakpoints
```

### Working with Manifests

```bash
# Manifests are ignored by default
# Create a local manifest for testing
cp manifests/brokers_manifest.yaml manifests/test_manifest.local.yaml

# Edit your local manifest
vim manifests/test_manifest.local.yaml

# This won't be committed (*.local.yaml is ignored)
```

---

## Documentation

### Updating Documentation

When adding features or making changes:

1. **Update docstrings** in code
2. **Update README.md** if it affects usage
3. **Add to `docs/`** for detailed guides
4. **Update CONTRIBUTING.md** if it affects workflow

### Documentation Style

- Use clear, concise language
- Include code examples
- Add diagrams where helpful
- Link related documentation

---

## Questions or Need Help?

- Open an issue with the `question` label
- Check existing issues and documentation
- Refer to the [Git Commands Guide](docs/git-commands.md)

---

## License

By contributing to PrivacyGuard Ops, you agree that your contributions will be licensed under the same license as the project.

---

## Thank You!

Your contributions help make PrivacyGuard Ops better for everyone. We appreciate your time and effort! 🙏
