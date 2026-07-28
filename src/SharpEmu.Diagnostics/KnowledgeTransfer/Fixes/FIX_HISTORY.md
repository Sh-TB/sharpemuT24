# Fix History

## EXP-001: IL2CPP Fake Heap
- Date: 2026-07-22
- Games: Harvest Days, New Game
- Commit: 92bf7e9
- Before: Crash at import #659 (NULL vtable dispatch)
- After: Import #16904 (no crash)
- Files: DirectExecutionBackend.Imports.cs
- Result: Keep

## EXP-002: NULL Execute Fault Recovery
- Date: 2026-07-22
- Games: Harvest Days, New Game
- Commit: 92bf7e9
- Before: Crash at RIP=0
- After: 15-1005 faults recovered
- Files: DirectExecutionBackend.Exceptions.cs
- Result: Keep

## EXP-003: Unmapped Memory Recovery
- Date: 2026-07-22
- Games: Arise
- Commit: 92bf7e9
- Before: Crash at import #2000
- After: Import #114612, first frame
- Files: DirectExecutionBackend.Exceptions.cs
- Result: Keep

## EXP-004: SHARPEMU_APP0_DIR
- Date: 2026-07-22
- Games: Arise
- Commit: 8a5ef94
- Before: Game can't find files
- After: Game reaches VideoOut
- Files: scripts/game-loop.sh
- Result: Keep

## EXP-005: Save Data Path Fix
- Date: 2026-07-22
- Games: Arise
- Commit: 8a5ef94
- Before: No first frame
- After: First frame (3840x2160 splash)
- Files: scripts/game-loop.sh
- Result: Keep

## EXP-006: PR #542 Compatibility
- Date: 2026-07-22
- Games: All
- Commit: 26c882b
- Before: Missing NIDs (YaHc3GS7y7g, SreZybSRWpU, DiGVep5yB5w, etc.)
- After: NIDs resolved, no regression
- Files: MessengerCompatExports.cs, CxxAbiExports.cs, LibcStdioExports.cs
- Result: Keep

## EXP-007: Sema Fast Path
- Date: 2026-07-22
- Games: Harvest Days, New Game
- Commit: 5476082
- Before: Game stuck in semaphore wait
- After: Game proceeds (still stuck in IL2CPP init)
- Files: KernelSemaphoreCompatExports.cs
- Result: Keep

## EXP-008: C11SyncExports Access Fix
- Date: 2026-07-22
- Games: Harvest Days, New Game
- Commit: 60b18f0
- Before: _Mtx_init, _Cnd_init unresolved (build didn't include them)
- After: _Mtx_init, _Cnd_init RESOLVED. Harvest Days NIDs: 3→1, New Game: 5→2
- Files: KernelPthreadCompatExports.cs (private→internal), MessengerCompatExports.cs (using)
- Result: Keep
