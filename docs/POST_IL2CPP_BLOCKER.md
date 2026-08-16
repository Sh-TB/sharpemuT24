# POST-IL2CPP BLOCKER — SharpEmuT24

**Last updated:** EXP-202 (2026-08-13)
**Status:** IL2CPP GC semaphore deadlock — `_currentExternalGuestThreadHandle` overwrite

---

## Root Cause (PROVEN by EXP-202)

`_currentExternalGuestThreadHandle` is a **single static field** in `DirectExecutionBackend.cs` that gets overwritten every time ANY thread calls `RegisterGuestThreadContext` (which happens via `scePthreadSelf()`).

When the GC thread calls `scePthreadSelf()`, it overwrites `_currentExternalGuestThreadHandle` with the GC thread's handle. When the main EBOOT thread later hits an HLE safe point, `DeliverPendingGuestExceptionAtSafePoint` uses `_currentExternalGuestThreadHandle` (because `CurrentGuestThreadHandle=0` for the main thread), which now contains the GC thread's handle instead of the main thread's handle.

The pending exception for the main thread's handle is never consumed → handler never runs → GC acknowledgment semaphore (0x83) never signaled → deadlock.

## Fix Direction (EXP-203)

Change `_currentExternalGuestThreadHandle` from `static ulong` to `[ThreadStatic]` or per-host-thread dictionary.

## Key Source Locations

| File | Line | Function |
|------|------|----------|
| `DirectExecutionBackend.cs` | 2958 | `_currentExternalGuestThreadHandle = threadHandle` (overwrite point) |
| `DirectExecutionBackend.cs` | 4188-4192 | `DeliverPendingGuestExceptionAtSafePoint` handle lookup |
| `KernelPthreadCompatExports.cs` | 100 | `scePthreadSelf()` calls `RegisterGuestThreadContext` |
| `KernelPthreadState.cs` | 75-84 | `AllocateThreadHandle` — allocates host heap pointer as handle |
