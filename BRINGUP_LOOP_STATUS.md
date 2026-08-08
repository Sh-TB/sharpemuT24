# Bring-up Loop Status (Permanent — Never Delete)

## Current Iteration

### Dreaming Sarah
- Status: ✅ COMPLETE (Golden Test)
- First Frame: YES (3840x2160, guest frame)
- Progress: 100%
- Blocker: None

### Arise
- Status: ✅ FIRST FRAME
- First Frame: YES (3840x2160, splash screen)
- Progress: 85%
- Blocker: Missing game data files (bigfile.bfdb)
- Next: Asset loading pipeline

### Harvest Days
- Status: 🟡 RUNNING
- First Frame: NO
- Progress: 60%
- Imports: ~948
- NULL recoveries: 15
- Blocker: IL2CPP static init loop
- Next: Real IL2CPP runtime or _Execute_once callback execution

### New Game
- Status: 🟡 RUNNING
- First Frame: NO
- Progress: 60%
- NULL recoveries: 1005
- Blocker: IL2CPP static init loop
- Next: Same as Harvest Days

## Experiment History

| Exp | Game | Change | Before | After | Result |
|-----|------|--------|--------|-------|--------|
| 1 | Arise | Unmapped memory recovery | Crash #2000 | #114612 | Keep |
| 2 | Arise | SHARPEMU_APP0_DIR | No VideoOut | VideoOut | Keep |
| 3 | Arise | Save data path fix | No frame | First Frame | Keep |
| 4 | Harvest | IL2CPP fake heap | Crash #659 | #16904 | Keep |
| 5 | Harvest | NULL execute recovery | Crash #8825 | #16904 | Keep |
| 6 | All | Sema fast path | — | — | Keep |
| 7 | All | PR #542 _Execute_once | — | — | Keep (no regression) |

## Milestone Tags
- `milestone/2-games-first-frame` — 2/4 games render first frame
- `milestone/pr542-applied` — PR #542 compatibility fixes applied
- `backup/arise-first-frame-working` — Arise first frame milestone
- `backup/before-next-experiment` — Before any new changes
