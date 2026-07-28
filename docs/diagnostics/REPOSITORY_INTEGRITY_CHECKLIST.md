# Repository Integrity Checklist (Executable Pre-Flight)

**Companion to:** `SECTION0_REPOSITORY_INTEGRITY.md`
**Purpose:** A concrete, executable checklist that agents run before any
git operation or experiment that depends on repository state.

---

## How to Use

Before any of these actions:
- merge
- push
- branch decision
- release preparation
- claiming a commit exists
- running EXP-028 (or any EXP) instrumentation
- publishing a report that references repository state

**Run every command below, capture the output, and fill in the checklist.**
If any field is empty or any check fails, STOP and report to the user.

---

## Step 1 — Capture Raw Git State

Run these commands and paste the output into the corresponding fields:

```bash
# 1.1 Remote URL
git remote -v

# 1.2 Local branch (with tracking info)
git branch -vv

# 1.3 All branches (local + remote)
git branch -a

# 1.4 Recent local commits
git log --oneline --decorate -5

# 1.5 GROUND TRUTH from GitHub
git ls-remote origin
```

---

## Step 2 — Fill in the Four-Field Branch Verification (Rule 2)

```
Current local branch:        ____________
Remote tracking branch:      ____________ -> ____________
Default GitHub branch:       ____________ -> ____________
EXP commit location:         ____________
```

### How to determine each field

- **Current local branch:** From `git branch -vv` — the line starting with `*`
- **Remote tracking branch:** From `git branch -vv` — the `[origin/...]` part
- **Default GitHub branch:** From `git ls-remote origin` — the ref that `HEAD` points to
- **EXP commit location:** Compare the EXP commit hash against origin/main and origin/master

### Example (filled in)

```
Current local branch:        master
Remote tracking branch:      origin/master -> 08c0735
Default GitHub branch:       main -> 3e3d8081
EXP commit location:         on master only (NOT on default branch)
```

---

## Step 3 — Push Verification (Rule 1)

If you are about to claim "push succeeded", verify with:

```bash
git ls-remote origin refs/heads/<branch>
```

The output MUST contain the expected commit hash.

### Check

```
Expected commit hash:        ____________
Expected remote branch:      ____________
git ls-remote output:        ____________
Push verified (Rule 1):      [ ] YES  [ ] NO
```

If NO, you MUST NOT claim "push succeeded".

---

## Step 4 — Branch Divergence Check (Rule 3)

If `master != main` (EXP commit on master, not on default branch main):

```
master contains EXP commit:  [ ] YES  [ ] NO
main contains EXP commit:    [ ] YES  [ ] NO
```

If YES on master and NO on main:

**STOP. Do NOT merge automatically.**

Ask the user:

```
EXP commit is on master only. The default branch is main, which does
NOT have the EXP changes.

Option A: Keep EXP branch isolated on master. No action.
Option B: Merge master into main. Requires explicit approval.

Please choose A or B.
```

---

## Step 5 — Independent Verification (Rule 4)

For important commits (release tags, EXP milestones), run BOTH methods:

### Method 1: git ls-remote

```bash
git ls-remote origin refs/heads/<branch>
```

Output: ____________

### Method 2: GitHub API

```bash
curl -s "https://api.github.com/repos/Sh-TB/sharpemuT24/commits/<hash>/branches-where-head"
```

Output: ____________

### Verdict

```
Method 1 (git ls-remote):    [ ] PASS  [ ] FAIL
Method 2 (GitHub API):       [ ] PASS  [ ] FAIL  [ ] N/A (rate-limited)
Final verdict:               [ ] VERIFIED (PROVEN)  [ ] VERIFIED (single method)  [ ] NOT PROVEN
```

---

## Step 6 — Pre-Experiment Gate (for EXP-028 and all future experiments)

Before running any instrumentation or experiment:

```
Repository Integrity Gate:   [ ] PASS  [ ] FAIL
Instrumentation Commit:      [ ] VERIFIED  [ ] NOT VERIFIED
Build Source Commit:         [ ] VERIFIED  [ ] NOT VERIFIED
```

### Definitions

- **Repository Integrity Gate: PASS** — `git ls-remote origin` confirms the
  expected commit is on the expected remote branch.

- **Instrumentation Commit: VERIFIED** — The commit containing the
  instrumentation patches is confirmed present on the remote via
  `git ls-remote origin`.

- **Build Source Commit: VERIFIED** — The commit that will be built matches
  the instrumentation commit on the remote. (Prevents building from a
  stale local checkout.)

**If ANY of these is not PASS/VERIFIED, the experiment MUST NOT proceed.**

---

## Step 7 — Output Language Check

Confirm all outputs are in English:

```
Reports:                    [ ] English
Logs:                       [ ] English
Commit messages:            [ ] English
Technical summaries:        [ ] English
Documentation (docs/*.md):  [ ] English
```

Conversation with the user may remain Persian.

---

## Final Sign-Off

```
Date:           ____________
Agent:          ____________
Checklist run:  ____________

All checks passed:  [ ] YES  [ ] NO

If NO, do NOT proceed with the planned operation. Report the failure to
the user with the specific check that failed and the raw command output
that proves the failure.
```

---

## Quick Reference

| Rule | What it prevents | Key command |
|------|------------------|-------------|
| Rule 1 | False "push succeeded" claims | `git ls-remote origin` |
| Rule 2 | Incomplete branch state reporting | `git branch -vv` + `git ls-remote origin` |
| Rule 3 | Automatic merges without approval | (STOP if master != main) |
| Rule 4 | Single-source-of-truth failures | `git ls-remote` + GitHub API |

---

## Acceptance

This checklist is accepted when:

1. ✅ The agent has run all Step 1 commands
2. ✅ All Step 2 fields are filled in
3. ✅ Step 3 push verification is checked (if applicable)
4. ✅ Step 4 branch divergence is checked (if applicable)
5. ✅ Step 5 independent verification is checked (for important commits)
6. ✅ Step 6 pre-experiment gate is all PASS/VERIFIED (before any EXP)
7. ✅ Step 7 language check is all English
8. ✅ Final sign-off is completed
