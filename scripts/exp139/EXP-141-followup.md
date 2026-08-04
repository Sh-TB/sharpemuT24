# EXP-141 Follow-up — WaitSema(0x81) Deadlock Investigation

**Date:** 2026-08-04
**Status:** Deadlock unchanged — boot.config and memory queries are NOT the blocker

---

## Priority 1: boot.config Test

### Test
Created `/tmp/exp125_games/yatzi/Media/boot.config` with minimal Unity config:
```
player-initial-name=Player
player-initial-color=0,0,0,255
```

### Result
```
fopen: guest='/app0/Media/boot.config' host='/tmp/exp125_games/yatzi/Media/boot.config' mode='rb' -> OK handle=0x2010000000 length=58
```

boot.config now opens successfully. But:

| Metric | Before (no boot.config) | After (with boot.config) |
|--------|------------------------|--------------------------|
| sema.create | 143 | 143 |
| sema.signal | 13 | 13 |
| SignalSema(0x84) | 0 | **0** (no change) |
| SignalSema(0x81) | 0 | **0** (no change) |
| Exit code | 4 (stall) | 124 (stall) |

**VERDICT: boot.config is NOT the blocker.** The deadlock is identical with or without boot.config.

---

## Priority 2: Missing Kernel Memory APIs

### Analysis
`sceKernelVirtualQuery` and `sceKernelDirectMemoryQuery` are **already implemented** in HLE:
- `KernelVirtualQuery()` at `KernelMemoryCompatExports.cs:3273` — searches mapped regions
- `KernelDirectMemoryQuery()` at `KernelMemoryCompatExports.cs:3399` — searches direct allocations

They return `NOT_FOUND` because the guest is querying addresses that are **not in any mapped region**. This is a legitimate return value, not a missing implementation.

**VERDICT: P2 REJECTED.** These functions work correctly. The NOT_FOUND is the correct response for the queried addresses. Implementing stubs would return wrong data.

---

## Priority 3: Execution Timeline Analysis

### Complete timeline from ExecuteEntry to deadlock:

```
Line 1455: ExecuteEntry starting at 0x800000070 (eboot main entry)
Line ~2000: PRINF (Unity PRINF debug output)
Line ~2020: Import#2084: unity_mono_set_user_malloc_mutex
Line ~2080: BST-WALK (IL2CPP symbol search — 7 symbols found)
Line ~2100: More imports (sceKernelCreateSema, pthread mutex, etc.)
Line 2804: First AssetGarbageCollectorHelper worker scheduled
Line 2908: Last (13th) worker scheduled
Line 2924: Import#4861: sceKernelMkdir → PERMISSION_DENIED
Line 2930: sema.create 0x7C (Baselib_SystemSemaphore)
Line 2940: Massive scePthreadMutexLock loop (38000+ calls)
Line 2964: sema.create 0x81 (Baselib_SystemSemaphore — main thread's job queue)
Line 2966: sema.create 0x82 (Baselib_SystemSemaphore)
Line 2967: sema.create 0x83 (SuspendSemaphore — GC thread)
Line 2968: sema.create 0x84 (ResumeSemaphore — GC thread resume)
Line 2969-2978: sema.create 0x85-0x90 (more Baselib_SystemSemaphore)
Line 2980: Thread-XXX scheduled (GC scavenger, entry=0x804F88AA0)
Line 2981: sema.wait-host-block 0x81 (MAIN THREAD BLOCKS HERE)
Line 2982: sema.wait-block 0x83 (GC THREAD BLOCKS HERE)
Line 2983+: NID-COUNTS spin (stall watchdog)
```

### Key observations:

1. **Massive scePthreadMutexLock loop**: Between mkdir (line 2924) and sema 0x81 creation (line 2964), the guest calls `scePthreadMutexLock` 38000+ times. This is a tight loop doing mutex operations — likely IL2CPP type initialization or metadata processing.

2. **Semaphore creation order**: 0x81 → 0x82 → 0x83 (Suspend) → 0x84 (Resume) → 0x85-0x90. All created in immediate succession.

3. **Thread-XXX (GC scavenger) scheduled AFTER all semaphores created**: The GC thread is the last thread to be scheduled. It immediately blocks on 0x83 (SuspendSemaphore).

4. **Main thread blocks on 0x81 IMMEDIATELY after Thread-XXX is scheduled**: The main thread creates all semaphores, schedules the GC thread, then immediately calls WaitSema(0x81) and blocks.

5. **No code executes between Thread-XXX scheduling and main thread blocking**: The main thread does NOT do any work after scheduling the GC thread — it goes straight to WaitSema(0x81).

### This means:
- The main thread creates the dispatch loop semaphores (0x81-0x84)
- The main thread schedules the GC thread
- The main thread enters the dispatch loop and immediately blocks on WaitSema(0x81)
- **The main thread never submits a bootstrap job before blocking**
- The bootstrap job submission should happen BEFORE entering the dispatch loop, but it doesn't

### The missing step:
The main thread should:
1. Submit the bootstrap job (increment [r14+0x90], signal worker semaphore)
2. THEN enter the dispatch loop (WaitSema(0x81))

But the main thread goes directly from semaphore creation to WaitSema(0x81) without submitting any job.

---

## Root Cause Hypothesis

The bootstrap job submission is **missing from the initialization sequence**. The main thread:
1. Creates workers ✅
2. Creates semaphores ✅
3. Schedules GC thread ✅
4. Enters dispatch loop ✅
5. **Submits bootstrap job** ❌ ← MISSING

The bootstrap job submission likely happens in a Unity C# method that is called via `il2cpp_runtime_invoke` or similar. Since `il2cpp_resolve_icall` is direct-bridged, we cannot see if the icall resolution succeeds or fails.

**The most likely cause:** A Unity icall (like `Schedule_Injected` or `ScheduleBatchedJobs`) resolves to NULL because `il2cpp_resolve_icall` returns NULL natively. This would mean the IL2CPP runtime's icall table is not properly populated.

---

## Package Integrity

### BOOT_MANIFEST.txt
```
eboot.bin: 32697964 bytes
sce_module/libc.prx: 1334282 bytes
sce_module/libSceNpCppWebApi.prx: 7954839 bytes
Media/Modules/Il2cppUserAssemblies.prx: 74726132 bytes
Media/Modules/PS5Util.prx: 67668 bytes
Media/Metadata/global-metadata.dat: 10669264 bytes
Media/Plugins/lib_burst_generated.prx: 104736 bytes
Media/Plugins/PSNCommon.prx: 73444 bytes
Media/Plugins/PSNCore.prx: 511508 bytes
Media/Plugins/SaveData.prx: 82960 bytes
Media/boot.config: 58 bytes
```

All files loaded successfully. 8/8 PRXs loaded, 0 failures.

---

## Golden Gate Status

Dreaming Sarah: ✅ PASS (23/23/744 colors) — no regression

---

## Next Steps

1. **Trace `il2cpp_resolve_icall` natively** — need to intercept the icall resolution to see if Unity Job System icalls resolve to NULL
2. **Check if the massive mutex loop (38000+ calls) is normal** — this may be IL2CPP type initialization, or it may be a spin loop indicating a problem
3. **Check if `sceKernelMkdir` PERMISSION_DENIED affects Unity initialization** — Unity may need to create cache directories
4. **Consider adding runtime instrumentation** — breakpoint at the producer address (eboot.bin @ 0x159d52) to see if it's ever reached
