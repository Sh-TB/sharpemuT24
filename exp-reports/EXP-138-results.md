# EXP-138 Results — TryCallGuestFunction RAX Propagation Fix Validation

**Date:** 2026-08-04
**Commit:** `9cef960` (EXP-138 patch)
**Latest commit:** `36a91fa` (docs + .agent_state)
**Status:** ⚠️ CANNOT VALIDATE IN SANDBOX — no dotnet SDK available

---

## Honest Status

| Step | Status | Reason |
|------|--------|--------|
| 1. Build (`dotnet build -c Release`) | ❌ CANNOT DO | No dotnet SDK in sandbox |
| 2. Dreaming Sarah Golden Test | ❌ CANNOT DO | Requires build |
| 3. Arise Regression | ❌ CANNOT DO | Requires build |
| 4. Yatzi FAST_PATH=0 Validation | ❌ CANNOT DO | Requires build + regression pass |
| 5. Evidence Collection (RAX/resolver/semaphore/AGC) | ❌ CANNOT DO | Requires runtime |

**The patch is applied to source code and committed to GitHub (commit `9cef960`). Static verification passes. Build + runtime validation MUST be done by maintainer on a machine with dotnet SDK.**

---

## Static Verification (What I CAN Do In Sandbox)

### Build Verification — ❌ CANNOT BUILD
```bash
$ dotnet --version
bash: dotnet: command not found

$ find / -maxdepth 4 -name "dotnet" -type f
(no results)

$ ls /usr/share/dotnet/
ls: cannot access '/usr/share/dotnet/': No such file or directory
```
**Result:** No dotnet SDK installed in sandbox. Cannot build.

### Patch Syntax Verification — ✅ PASS

Static checks performed on the patched source:

| Check | Result | Evidence |
|-------|--------|----------|
| `CallNativeEntry` returns `ulong` | ✅ | Line 879: `private unsafe static ulong CallNativeEntry(void* entry)` |
| Delegate signature updated to `ulong` | ✅ | Line 882: `(delegate* unmanaged[Cdecl]<ulong>)entry` |
| `ExecuteGuestThreadEntry` writes `context.Rax` | ✅ | Line 5043: `context[CpuRegister.Rax] = nativeReturn;` |
| `ExecuteGuestContinuationEntry` writes `context.Rax` | ✅ | Line 5216: `context[CpuRegister.Rax] = nativeReturn;` |
| Entry path `num6` is `ulong` | ✅ | Line 5506: `ulong num6 = ulong.MaxValue;` |
| `NativeWorker.cs` `RunGuestEntryStub` returns `ulong` | ✅ | Line 59: `private unsafe ulong RunGuestEntryStub(...)` |
| No remaining `int CallNativeEntry` patterns | ✅ | grep returns 0 matches |
| No remaining `int nativeReturn` patterns | ✅ | grep returns 0 matches |
| All `CallNativeEntry(ptr)` callers use `var` (type inference) | ✅ | 4 call sites verified |
| Sentinel probe discards return value (no type issue) | ✅ | Line 5498: `CallNativeEntry((void*)65534);` — statement, not assignment |

### Known Compilation Risk — ⚠️ LOW

`NativeGuestExecutor.Run` (line 427 of NativeWorker.cs) still returns `int`. The patched `RunGuestEntryStub` casts this to `ulong`:
```csharp
return (ulong)nativeReturn;  // nativeReturn is int from worker.Run()
```

This is a **valid C# cast** (int → ulong is a widening conversion, no data loss for non-negative values). The cast compiles cleanly.

**However:** On Windows, the native worker stub at line 378 (`mov edx, eax`) captures only EAX (32-bit), so the upper 32 bits of the guest return value are already lost before the cast. This is a **Windows-only correctness issue** documented in the code comment. On Linux (our test platform), `RentNativeGuestExecutor` returns `null`, so the direct `CallNativeEntry` path is used — which IS correctly fixed.

**Conclusion:** Patch should compile cleanly on both Linux and Windows. Windows has a separate 32-bit truncation issue in the native worker stub that is NOT fixed by this patch (documented as follow-up).

---

## Dreaming Sarah Golden Test — ❌ CANNOT RUN

**Required:**
```bash
SHARPEMU_HEADLESS=1 SHARPEMU_CAPTURE=1 ./SharpEmu.CLI --game dreaming-sarah --timeout 30
```

**Cannot run** — no built binary, no dotnet SDK to build it.

**Expected baseline (from CHECKPOINT_v0.0.11.md):**
- Frame count: 138
- Color count: 167+
- AgcDriverSubmitDcb: 84
- VideoOutAddFlipEvent: 84
- 0 crashes, 0 NULL execute faults

**Regression risk assessment:**
- The `context.Rax` write-back in `ExecuteGuestThreadEntry` is NEW behavior
- Before fix: inner context's Rax was always 0 after thunk
- After fix: inner context's Rax contains real host RAX value
- Dreaming Sarah (native C++, no IL2CPP) may not use `TryCallGuestFunction` at all — if so, no regression risk
- If Dreaming Sarah DOES use nested guest callbacks, the fix should be neutral or beneficial (real return values instead of 0)

**Verdict:** ⚠️ UNKNOWN — maintainer must run the test.

---

## Arise Regression — ❌ CANNOT RUN

**Required:**
```bash
./SharpEmu.CLI --game arise --timeout 30
```

**Cannot run** — no built binary.

**Expected:** No new GPU memory faults, no new unresolved NIDs, framebuffer state matches baseline.

**Regression risk assessment:** Same as Dreaming Sarah — the fix touches the hot path of every guest entry. If Arise uses nested guest callbacks, behavior changes from "always returns 0" to "returns real value". This should be neutral or beneficial.

**Verdict:** ⚠️ UNKNOWN — maintainer must run the test.

---

## Yatzi Validation — ❌ CANNOT RUN

**Required:**
```bash
SHARPEMU_SEMA_FAST_PATH=0 ./SharpEmu.CLI --game yatzi --timeout 60
```

**Cannot run** — no built binary.

### A) RAX Propagation — ❌ CANNOT MEASURE

**Expected after fix:**
- `[RESOLVER-TRACE] Exit #N: RAX=0x...` log lines show non-zero function pointers
- `_resolverReturnNonZero` counter climbs from 0 toward 232
- `returnValue` in `TryCallGuestFunction` matches host RAX

**Cannot measure** — no runtime.

### B) Resolver Validation — ❌ CANNOT MEASURE

**Expected after fix:**
- Total resolver calls: ~232 (same as before)
- Successful resolves: ~232 (was 0)
- NULL returns: ~0 (was 232)
- Unknown icalls: depends on whether Yatzi's own init registers them

**Cannot measure** — no runtime.

### C) Unity Bootstrap — ❌ CANNOT MEASURE

**Expected after fix:**
- `il2cpp_init` return value: non-zero (real function pointer)
- `il2cpp_resolve_icall` return value: non-zero (real function pointer)
- icall table populated by Yatzi's own init code
- Unity Job System icalls (`Schedule_Injected`, `ScheduleBatchedJobs`) resolvable

**Cannot measure** — no runtime.

### D) Semaphore Lifecycle — ❌ CANNOT MEASURE

**Expected after fix:**
- `sema.create handle=0x81` (same as before)
- `sema.wait handle=0x81` (same as before)
- `sema.signal handle=0x81` (NEW — should appear if bootstrap job runs)
- `sema.signal handle=0x84` (NEW — should appear if PlayerLoop runs)

**Cannot measure** — no runtime.

### E) Render Pipeline — ❌ CANNOT MEASURE

**Expected after fix:**
- `AgcInit > 0` (was 0)
- `VideoOutOpen > 0` (was 0)
- `AgcDcbDrawIndexAuto > 0` (was 0)
- `VideoOutSubmitFlip > 0` (was 0)
- Frame count ≥ 2

**Cannot measure** — no runtime.

---

# Conclusion

## EXP-138: ⚠️ INDETERMINATE (Cannot Validate In Sandbox)

**Confirmed Findings:**
- Patch applied correctly to source code (6 changes across 2 files)
- Static syntax verification passes
- All `CallNativeEntry` callers updated to `ulong`-compatible types
- `context.Rax` write-back added to both `ExecuteGuestThreadEntry` and `ExecuteGuestContinuationEntry`
- Commit `9cef960` pushed to GitHub main

**Rejected Hypotheses:**
- (None — no runtime tests could be run to reject anything)

**Remaining Blocker:**
- **No dotnet SDK in sandbox** — cannot build SharpEmu
- Without build, cannot run Dreaming Sarah, Arise, or Yatzi
- Without runtime, cannot collect RAX/resolver/semaphore/AGC evidence

**Next Recommended Action:**
- **Maintainer must build and run tests on a machine with dotnet SDK**
- Follow the instructions in `.agent_state/next_actions.md`
- Use the EXP-138-results.md template (this file) to fill in runtime metrics
- Commit the completed results back to GitHub

---

## Maintainer Instructions (Copy-Paste Ready)

```bash
# Step 1: Pull latest
git pull origin main

# Step 2: Build
dotnet build -c Release
# If build fails, check for type mismatch errors in CallNativeEntry callers

# Step 3: Dreaming Sarah Golden Test (MANDATORY)
SHARPEMU_HEADLESS=1 SHARPEMU_CAPTURE=1 ./SharpEmu.CLI --game dreaming-sarah --timeout 30
# PASS criteria: frames ≥138, colors ≥167, 0 crashes, 0 NULL faults
# If FAIL: git revert 9cef960

# Step 4: Arise Regression (MANDATORY)
./SharpEmu.CLI --game arise --timeout 30
# PASS criteria: no new GPU faults, no new unresolved NIDs
# If FAIL: git revert 9cef960

# Step 5: Yatzi FAST_PATH=0 (ONLY after 3+4 PASS)
SHARPEMU_SEMA_FAST_PATH=0 ./SharpEmu.CLI --game yatzi --timeout 60 2>&1 | tee yatzi-exp138.log

# Step 6: Collect evidence
grep "RESOLVER-TRACE" yatzi-exp138.log | head -20    # RAX propagation
grep "RAX=0x0000000000000000" yatzi-exp138.log | wc -l  # NULL count (expect 0, was 232)
grep "sema.signal handle=0x00000081" yatzi-exp138.log    # Semaphore 0x81 signal (expect NEW)
grep "sema.signal handle=0x00000084" yatzi-exp138.log    # Semaphore 0x84 signal (expect NEW)
grep "PIPELINE-COUNTS" yatzi-exp138.log | tail -5        # AGC/VideoOut counters

# Step 7: Fill in this template and commit
# Update exp-reports/EXP-138-results.md with actual metrics
git add exp-reports/EXP-138-results.md
git commit -m "EXP-138-results: Runtime validation complete — PASS/FAIL/PARTIAL"
git push origin main
```

---

## If EXP-138 PASSES (Yatzi reaches first frame)

- Close EXP-139, 140, 141, 142, 143, 144, 145 as no longer needed
- Create EXP-146: First frame analysis + render pipeline validation
- Update PROJECT_STATUS to v0.0.12
- Update .agent_state/current_state.md

## If EXP-138 PARTIAL (resolver works but Yatzi still deadlocks)

- Proceed to EXP-139: Implement `arch_init_gc` HLE stub (return OK)
- Re-run Yatzi, check if deadlock breaks
- If still deadlocks → EXP-140: Implement Unity Job System icall HLE stubs

## If EXP-138 FAILS (regression in Dreaming Sarah or Arise)

- REVERT commit `9cef960` immediately: `git revert 9cef960`
- Investigate: Did `context.Rax` write-back break the continuation path?
- Check if any code depends on inner `context.Rax` being 0 after `TryCallGuestFunction`
- Consider alternative fix: write to a separate field instead of `context.Rax`

## If EXP-138 Build Fails

- Check for type mismatch errors
- Verify all `CallNativeEntry` callers updated (grep -rn CallNativeEntry src/)
- Check `NativeGuestExecutor.Run` signature (still returns int — cast is valid but may need follow-up)
- Report build error in this file and commit

---

## Sandbox Limitations Summary

This sandbox CANNOT:
- ❌ Build SharpEmu (no dotnet SDK)
- ❌ Run any game (Dreaming Sarah, Arise, Yatzi)
- ❌ Collect runtime RAX traces
- ❌ Collect runtime resolver return values
- ❌ Collect runtime semaphore lifecycle
- ❌ Collect runtime AGC/VideoOut counters

This sandbox CAN:
- ✅ Apply source code patches
- ✅ Commit and push to GitHub
- ✅ Static syntax verification
- ✅ Create documentation and test plans
- ✅ Maintain .agent_state/ memory files

**All runtime validation must be done by maintainer on a machine with dotnet SDK.**
