# Known Facts — SharpEmuT24 Investigation

**Last updated:** 2026-08-04 (after EXP-138 patch applied)

---

## CONFIRMED Facts (proven, runtime-verified or static-verified)

### CPU Backend
- Direct execution model: guest x86_64 runs natively on host CPU via VirtualAlloc PAGE_EXECUTE_READWRITE. Atomic operations are correct by construction (EXP-114).
- CPU instruction correctness: 768/768 fuzz PASS for cmovns/test/lea/branch logic (EXP-027, CLOSED).
- BST Resolver Algorithm: 239 nodes, 0 violations, RB tree valid, inverted tree correct (EXP-026, CLOSED).
- Synthetic Resolver: 239/239 symbol resolve (EXP-028, CLOSED).

### Loader / RELA
- RELA table loaded successfully from guest memory at 0x801F435F0 (EXP-132, CONFIRMED).
- 50,450 R_X86_64_RELATIVE relocations processed without error (EXP-132, CONFIRMED).
- Relocations ARE applied to guest memory, NOT to file (EXP-133 confirmed EXP-132's correction).
- 8 PRX modules load successfully.
- PRX module_start (DT_INIT) IS executed for all 3 PRXs (libc, libSceNpCppWebApi, Il2cppUserAssemblies) — all return 0 (EXP-137 Phase 6-D, OVERTURNS EXP-055).

### IL2CPP
- Real Yatzi dump present: eboot.bin (32.7MB), Il2cppUserAssemblies.prx (74.7MB), global-metadata.dat (10.7MB, magic 0xFAB11BAF) (EXP-060/061, CONFIRMED).
- Old eboot (7.7MB) was Dreaming Sarah, not Yatzi — all EXP-035..058 findings INVALID (EXP-061, CONFIRMED).
- il2cpp_init HLE'd to return 0 at DirectExecutionBackend.Imports.cs:2571 — real init callback at eboot.bin 0x8013FB0B0 never runs (EXP-026, CONFIRMED).
- IL2CPP BST initialization code DID execute during Il2cppUserAssemblies.prx module_start (FLAG-WATCH trace at exp118_run.log:932) (EXP-137 Phase 6-D, CONFIRMED).

### Semaphore / Threading
- Semaphore 0x81 (Baselib_SystemSemaphore) created with init=0, max=2147483647 (EXP-137 Phase 2B, CONFIRMED).
- Semaphore 0x81 is NEVER signaled across all 3 logs (exp118, testA, testB) (EXP-137 Phase 2B, CONFIRMED).
- 14 worker threads (13 AssetGarbageCollectorHelper + 1 GC scavenger) created, started, reached entry, all blocked on WaitSema (EXP-137 Phase 3B, CONFIRMED).
- Semaphore ABI correct: CreateSema/WaitSema/SignalSema all match Sony ABI exactly (EXP-137 Phase 3A, CONFIRMED).
- HLE honors guest init count correctly (EXP-135, CONFIRMED).

### Unity Job System
- SharpEmu implements ZERO Unity Job System icalls (Schedule_Injected, ScheduleBatchedJobs, ResetJobWorkerCount, etc.) (EXP-137 Phase 4, CONFIRMED).
- il2cpp_resolve_icall HLE stub at line 2569 is DEAD CODE (TryResolveIl2CppApiAddress is private and never called) (EXP-137 Phase 4, CONFIRMED).
- 60+ Unity Job System icalls identified in Yatzi eboot.bin strings (EXP-137 Phase 2A, CONFIRMED).

### Producer / Worker Queue
- Producer `inc dword [r14+0x90]` EXISTS at eboot.bin @ 0x159d52 in func@0x159cd0 (EXP-137 Phase 2C, OVERTURNS EXP-135).
- Consumer `lock xadd dword [r14+0x90], eax` (eax=-1) at Il2cppUserAssemblies.prx @ 0x299978 (dispatch loop).
- Atomicity mismatch: producer uses non-atomic inc, consumer uses atomic lock xadd.
- 458/459 SignalSema callers in eboot never executed at runtime (EXP-134, CONFIRMED).

### NID Resolution
- NID `XAKDgxcra6k` = `arch_init_gc` (IL2CPP GC architecture initializer) — verified via SharpEmu's Ps5Nid.cs SHA1+salt algorithm (EXP-136, CONFIRMED).
- NID `J3edELK4FvM` = `arch_raise_user` (IL2CPP abort mechanism) — same verification (EXP-136, CONFIRMED).
- NID `1D0H2KNjshE` = `powf` (math power function) — called 60,343 times in 2s (EXP-136, CONFIRMED).
- NID `hsi9drzHR2k` = `log2f` (math log2 function) — called 19,968 times in 2s (EXP-136, CONFIRMED).
- arch_init_gc returns 0x80020002 (NOT_FOUND) at exp118_run.log:8315 (EXP-136, CONFIRMED).
- arch_init_gc is imported by both Il2cppUserAssemblies.prx AND PS5Util.prx (EXP-136, CONFIRMED).
- SharpEmu has ZERO implementation for arch_init_gc anywhere in src/ (EXP-136, CONFIRMED).

### Runtime Timeline (from exp118_run.log)
- Line 8313: sceKernelAllocateDirectMemory called
- Line 8315: *** arch_init_gc called → returns NOT_FOUND ***
- Line 8317: GC scavenger thread scheduled at 0x804F88AA0
- Line 8319: *** arch_raise_user called — IL2CPP abort mechanism triggered ***
- Line 8320+: stall, deadlock
- Line 8559: Stall detected — main thread blocked on WaitSema(0x81), 13 workers on 0x5C-0x74, GC on 0x83

---

## REJECTED Hypotheses (do NOT re-test)

| Hypothesis | Rejected by | Evidence |
|------------|-------------|----------|
| Vblank/event-flag driven dispatch | EXP-126 | No sceVideoOutAddVblankEvent, no sceKernelWaitEventFlag in either binary |
| RELA relocation failure | EXP-131 → EXP-132 | 50,450 relocations applied successfully |
| Producer at 0x801028d80 is the real producer | EXP-133 | Zero direct callers, zero LEA refs, unreachable dead code |
| Dispatch loop reached via corrupted function pointer | EXP-134 | Direct CALL instruction at 0x804F4560E |
| HLE semaphore ignores guest init count | EXP-135 | HLE reads init from guest registers correctly |
| SHARPEMU_SEMA_FAST_PATH=1 is a fix | EXP-119 | Crashes at RIP=0 (NULL call), pipeline counters still zero |
| Extra IL2CPP thread is a job dispatcher | EXP-123 | It's the GC scavenger thread |
| Worker task function pointer uninitialized by mistake | EXP-121 | Deliberately zeroed at creation (0x800a9fcae) |
| ABI mismatch in semaphore exports | EXP-137 Phase 3A | All match Sony ABI exactly |
| Worker scheduling bug | EXP-137 Phase 3B | All 14 workers created+started+blocked, not scheduling issue |
| PRX init_array missing | EXP-137 Phase 6-C | PRXs use DT_INIT (module_start), all return 0 |
| Constructor execution broken | EXP-137 Phase 6-D | All 3 PRX module_starts return 0, real IL2CPP code ran |
| sceKernelGetCompiledSdkVersion returning 0 | EXP-136 H7 | Yatzi doesn't import this NID |
| sceKernelSyncOnAddressWait broken | EXP-136 H7 | Yatzi doesn't import this NID |
| _Cnd_init stub breaks Unity Baselib | EXP-136 H4 | Yatzi uses POSIX pthread_cond_* instead |
| powf/log2f unimplemented cause deadlock | CHECKPOINT §17 | Called 80K+ times in 2s, loop is finite, REFUTED |
| [r14+0x90] never incremented by any binary code | EXP-137 Phase 2C | Producer exists at eboot.bin @ 0x159d52 (OVERTURNS EXP-135) |
| 0x1cfccb0 pointer theory | EXP-133 | Relocations applied to guest memory, file value 0x0 is pre-relocation normal |

---

## UNKNOWN (open questions, awaiting runtime validation post-EXP-138)

1. Is the producer `inc [r14+0x90]` at eboot.bin @ 0x159d52 reachable from main thread bootstrap after EXP-138 fix?
2. Does fixing TryCallGuestFunction RAX propagation cascade-fix IL2CPP API resolution?
3. Does arch_init_gc still return NOT_FOUND after EXP-138 fix, or was it a downstream symptom?
4. Are Unity Job System icalls registered by Yatzi's own init code, or do they need SharpEmu HLE?
5. Is the atomicity mismatch (non-atomic inc producer vs atomic lock xadd consumer) a memory-ordering issue under SharpEmu?
6. What should signal semaphore 0x84 (ResumeSemaphore) to wake Thread-X?

---

## EXP-138 Patch (Applied, Commit 9cef960)

**Root cause fix for EXP-026/137 "232 NULL returns":**

1. `CallNativeEntry`: `int` → `ulong` (preserve 64-bit function pointers)
2. `ExecuteGuestThreadEntry`: `context[CpuRegister.Rax] = nativeReturn` after thunk
3. `ExecuteGuestContinuationEntry`: same Rax write-back
4. Entry path (`num6`): `int` → `ulong`, `-1` → `ulong.MaxValue`
5. `NativeWorker.cs` `RunGuestEntryStub`: `int` → `ulong` (dead code, type consistency)

**Status:** Applied to source, committed to GitHub. Build + runtime validation PENDING (no dotnet SDK in sandbox).
