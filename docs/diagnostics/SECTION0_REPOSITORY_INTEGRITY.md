# SECTION 0 — Repository Integrity Gate (MANDATORY POLICY)

**Owner:** SharpEmuT24 Debug Supervisor
**Status:** Permanent policy — applies to all agents, coders, and automated reports
**Effective:** 2026-07-29
**Supersedes:** All previous informal repository-state claims

---

## Purpose

Prevent future false reports about Git state, commits, branches, and pushes.

No agent, coder, or automated report is allowed to claim repository state
based on memory, previous summaries, or local assumptions.

All repository claims MUST be verified using raw Git evidence.

---

## Mandatory Pre-Flight Before Any Git Operation

Before performing any of the following:

- merge
- push
- branch decision
- release preparation
- claiming a commit exists

The agent MUST run ALL of these commands and capture their output:

```bash
git remote -v
git branch -vv
git branch -a
git log --oneline --decorate -5
git ls-remote origin
```

The output of these commands is the ONLY acceptable evidence for any
repository-state claim. Summaries, memory, and assumptions are NOT evidence.

---

## Verification Rules

### Rule 1 — Push Verification

Never report "Push succeeded" unless:

```bash
git ls-remote origin
```

shows the expected commit hash on the expected remote branch.

**Forbidden phrasing without ls-remote evidence:**
- "Push succeeded"
- "Commit is on the remote"
- "Changes are now on GitHub"
- "Successfully pushed"

**Required phrasing when verified:**
- "Push verified: `git ls-remote origin` shows commit `<hash>` at `refs/heads/<branch>`"

### Rule 2 — Branch Verification

Always report ALL FOUR of these fields when discussing repository state:

```
Current local branch:        <name>
Remote tracking branch:      <name> -> <hash>
Default GitHub branch:       <name> -> <hash>
EXP commit location:         <on main / on master only / on neither>
```

**Example (correct):**
```
Current local branch:        master
Remote tracking branch:      origin/master -> 08c0735
Default GitHub branch:       main -> 3e3d8081
EXP commit location:         on master only (NOT on default branch)
```

**Example (forbidden — incomplete):**
```
Branch: master
Push: succeeded
```

### Rule 3 — No Automatic Merge

If `master != main` (i.e., the EXP commit is on `master` but not on the
default branch `main`):

**STOP.**

Ask the user for an explicit decision:

- **Option A:** Keep EXP branch isolated on `master`. No action.
- **Option B:** Merge `master` into `main`. Requires explicit approval.

Never merge automatically. Never force push. Never rewrite history.

### Rule 4 — Independent Verification

For important commits (release tags, EXP milestones, public claims), use
TWO independent verification methods:

**Method 1:** `git ls-remote origin`
```bash
git ls-remote origin refs/heads/<branch>
```

**Method 2:** GitHub API
```bash
curl -s "https://api.github.com/repos/Sh-TB/sharpemuT24/commits/<hash>/branches-where-head"
```

Only after BOTH methods agree, mark the claim as:

```
VERIFIED (PROVEN)
```

If only one method is available (e.g., rate-limited API), mark as:

```
VERIFIED (single method — git ls-remote)
```

Never mark as PROVEN without at least `git ls-remote origin` evidence.

---

## Documentation Requirement

Every repository-state claim must be backed by a file at:

```
docs/diagnostics/SECTION0_REPOSITORY_INTEGRITY.md
```

(or a dated variant like `SECTION0_REPOSITORY_INTEGRITY_<YYYYMMDD>.md`)

Containing:

1. **Remote URL** (from `git remote -v`)
2. **Local branch** (from `git branch -vv`)
3. **Remote branches** (from `git branch -a` + `git ls-remote origin`)
4. **Commit hashes** (local HEAD, origin/main, origin/master)
5. **Verification commands** (the actual commands run, with output)
6. **Final verdict** (PROVEN / NOT PROVEN / PARTIAL)

---

## Integration With EXP-028 (and all future experiments)

Before running ANY of these:

- T12/T13 boundary trace
- T5 memory read trace
- T6 branch trace
- Yatzi instrumentation
- Any experiment that depends on the repository state

The agent MUST confirm ALL THREE:

```
Repository Integrity Gate:   PASS
Instrumentation Commit:      VERIFIED
Build Source Commit:         VERIFIED
```

If ANY of these is not PASS/VERIFIED, the experiment MUST NOT proceed.

### Definitions

- **Repository Integrity Gate: PASS** — `git ls-remote origin` confirms
  the expected commit is on the expected remote branch.

- **Instrumentation Commit: VERIFIED** — The commit containing the
  instrumentation patches (e.g., `_Exp028*.cs` files) is confirmed
  present on the remote via `git ls-remote origin`.

- **Build Source Commit: VERIFIED** — The commit that will be built
  (the one the user will `dotnet build` from) is confirmed to match
  the instrumentation commit on the remote. This prevents the scenario
  where the user builds from a stale local checkout that doesn't have
  the instrumentation.

---

## Output Language Rule

From now on, ALL Coder/Agent outputs must be in English:

- Reports → English
- Logs → English
- Commit messages → English
- Technical summaries → English
- Documentation files (`*.md` in `docs/`) → English

Conversation with the user may remain Persian.

**Rationale:** English ensures the diagnostic artifacts are reviewable
by the broader SharpEmu community and don't get lost in translation
when quoted in GitHub issues or PRs.

---

## Final Rule

**Evidence first.**

Never trust:
- previous reports
- summaries
- memory
- assumptions

Trust only:
- Raw command output
- Logs
- Hashes
- Trace evidence

---

## Acceptance Criteria

This policy is accepted and in effect when:

1. This file exists at `docs/diagnostics/SECTION0_REPOSITORY_INTEGRITY.md`
2. A companion checklist exists at `docs/diagnostics/REPOSITORY_INTEGRITY_CHECKLIST.md`
3. Both files are committed to the repository
4. The worklog records the policy adoption
5. All future agent reports include the four-field branch verification (Rule 2)

---

## Change Log

| Date       | Change                          | Author                        |
|------------|---------------------------------|-------------------------------|
| 2026-07-29 | Initial policy adoption         | SharpEmuT24 Debug Supervisor  |
