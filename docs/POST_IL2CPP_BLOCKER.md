# POST-IL2CPP BLOCKER — SharpEmuT24

**Last updated:** EXP-201 (2026-08-13)
**Status:** IL2CPP GC semaphore deadlock — thread handle mismatch prevents exception delivery

---

## Blocker Summary

After IL2CPP bootstrap succeeds (EXP-198), the game reaches the IL2CPP GC stop-the-world phase. The GC thread calls `sceKernelRaiseException` to interrupt a target thread, but the exception is never delivered because the target thread handle doesn't match any registered thread.

### Call Chain

```
IL2CPP GC thread (handle=0x7FB61C699D00, entry=0x804F88AA0)
  ↓
sceKernelRaiseException(target=0x7FB61CD7EC30, type=0x1E) at RIP 0x804FC1635
  ↓
HLE: TryRaiseGuestException(target=0x7FB61CD7EC30, handler=0x809A4F210)
  ↓
Look up 0x7FB61CD7EC30 in _guestThreads → NOT FOUND
  ↓
Look up 0x7FB61CD7EC30 in _externalGuestThreads → NOT FOUND
  ↓
Queue in _pendingGuestExceptions[0x7FB61CD7EC30]
  ↓
Return true (success) — but exception is never consumed
  ↓
GC thread blocks on sceKernelWaitSema(0x83)
  ↓
All 14 threads deadlock → stall watchdog (exit code 4)
```

### Why the Handle Doesn't Match

1. `KernelPthreadState.CreateThreadHandle()` allocates a host heap pointer via `Marshal.AllocHGlobal`
2. This pointer is returned to the guest as the thread ID
3. The main EBOOT thread calls `scePthreadSelf()` which calls `GetCurrentThreadHandle()`
4. `GetCurrentThreadHandle()` checks `GuestThreadExecution.CurrentGuestThreadHandle` — if 0, calls `EnsureCurrentThreadRegistered()` which allocates a NEW handle
5. The main thread's handle (from `EnsureCurrentThreadRegistered`) is different from what `TryStartThread` registered for worker threads
6. The GC thread obtains the main thread's handle (via `scePthreadSelf` or similar) and passes it to `sceKernelRaiseException`
7. `TryRaiseGuestException` can't find this handle because the main thread was never registered in `_guestThreads` or `_externalGuestThreads`

### Evidence

| Evidence | Value |
|----------|-------|
| `sceKernelRaiseException` called | YES (Import#83236) |
| Target handle | `0x00007FB61CD7EC30` |
| Scheduled thread handles | 14 handles, none match `0x7FB61CD7EC30` |
| `guest_exception.queued` | 1 entry |
| `guest_exception.delivery_enter` | 0 entries |
| `guest_exception.safe_point_enter` | 0 entries |
| GC thread state | Blocked on `sceKernelWaitSema(0x83)` |
| Worker thread state | All 13 blocked on `sceKernelWaitSema` |
| GPU pipeline counters | All 0 |
| Exit code | 4 (stall watchdog) |

### Fix Direction (EXP-202)

Option A: Register the main thread in `_externalGuestThreads` when `EnsureCurrentThreadRegistered()` is called
Option B: Make `TryRaiseGuestException` also check `KernelPthreadState.Threads` for the handle
Option C: Make `DeliverPendingGuestExceptionAtSafePoint` match by `KernelPthreadState` handle, not just `CurrentGuestThreadHandle`

---

## Key Addresses

| Address | Purpose |
|---------|---------|
| `0x804F88AA0` | IL2CPP GC thread entry (PRX) |
| `0x804FC1635` | `sceKernelRaiseException` caller RIP (PRX) |
| `0x809A4F210` | Installed exception handler (PS5Util.prx) |
| `0x809A4F1F3` | `sceKernelInstallExceptionHandler` caller RIP (PS5Util.prx) |
| Semaphore `0x83` | GC acknowledgment semaphore |
| `0x7FB61CD7EC30` | Target thread handle (not in registry) |
| `0x7FB61C699D00` | GC thread handle |

## Key Source Files

| File | Function | Line |
|------|----------|------|
| `KernelExceptionCompatExports.cs` | `RaiseException` (HLE) | 67-110 |
| `KernelExceptionCompatExports.cs` | `InstallExceptionHandler` (HLE) | 16-55 |
| `DirectExecutionBackend.cs` | `TryRaiseGuestException` | 3799 |
| `DirectExecutionBackend.cs` | `DeliverPendingGuestExceptionAtSafePoint` | 4184 |
| `KernelPthreadState.cs` | `CreateThreadHandle` | 51 |
| `KernelPthreadState.cs` | `GetCurrentThreadHandle` | 27 |
| `KernelPthreadState.cs` | `EnsureCurrentThreadRegistered` | 62 |
| `KernelPthreadState.cs` | `AllocateThreadHandle` | 75 |
| `KernelExports.cs` | `PthreadCreateCore` | 200 |
