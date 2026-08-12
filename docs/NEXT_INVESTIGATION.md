# NEXT INVESTIGATION — SharpEmuT24

**Last updated:** EXP-200 (2026-08-13)
**Target:** Break the IL2CPP GC semaphore deadlock and reach first GPU initialization

---

## Current Blocker

### IL2CPP GC Stop-the-World Deadlock

After IL2CPP bootstrap (EXP-198 fix), the game reaches the point where:
1. Unity worker threads (13 AssetGarbageCollectorHelper) are scheduled
2. IL2CPP GC thread (entry `0x804F88AA0` in PRX) starts
3. GC attempts to stop all worker threads via `sceKernelRaiseException`
4. `sceKernelRaiseException` (NID `il03nluKfMk`) HLE stub calls `scheduler.TryRaiseGuestException()`
5. **`TryRaiseGuestException` does not actually interrupt the target thread**
6. Worker threads never run their exception handlers → never acknowledge the GC
7. GC thread blocks on semaphore `0x83` (waiting for acknowledgments)
8. Worker threads block on their own semaphores (waiting for GC to complete)
9. **Result: Classic deadlock → stall watchdog triggers after 20s**

### Evidence

| Metric | Value |
|--------|-------|
| Exit code | 4 (stall watchdog) |
| Threads blocked | 14 (all on `sceKernelWaitSema`) |
| GPU pipeline counters | All 0 (no rendering attempted) |
| `sceKernelRaiseException` calls | 0 in EXP-199 run (7 in EXP-198 verbose run) |
| IL2CPP GC thread | Blocked on semaphore 0x83 |
| Prosper warning | "A stubbed RaiseException left every thread un-acked -> deadlock" |

---

## Next Experiment: EXP-201

### Goal

Implement proper async guest exception delivery in `sceKernelRaiseException` so the IL2CPP GC stop-the-world mechanism works.

### Approach

1. **Study Prosper's implementation** (`hle_kernel.cpp:3072-3198`):
   - How it uses targeted POSIX signals (SIGUSR1) on Linux
   - How the signal handler saves guest register state
   - How it redirects the guest's RIP to the installed exception handler
   - How it restores state after the handler returns

2. **Study SharpEmu's `TryRaiseGuestException`**:
   - Find the implementation in `GuestThreadExecution` or `DirectExecutionBackend`
   - Determine what it currently does (likely returns error or queues without delivery)
   - Identify the minimal change needed to actually interrupt the target thread

3. **Implement targeted POSIX signal delivery**:
   - Use `pthread_kill(target_thread, SIGUSR1)` to interrupt the target
   - Install a SIGUSR1 handler that saves the guest context
   - Redirect the guest's RIP to the installed exception handler address
   - After the handler returns (via `siglongjmp` or similar), restore execution

4. **Handle the `NOT a static __thread` quirk**:
   - Prosper warns (`hle_kernel.cpp:3167-3169`): guest threads run under a GUEST `%fs`, so host `thread_local` resolves into the GUEST TLS block
   - The exception delivery buffer must NOT use `thread_local` — use a per-thread struct indexed by thread handle instead

### Success Criteria

1. `sceKernelRaiseException` calls succeed (no `ORBIS_GEN2_ERROR_BUSY`)
2. Worker threads acknowledge the GC (semaphore `0x83` gets signaled)
3. The deadlock is broken
4. The game progresses past the GC initialization phase
5. GPU/VideoOut initialization is attempted (pipeline counters > 0)

### Key Files to Modify

| File | Purpose |
|------|---------|
| `src/SharpEmu.Libs/Kernel/KernelExceptionCompatExports.cs` | `sceKernelRaiseException` HLE stub |
| `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs` or `GuestThreadExecution.cs` | `TryRaiseGuestException` implementation |
| `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.PosixSignals.cs` | POSIX signal handling |

### Key Addresses

| Address | Purpose |
|---------|---------|
| `0x804F88AA0` | IL2CPP GC thread entry (in PRX) |
| Semaphore `0x83` | GC acknowledgment semaphore (GC thread waits on this) |
| NID `il03nluKfMk` | `sceKernelRaiseException` |
| NID `WkwEd3N7w0Y` | `sceKernelInstallExceptionHandler` (installs the handler) |

### Prosper Reference

```
// Prosper hle_kernel.cpp:3072-3198
// ---- Async exception delivery = the IL2CPP GC's stop-the-world thread suspension ----
// The runtime installs a handler (sceKernelInstallExceptionHandler) for exception type 0x1e,
// then to stop the world it calls sceKernelRaiseException(thread, 0x1e) on each thread. On
// real hardware that asynchronously interrupts the target thread and runs its handler ON that
// thread; the handler captures the thread's registers (for GC root scanning) and blocks until
// resumed. POSIX hosts use a targeted signal. Windows suspends the target, redirects its CONTEXT
// through a small aligned thunk, and restores the interrupted CONTEXT after the guest handler
// returns. Both paths synthesize the same FreeBSD amd64 mcontext and run the real guest handler
// on the target thread. A stubbed RaiseException left every thread un-acked -> deadlock.
```

### Important Notes

- SharpEmu uses **direct execution** (guest code runs natively on host CPU)
- Interrupting a guest thread means interrupting the host thread that's running it
- The signal handler must distinguish between "guest signal" and "host signal"
- The guest's `%fs` (TLS base) must be preserved during the exception handler
- After the handler returns, the guest must resume exactly where it was interrupted

---

## After EXP-201 (If Successful)

Once the GC deadlock is broken, the next blockers will likely be:

1. **GPU/AGC initialization** — The game will attempt to initialize the PS5 graphics pipeline (sceAgcInit, sceAgcCreateShader, etc.)
2. **VideoOut** — VideoOutOpen, VideoOutRegisterBuffers, VideoOutSubmitFlip
3. **Shader compilation** — The game's shaders need to be compiled (SharpEmu has a shader compiler)
4. **First frame** — The first valid draw command submission and framebuffer present

Each of these will need investigation when reached.
