# Advanced Git Commands Guide

This guide covers advanced Git commands that are essential for managing complex workflows, handling mistakes, and maintaining a clean commit history in the PrivacyGuard Ops project.

---

## Table of Contents
- [git stash](#git-stash)
- [git cherry-pick](#git-cherry-pick)
- [git revert](#git-revert)
- [git reset](#git-reset)
- [Best Practices](#best-practices)

---

## git stash

### What it does
`git stash` temporarily shelves (or stashes) changes you've made to your working directory so you can work on something else, then come back and re-apply them later.

### When to use it
- You need to switch branches but have uncommitted changes
- You want to clean your working directory without losing work
- You need to pull the latest changes but have local modifications

### Basic Usage

#### Stash current changes
```bash
# Stash all tracked files
git stash

# Stash with a descriptive message
git stash save "WIP: working on vault encryption feature"

# Stash including untracked files
git stash -u

# Stash including untracked and ignored files
git stash -a
```

#### List stashes
```bash
# View all stashes
git stash list
```

Output example:
```
stash@{0}: WIP on main: 5002d47 Add vault encryption
stash@{1}: WIP on main: c264051 Update PII guard
```

#### Apply stashed changes
```bash
# Apply the most recent stash
git stash apply

# Apply a specific stash
git stash apply stash@{1}

# Apply and remove from stash list (pop)
git stash pop

# Pop a specific stash
git stash pop stash@{1}
```

#### Remove stashes
```bash
# Remove the most recent stash
git stash drop

# Remove a specific stash
git stash drop stash@{1}

# Remove all stashes
git stash clear
```

### Real-world Example
```bash
# You're working on a feature branch
git checkout feature/audit-export

# Make some changes to vault.py
vim src/pgo/modules/vault.py

# Urgent bug fix needed on main branch
git stash save "WIP: vault encryption improvements"

# Switch to main and fix the bug
git checkout main
# ... fix bug and commit ...

# Return to your feature branch
git checkout feature/audit-export

# Restore your work
git stash pop
```

---

## git cherry-pick

### What it does
`git cherry-pick` allows you to apply a specific commit from one branch to another. It creates a new commit with the same changes but a different commit hash.

### When to use it
- You need a specific fix from another branch
- You want to apply a hotfix to multiple release branches
- You accidentally committed to the wrong branch

### Basic Usage

#### Pick a single commit
```bash
# Cherry-pick a commit by its hash
git cherry-pick <commit-hash>

# Example
git cherry-pick a1b2c3d4
```

#### Pick multiple commits
```bash
# Cherry-pick a range of commits
git cherry-pick <start-commit>..<end-commit>

# Example
git cherry-pick abc123..def456

# Cherry-pick multiple specific commits
git cherry-pick commit1 commit2 commit3
```

#### Cherry-pick with options
```bash
# Cherry-pick without committing (stage changes only)
git cherry-pick -n <commit-hash>
git cherry-pick --no-commit <commit-hash>

# Cherry-pick and edit the commit message
git cherry-pick -e <commit-hash>
git cherry-pick --edit <commit-hash>

# Cherry-pick and add sign-off
git cherry-pick -s <commit-hash>
git cherry-pick --signoff <commit-hash>
```

#### Handle conflicts
```bash
# If conflicts occur during cherry-pick:

# 1. Resolve conflicts in your editor
vim <conflicted-file>

# 2. Stage the resolved files
git add <resolved-file>

# 3. Continue the cherry-pick
git cherry-pick --continue

# Or abort if you change your mind
git cherry-pick --abort
```

### Real-world Example
```bash
# Scenario: You fixed a critical bug on the development branch
# and need to apply it to the production release branch

# First, find the commit hash
git log --oneline
# Output: 5f3e8b2 Fix PII leak in audit export

# Checkout the release branch
git checkout release/v0.1

# Cherry-pick the fix
git cherry-pick 5f3e8b2

# The fix is now applied to the release branch
git log --oneline
# Output: 9a7c4d1 Fix PII leak in audit export (cherry-picked from 5f3e8b2)
```

### Example: Applying hotfix to multiple branches
```bash
# Apply a security fix to multiple release branches
git checkout release/v0.1
git cherry-pick 8c3f5a1

git checkout release/v0.2
git cherry-pick 8c3f5a1

git checkout main
git cherry-pick 8c3f5a1
```

---

## git revert

### What it does
`git revert` creates a new commit that undoes the changes from a previous commit. Unlike `git reset`, it doesn't rewrite history, making it safe for shared branches.

### When to use it
- You need to undo a commit that has been pushed to a shared branch
- You want to maintain a complete history of changes
- You need to undo changes without affecting other developers

### Basic Usage

#### Revert a single commit
```bash
# Revert the most recent commit
git revert HEAD

# Revert a specific commit
git revert <commit-hash>

# Example
git revert 3f2e1d0
```

#### Revert multiple commits
```bash
# Revert a range of commits (oldest to newest)
git revert <oldest-commit>..<newest-commit>

# Example
git revert abc123..def456

# Revert without creating a commit immediately
git revert -n <commit-hash>
git revert --no-commit <commit-hash>
```

#### Revert with options
```bash
# Revert and edit the commit message
git revert -e <commit-hash>

# Revert a merge commit (specify parent)
git revert -m 1 <merge-commit-hash>
```

### Real-world Example
```bash
# Scenario: A feature was merged but caused issues in production

# View recent commits
git log --oneline
# Output:
# 7d4f2e1 Merge feature/new-scanner
# 3c8b5a0 Add automated scanning
# 2f1e9d3 Update dependencies

# Revert the problematic feature merge
git revert 7d4f2e1 -m 1

# This creates a new commit that undoes the merge
git log --oneline
# Output:
# 9e5c3f2 Revert "Merge feature/new-scanner"
# 7d4f2e1 Merge feature/new-scanner
# 3c8b5a0 Add automated scanning
# 2f1e9d3 Update dependencies
```

### Example: Reverting multiple commits
```bash
# Revert the last 3 commits without auto-committing
git revert --no-commit HEAD~2..HEAD

# Review the changes
git status
git diff --staged

# Commit all reverts at once with a descriptive message
git commit -m "Revert problematic changes from audit export refactor"
```

---

## git reset

### What it does
`git reset` moves the current branch pointer to a different commit. It can modify the staging area and working directory depending on the mode used. **Warning:** This rewrites history and should be used carefully on shared branches.

### When to use it
- You need to undo local commits before pushing
- You want to unstage files
- You need to completely reset your branch to match remote
- You're working on a feature branch that hasn't been shared

### The Three Modes

#### 1. Soft Reset (--soft)
Moves HEAD but keeps changes in staging area.

```bash
# Reset to a previous commit, keeping changes staged
git reset --soft HEAD~1

# Reset to a specific commit
git reset --soft <commit-hash>
```

**Use case:** You want to recommit with a better message or split into multiple commits.

#### 2. Mixed Reset (--mixed, default)
Moves HEAD and unstages changes, but keeps them in working directory.

```bash
# Reset and unstage (default behavior)
git reset HEAD~1
git reset --mixed HEAD~1

# Unstage specific files
git reset HEAD <file>
```

**Use case:** You want to undo commits and reorganize changes before recommitting.

#### 3. Hard Reset (--hard)
Moves HEAD and discards all changes. **Destructive!**

```bash
# Reset and discard all changes
git reset --hard HEAD~1

# Reset to match remote branch exactly
git reset --hard origin/main

# Reset to a specific commit
git reset --hard <commit-hash>
```

**Use case:** You want to completely discard changes and return to a clean state.

### Basic Usage

#### Undo the last commit
```bash
# Keep changes staged
git reset --soft HEAD~1

# Keep changes in working directory (unstaged)
git reset HEAD~1

# Discard changes completely
git reset --hard HEAD~1
```

#### Undo multiple commits
```bash
# Undo last 3 commits, keep changes
git reset HEAD~3

# Undo last 3 commits, discard changes
git reset --hard HEAD~3
```

#### Reset to a specific commit
```bash
# Find the commit hash
git log --oneline

# Reset to that commit
git reset --hard a1b2c3d

# Or reset to a tag
git reset --hard v0.1.0
```

#### Unstage files
```bash
# Unstage a specific file
git reset HEAD <file>

# Unstage all files
git reset HEAD .
```

### Real-world Examples

#### Example 1: Fix a commit message
```bash
# You just committed with a typo in the message
git commit -m "Fix vult encryption bug"  # Oops, "vult" should be "vault"

# Undo the commit but keep changes staged
git reset --soft HEAD~1

# Recommit with correct message
git commit -m "Fix vault encryption bug"
```

#### Example 2: Combine multiple commits
```bash
# You made 3 small commits that should be one
git log --oneline
# Output:
# 3d7f2e1 Fix typo in comment
# 9c4b5a2 Add missing import
# 7e1f3d8 Implement vault encryption

# Reset to before these commits, keeping changes staged
git reset --soft HEAD~3

# Commit them all at once
git commit -m "Implement vault encryption with proper imports and documentation"
```

#### Example 3: Discard all local changes
```bash
# Your local branch is messy and you want to start fresh

# See what would be lost
git status
git diff

# Discard all changes and match remote
git fetch origin
git reset --hard origin/main

# Clean up untracked files too
git clean -fd
```

#### Example 4: Unstage files before committing
```bash
# You staged too many files
git add .
git status

# Unstage specific files
git reset HEAD src/pgo/modules/test_helpers.py
git reset HEAD reports/temp_report.json

# Or unstage everything
git reset HEAD .

# Now stage only what you need
git add src/pgo/core/audit.py src/pgo/core/state.py
git commit -m "Update audit chain verification"
```

### Important Warnings

⚠️ **Never use `git reset --hard` on shared branches!** This rewrites history and will cause problems for other developers.

⚠️ **Before using `git reset --hard`, make sure you don't have uncommitted changes you want to keep.** Consider using `git stash` first.

⚠️ **If you've already pushed commits, use `git revert` instead of `git reset`.** This maintains history and is safe for collaboration.

---

## Best Practices

### General Guidelines

1. **For shared branches:** Use `git revert` instead of `git reset`
   - Maintains history
   - Safe for collaboration
   - Can be easily undone

2. **For local branches:** `git reset` is fine before pushing
   - Clean up messy commit history
   - Combine related commits
   - Fix commit messages

3. **Use `git stash` frequently**
   - Before switching branches
   - Before pulling updates
   - To temporarily set aside experimental changes

4. **Cherry-pick with caution**
   - Prefer merging when possible
   - Use for specific fixes that need to be backported
   - Document why you're cherry-picking in the commit message

### Workflow Examples

#### Clean feature branch workflow
```bash
# Start a feature
git checkout -b feature/new-audit-check

# Make commits as you work
git add . && git commit -m "WIP: initial audit check structure"
git add . && git commit -m "WIP: add validation logic"
git add . && git commit -m "WIP: add tests"

# Before merging, clean up commits
git reset --soft HEAD~3
git commit -m "Add comprehensive audit chain validation"

# Now push the clean feature
git push origin feature/new-audit-check
```

#### Hotfix workflow with cherry-pick
```bash
# Critical bug found in production
git checkout -b hotfix/security-fix main

# Fix the bug
vim src/pgo/modules/pii_guard.py
git add . && git commit -m "Fix XSS vulnerability in PII redaction"

# Apply to production
git checkout release/v0.1
git cherry-pick <commit-hash>
git push origin release/v0.1

# Apply to development
git checkout main
git cherry-pick <commit-hash>
git push origin main
```

#### Recover from mistakes
```bash
# You accidentally committed to main instead of a feature branch
git log --oneline  # Get the commit hash

# Create a feature branch with your changes
git branch feature/my-work

# Reset main to match remote (remove your commit)
git reset --hard origin/main

# Switch to your feature branch (your work is safe there)
git checkout feature/my-work
```

### Commit Message Convention

When using these commands, follow these commit message conventions:

- **Revert commits:** `Revert "Original commit message"`
- **Cherry-pick commits:** Add `(cherry picked from commit <hash>)` to the message
- **Reset/recommit:** Use a clear, descriptive message explaining the final state

### Safety Tips

1. **Before destructive operations:**
   ```bash
   # Create a backup branch
   git branch backup-$(date +%Y%m%d)
   
   # Or tag the current state
   git tag before-reset-$(date +%Y%m%d-%H%M%S)
   ```

2. **Check what you're about to do:**
   ```bash
   # Before git reset --hard
   git status
   git diff
   git log --oneline -n 5
   
   # Before git cherry-pick
   git show <commit-hash>
   ```

3. **Verify after operations:**
   ```bash
   # After any operation
   git log --oneline -n 5
   git status
   git diff origin/main
   ```

### Recovery Commands

If you make a mistake, Git's reflog can help you recover:

```bash
# View reflog (shows all HEAD movements)
git reflog

# Restore to a previous state
git reset --hard HEAD@{2}

# Or restore to a specific commit from reflog
git reset --hard <reflog-hash>
```

---

## PrivacyGuard Ops Specific Guidelines

### For this project:

1. **Never commit sensitive data** - Use `git stash` if you have local test data
2. **Clean vault before commits** - Evidence files should not be in version control
3. **Audit log integrity** - Don't use `reset --hard` on branches with audit events
4. **Security fixes** - Use `cherry-pick` to apply fixes across release branches
5. **Feature development** - Clean up commits with `reset --soft` before PR

### Example: Working with PGO
```bash
# You're testing with local evidence
git stash -u  # Stash untracked files (evidence)

# Make code changes
vim src/pgo/modules/vault.py
git add . && git commit -m "Improve vault encryption"

# Test needs evidence back
git stash pop

# Evidence files are back in vault/ but still ignored by .gitignore
```

---

## Additional Resources

- [Official Git Documentation](https://git-scm.com/doc)
- [Git Book - Stashing](https://git-scm.com/book/en/v2/Git-Tools-Stashing-and-Cleaning)
- [Git Book - Reset](https://git-scm.com/book/en/v2/Git-Tools-Reset-Demystified)
- [Atlassian Git Tutorials](https://www.atlassian.com/git/tutorials)

---

## Quick Reference Card

| Command | Use Case | Safe for Shared Branches? |
|---------|----------|---------------------------|
| `git stash` | Temporarily save changes | ✅ Yes |
| `git stash pop` | Restore stashed changes | ✅ Yes |
| `git cherry-pick <hash>` | Apply specific commit | ✅ Yes (creates new commit) |
| `git revert <hash>` | Undo a commit | ✅ Yes (creates new commit) |
| `git reset --soft HEAD~1` | Undo commit, keep changes staged | ⚠️ Only before push |
| `git reset HEAD~1` | Undo commit, unstage changes | ⚠️ Only before push |
| `git reset --hard HEAD~1` | Undo commit, discard changes | ❌ No (destructive) |
| `git reset --hard origin/main` | Match remote exactly | ❌ No (destructive) |

---

**Remember:** When in doubt, create a backup branch first, and prefer commands that don't rewrite history on shared branches!
