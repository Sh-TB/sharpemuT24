# SharpEmu Knowledge Transfer System v1.0

## Standard for Transferring Knowledge Between Debug Tester and Main Fork

**Goal:** Every experiment, every game, every crash, and every fix must be transferable. No knowledge should remain only in chat or in one AI's memory.

---

## Golden Rule

```
Never repeat the same experiment twice.

Before every new test:
1. Read previous Knowledge Transfer files.
2. Check known crashes.
3. Check previous fixes.
4. Continue from last checkpoint.

The emulator must learn from every game.
```

---

## Required Output File

Every tester/AI must produce exactly one file:

```
GAME_KNOWLEDGE_TRANSFER.md
```

This file follows the template below. The main fork imports knowledge from this file.

---

## Template

```markdown
# Game Knowledge Transfer Report

## 1. Metadata

- Game: [name]
- Title ID: [PPSAxxxxx]
- Version: [eboot version]
- Platform: PS5 (Gen5)
- Tester: [name/AI]
- Date: [ISO timestamp]
- Commit Hash: [git hash]
- Branch: [branch name]

## 2. Current Result

Status (check one):
- [ ] Crash
- [ ] Boot
- [ ] VideoOut
- [ ] Splash
- [ ] First Frame
- [ ] Gameplay

Progress:
```
ELF Loading        [X]%
Imports            [X]%
CRT                [X]%
IL2CPP             [X]%
Threads            [X]%
GPU                [X]%
VideoOut            [X]%
First Frame        [YES/NO]
```

## 3. Experiment History

For each experiment:
```
Experiment #:
Commit:
Change:
Reason:
Before:
After:
Result: [Progress / Regression / No change]
```

## 4. Root Cause

```
Crash address:
Register state:
Function/NID:
Reason:
```

## 5. Applied Fixes

For each fix:
```
File:
Method:
Change:
Lines changed:
```

## 6. New Knowledge

What we learned that we didn't know before.

## 7. Required Future Work

Remaining blockers and suggested next steps.

## 8. Regression Test

```
Before fix:
  Dreaming Sarah: [PASS/FAIL]
  Arise: [PASS/FAIL]
  Harvest Days: [PASS/FAIL]
  New Game: [PASS/FAIL]

After fix:
  Dreaming Sarah: [PASS/FAIL]
  Arise: [PASS/FAIL]
  Harvest Days: [PASS/FAIL]
  New Game: [PASS/FAIL]
```

## 9. Files Changed

List every file modified, with line counts.

## 10. Git Information

```
Commit: [hash]
Tag: [tag name]
Backup: [backup tag name]
```

## 11. Transfer Instructions

How to apply this to the main fork:
1. Copy changed files
2. Cherry-pick commits
3. Run tests
4. Expected result
```

---

## Knowledge Directory Structure

```
SharpEmu.Diagnostics/Knowledge/
├── Games/
│   ├── DreamingSarah.md
│   ├── Arise.md
│   ├── HarvestDays.md
│   └── NewGame.md
├── Experiments/
│   ├── EXP-0001-il2cpp-fake-heap.md
│   ├── EXP-0002-null-execute-recovery.md
│   └── ...
├── FixHistory/
│   └── fix-log.md
└── TransferTemplates/
    └── GAME_KNOWLEDGE_TRANSFER.md
```

---

## Test Loop Protocol

```
BUILD
  ↓
CHECKPOINT (git tag backup/pre-test-YYYYMMDD-HHMM)
  ↓
RUN GAME
  ↓
COLLECT LOG
  ↓
ANALYZE (find blocker, compare with previous run)
  ↓
FIND ROOT CAUSE
  ↓
SMALL FIX ONLY (one change per iteration)
  ↓
BUILD AGAIN
  ↓
REGRESSION TEST (all 4 games)
  ↓
SAVE KNOWLEDGE TRANSFER (GAME_KNOWLEDGE_TRANSFER.md)
  ↓
COMMIT + TAG
  ↓
NEXT ITERATION
```

---

## Release Rule

```
If a new change produces a meaningful improvement:
  - game reaches a new boot stage
  - new first frame rendered
  - new blocker removed
  - IL2CPP/CRT/HLE compatibility improves
  - GPU/VideoOut progress improves

Required actions:
  1. Commit all source code changes to Git
  2. Create backup tag before next experiment
  3. Publish latest source code archive
  4. Create/update GitHub Release with:
     - latest source code
     - build version
     - commit hash
     - test results
     - known blockers
     - changed components

Release naming:
  SharpEmuT24-bringup-v0.0.X-YYYY-MM-DD.tar.gz

Before publishing, verify:
  - Build succeeds
  - Dreaming Sarah regression passes
  - Arise first-frame state preserved
  - No previous working state lost

Never overwrite last known good version.
Always keep: backup/<previous-working-state>
And create: milestone/<new-progress>
```

---

## Progress Is Not Only Final Success

```
A build that moves a game from:
  Import #8,000 → Import #100,000
or:
  Crash → VideoOut → First Frame

is a milestone and should have its own tag and release notes.
```
