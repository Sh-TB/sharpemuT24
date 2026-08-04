# Next Actions — SharpEmuT24 Investigation

**Last updated:** 2026-08-04 (after EXP-138 patch applied)

---

## IMMEDIATE (Maintainer Action Required — Cannot Do In Sandbox)

### 1. Build SharpEmu with EXP-138 patch
```bash
git pull origin main
dotnet build -c Release
```
**Expected:** Build succeeds. If fails, check for type mismatch errors in CallNativeEntry callers.

### 2. Dreaming Sarah Golden Test (MANDATORY regression gate)
```bash
SHARPEMU_HEADLESS=1 SHARPEMU_CAPTURE=1 ./SharpEmu.CLI --game dreaming-sarah --timeout 30
```
**PASS criteria:**
- Frame count ≥ 138
- Color count ≥ 167
- 0 crashes
- 0 NULL execute faults
- VulkanVideoPresenter active
- Framebuffer dump generated

**If FAIL:** REVERT commit `9cef960` immediately.

### 3. Arise Regression (MANDATORY)
```bash
./SharpEmu.CLI --game arise --timeout 30
```
**PASS criteria:**
- No new GPU memory faults
- No new unresolved NIDs
- Framebuffer state matches baseline

**If FAIL:** REVERT commit `9cef960` immediately.

### 4. Yatzi FAST_PATH=0 Validation (ONLY after 2+3 PASS)
```bash
SHARPEMU_SEMA_FAST_PATH=0 ./SharpEmu.CLI --game yatzi --timeout 60
```
Collect:
- **A) RAX propagation:** Search log for `returned 0x...` — expect non-zero values (was 0 before fix)
- **B) Resolver:** Search log for `[RESOLVER-TRACE]` — expect non-zero returns (NULL count should drop from 232 to ~0)
- **C) Unity bootstrap:** Search for `sema.signal handle=0x81` (NEW) and `sema.signal handle=0x84` (NEW)
- **D) Rendering:** Search for `AgcDcbDrawIndexAuto > 0`, `VideoOutSubmitFlip > 0`, Frame #2

### 5. Create EXP-138-results.md
Format:
```markdown
# EXP-138 Results
Commit: 9cef960
Build: PASS/FAIL

## Dreaming Sarah Golden Test
Status: PASS/FAIL
Metrics: frame_count, color_count, crashes, null_faults

## Arise Regression
Status: PASS/FAIL
Metrics: gpu_faults, unresolved_nids, framebuffer_state

## Yatzi Validation
### RAX Propagation: PASS/FAIL
### Resolver: PASS/FAIL (NULL count: 232 → ?)
### Unity Bootstrap: PASS/FAIL
### Semaphore: PASS/FAIL (0x81 signaled? 0x84 signaled?)
### Rendering: PASS/FAIL (AgcDcbDrawIndexAuto? SubmitFlip? Frame #2?)

# Conclusion
EXP-138: PASS / FAIL / PARTIAL
Confirmed Findings: ...
Rejected Hypotheses: ...
Remaining Blocker: ...
Next Recommended EXP: ...
```

---

## CONDITIONAL (Based on EXP-138 Results)

### If EXP-138 PASSES (Yatzi reaches first frame)
- Close EXP-139, 140, 141, 142, 143, 144, 145 as no longer needed
- Create EXP-146: First frame analysis + render pipeline validation
- Update PROJECT_STATUS to v0.0.12

### If EXP-138 PARTIAL (resolver works but Yatzi still deadlocks)
- Proceed to EXP-139: Implement arch_init_gc HLE stub (return OK)
- Re-run Yatzi, check if deadlock breaks
- If still deadlocks → EXP-140: Implement Unity Job System icall HLE stubs

### If EXP-138 FAILS (regression in Dreaming Sarah or Arise)
- REVERT commit `9cef960`
- Investigate: Did context.Rax write-back break the continuation path?
- Check if any code depends on inner context.Rax being 0 after TryCallGuestFunction
- Consider alternative fix: write to a separate field instead of context.Rax

### If EXP-138 build fails
- Check for type mismatch errors
- Verify all CallNativeEntry callers updated (grep -rn CallNativeEntry src/)
- Check NativeGuestExecutor.Run signature (still returns int — may need update)

---

## LONG-TERM (After Yatzi First Frame)

1. Implement remaining Unity Job System icalls (EXP-140 full)
2. Fix sceKernelWaitEqueue fall-through bug (EXP-144.10)
3. Implement arch_init_gc properly (not just stub) — EXP-139
4. Full HLE export audit (EXP-145.6 — 6+ files remaining)
5. Create HLE_STUB_INVENTORY.md (EXP-145.17)
6. Consider Windows native worker stub fix (mov edx,eax → mov rdx,rax) — separate follow-up

---

## SANDBOX LIMITATIONS (What I Cannot Do)

- ❌ Build SharpEmu (no dotnet SDK)
- ❌ Run Dreaming Sarah Golden Test
- ❌ Run Arise regression
- ❌ Run Yatzi with FAST_PATH=0
- ❌ Collect runtime RAX traces
- ❌ Collect runtime resolver return values
- ❌ Collect runtime semaphore lifecycle
- ❌ Collect runtime AGC/VideoOut counters

**All runtime validation must be done by maintainer on a machine with dotnet SDK.**
