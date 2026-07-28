# Fix History Log

## EXP-0001: IL2CPP Fake Heap
- Date: 2026-07-22
- Game: Harvest Days, New Game
- Change: 64KB fake heap with default vtable + fake objects + per-function stubs
- Before: Crash at import #659 (NULL vtable dispatch)
- After: Import #16904 (no crash)
- Result: Keep

## EXP-0002: NULL Execute Fault Recovery
- Date: 2026-07-22
- Game: Harvest Days, New Game
- Change: Redirect NULL calls to return-zero stub
- Before: Crash at RIP=0
- After: 15-1005 faults recovered, game continues
- Result: Keep

## EXP-0003: Unmapped Memory Recovery
- Date: 2026-07-22
- Game: Arise
- Change: Decode instruction with Iced, set dest=0 for reads, skip instruction
- Before: Crash at import #2000 (refcount array access)
- After: Import #114612, VideoOut reached, first frame rendered
- Result: Keep

## EXP-0004: SHARPEMU_APP0_DIR
- Date: 2026-07-22
- Game: Arise
- Change: Set env var to resolve /app0/ paths to host filesystem
- Before: Game can't find files
- After: Game loads save data, reaches VideoOut
- Result: Keep

## EXP-0005: Save Data Path Fix
- Date: 2026-07-22
- Game: Arise
- Change: Create save data at work/sharpemu-build/user/savedata/268435456/arise/SaveData/
- Before: No first frame
- After: First frame rendered (3840x2160 splash)
- Result: Keep

## EXP-0006: PR #542 Compatibility
- Date: 2026-07-22
- Game: All
- Change: MessengerCompatExports, _Execute_once, IL2CPP dispatch fix
- Before: Various missing NIDs
- After: No regression, better Unity compatibility
- Result: Keep

## EXP-0007: Sema Fast Path
- Date: 2026-07-22
- Game: Harvest Days, New Game
- Change: SHARPEMU_SEMA_FAST_PATH=1 bypasses semaphore waits
- Before: Game stuck in semaphore wait
- After: Game proceeds (but still stuck in IL2CPP init)
- Result: Keep
