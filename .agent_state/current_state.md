# Current State — SharpEmuT24 Investigation

**Last updated:** 2026-08-04 (after AGENT_MASTER_RULES.md created)
**Latest commit:** `1eaabb4` (EXP-138-results.md)
**Latest EXP:** EXP-138 (TryCallGuestFunction RAX propagation fix — APPLIED, awaiting build + runtime validation)

**⚠️ READ FIRST:** `docs/AGENT_MASTER_RULES.md` — the single permanent file every agent MUST read at session start.

---

## Active Fix

**EXP-138:** `TryCallGuestFunction` return-value propagation bug
- **Status:** Patch applied to source, committed to GitHub (commit `9cef960`)
- **Files changed:** `DirectExecutionBackend.cs` (5 changes), `DirectExecutionBackend.NativeWorker.cs` (1 change)
- **What it fixes:** Root cause of EXP-026/137 "232 NULL returns" — every nested guest callback returned 0 because inner `CpuContext.Rax` was never written back after thunk execution
- **What's pending:** Build + Dreaming Sarah regression + Arise regression + Yatzi validation (cannot do in sandbox — no dotnet SDK)
- **Risk:** Highest blast radius fix in project — touches every guest entry, every nested callback, every continuation resume

---

## Current Root Cause Chain (CPU Backend layer)

```
CPU Backend
    |
    |  ❌ EXP-137 (root cause identified)
    |  TryCallGuestFunction return propagation
    |  context.Rax never written back after thunk
    |
    |  ✅ EXP-138 (patch applied, awaiting validation)
    |  CallNativeEntry int → ulong
    |  context.Rax = nativeReturn after thunk
    |
Guest Callback Return
    |
Resolver / IL2CPP
    |
    |  ❓ EXP-139 (gated on EXP-138)
    |  arch_init_gc returns NOT_FOUND
    |  May be downstream of EXP-138 or independent
    |
GC Init
    |
    |  ❓ EXP-140 (gated on EXP-138)
    |  Unity Job System icalls missing
    |  Schedule_Injected, ScheduleBatchedJobs, ResetJobWorkerCount
    |
Job Bootstrap
    |
    |  ❓ EXP-141 (gated on EXP-138)
    |  Semaphore 0x84 (ResumeSemaphore) never signaled
    |  Producer inc [r14+0x90] exists but unreachable
    |
Semaphore
    |
Worker Threads
    |
    |  ❓ EXP-144 (gated on bootstrap fix)
    |  VideoOut / equeue / GPU / AGC
    |  sceKernelWaitEqueue has known bug
    |
VideoOut
    |
Frame Rendering
```

---

## Items Already Closed (do not re-investigate)

- ✅ CPU instruction correctness (EXP-027: 768/768 fuzz PASS)
- ✅ BST Resolver Algorithm (EXP-026: 239 nodes, 0 violations, RB tree valid)
- ✅ Synthetic Resolver (EXP-028: 239/239 symbol resolve)
- ✅ FAST_PATH hypothesis (EXP-128/134: REJECTED)
- ✅ init_array / RELA (EXP-132: 50,450 relocations applied successfully)
- ✅ 0x1cfccb0 pointer theory (EXP-133: relocations applied to guest memory)
- ✅ Vblank/event hypothesis (EXP-126: no sceVideoOutAddVblankEvent in either binary)
- ✅ Producer at 0x801028d80 (EXP-133: unreachable dead code)
- ✅ HLE semaphore ignores init count (EXP-135: HLE correctly honors init)
- ✅ ABI mismatch in semaphore exports (EXP-137 Phase 3A: all match Sony ABI)
- ✅ Worker scheduling bug (EXP-137 Phase 3B: all 14 workers created+started+blocked)
- ✅ Constructor execution (EXP-137 Phase 6-D overturned EXP-055: PRX module_start IS executed, returns 0)
- ✅ PRX init_array missing (EXP-137 Phase 6-C: PRXs use DT_INIT, all return 0)

---

## Pending Validation (Cannot Do In Sandbox)

- ⏸ Build SharpEmu with EXP-138 patch (needs dotnet SDK)
- ⏸ Dreaming Sarah Golden Test regression (needs build)
- ⏸ Arise regression (needs build)
- ⏸ Yatzi FAST_PATH=0 validation (needs build + regression pass)
- ⏸ RAX propagation trace (needs runtime)
- ⏸ Resolver NULL count comparison (needs runtime)
- ⏸ Semaphore 0x81 lifecycle post-fix (needs runtime)
- ⏸ AGC/VideoOut counters post-fix (needs runtime)

---

## Maintainer Next Action

1. `git pull origin main`
2. `dotnet build -c Release`
3. Run Dreaming Sarah Golden Test — verify no regression (frame count ≥138, colors ≥167)
4. Run Arise — verify no regression (no new GPU faults, no new unresolved NIDs)
5. If both pass → run Yatzi with FAST_PATH=0
6. Collect evidence per EXP-138-results.md template
7. Create `exp-reports/EXP-138-results.md` with PASS/FAIL/PARTIAL verdict

If Dreaming Sarah or Arise regresses → REVERT commit `9cef960` immediately.
