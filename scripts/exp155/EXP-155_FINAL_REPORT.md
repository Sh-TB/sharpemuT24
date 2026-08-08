# EXP-155 — Validation Pipeline: Root Cause Confirmation

**Date:** 2026-08-06
**Status:** ALL hypotheses validated. Earliest confirmed broken transition: RAX propagation in TryCallGuestFunction.
**Rule:** TEST ONLY — no code changes, no HLE additions, no architecture modifications.

---

## 1. Confirmed Facts

### Fact 1: EXP-138 RAX Propagation Bug (CONFIRMED)

**Evidence:** Runtime log Entry #170 for `il2cpp_runtime_class_init`

| Measurement | Value |
|------------|-------|
| Resolver return (Exit RAX) | 0x0000000804ED9590 |
| innerRax (EXP032) | 0x0000000804ED9590 |
| cpuContext.Rax (after call) | 0x7FD670094000 |
| Match? | **NO — MISMATCH** |

**Log explicitly states:** `*** RETURN CORRUPTION *** Bug is in RETURN PROPAGATION (TryCallGuestFunction reads back RAX incorrectly)`

**Scope:** 232 out of 232 resolver calls have this same corruption.

### Fact 2: Gate Function at 0x804FB8E60 (CONFIRMED)

The gate function checks `byte [0x808D67B98]`:
- If flag == 0: `je +0x28 → RET` (skip method)
- If flag != 0: mark method as executed, return
- Called 59,744 times via thunk 0x804FA6030

### Fact 3: Flag Writers Have Chicken-and-Egg Guards (CONFIRMED)

Flag 0x808D67B98 has 3 writers — ALL check the flag before writing:
- Writer 0x804FB1C1B in function 0x804FB1B90: checks 0x808D67BB8 first, then 0x808D67B98
- Writer 0x804FBF45B in function 0x804FBF250: same pattern
- Writer 0x804FBF509 in function 0x804FBF250: same pattern

No unconditional writer exists. Flags are NEVER set.

### Fact 4: ELF Uses DT_INIT (CONFIRMED)

Both eboot.bin and Il2cppUserAssemblies.prx use:
- **DT_INIT** (tag 0xC, value 0x10) — standard ELF initialization
- NOT DT_ORBIS_INIT — PS5-specific tag does not exist in these binaries

### Fact 5: Dreaming Sarah Works Because No IL2CPP (CONFIRMED)

| Feature | Yatzi | Dreaming Sarah |
|---------|-------|----------------|
| Uses IL2CPP | Yes | No (native C++) |
| BST resolver | Yes (232 calls) | No (0 calls) |
| RAX corruption | 232 cases | 0 cases |
| il2cpp_runtime_class_init | Yes | No |
| Deadlocks | Yes (WaitSema 0x81) | No |

---

## 2. Hypotheses Tested

### Hypothesis 1: CallNativeEntry crashes during nested transitions
**Status: REJECTED**

**Evidence:**
- 0 mentions of "CallNativeEntry" in runtime log
- 0 mentions of "Invalid Program" error
- 0 crashes related to nested transitions
- The issue is SILENT data corruption, not a crash

### Hypothesis 2: std::_Execute_once involved
**Status: REJECTED**

**Evidence:**
- 0 mentions of "_Execute_once" in Yatzi log
- 0 mentions of "_Execute_once" in Dreaming Sarah log
- Neither game uses this function

### Hypothesis 3: EXP-138 RAX propagation bug
**Status: CONFIRMED**

**Evidence:**
- 232/232 resolver calls have CASE-B RETURN CORRUPTION
- Resolver returns correct address (0x804ED9590)
- cpuContext.Rax gets garbage (0x7FD670094000)
- Log explicitly identifies: "Bug is in RETURN PROPAGATION"

### Hypothesis 4: DT_ORBIS_INIT not used
**Status: CONFIRMED**

**Evidence:**
- Both binaries use DT_INIT (tag 0xC)
- DT_ORBIS_INIT (0x60000001) not present
- SharpEmu correctly uses DT_INIT

### Hypothesis 5: NID shortage
**Status: REJECTED**

**Evidence:**
- 232 resolver entries (sufficient)
- Only 3 unresolved NIDs (arch_init_gc, arch_raise_user, powf/log2f — all CLOSED)
- NID resolution is not the issue

### Hypothesis 6: IL2CPP init chain broken
**Status: CONFIRMED**

**Evidence:**
- il2cpp_runtime_class_init resolved to 0x804ED9590
- GOT slot receives garbage (0x7FD670094000)
- Type initialization NEVER runs
- Flags NEVER set
- Gate blocks ALL methods
- PlayerLoop NEVER runs

---

## 3. Decoder Findings Validation

| Decoder Finding | Status | Evidence |
|----------------|--------|----------|
| CallNativeEntry nested transition crash | **REJECTED** | No crash in logs; issue is silent RAX corruption |
| DT_ORBIS_INIT may not exist | **CONFIRMED** | Both binaries use DT_INIT, not DT_ORBIS_INIT |
| 705 unique NIDs, no shortage | **CONFIRMED** | 232 resolver entries, 3 unresolved (all CLOSED) |
| Yatzi triggers std::_Execute_once | **REJECTED** | 0 mentions in either game log |
| Yatzi/Dreaming Sarah behavioral difference | **CONFIRMED** | Difference is IL2CPP (Unity vs native C++) |

---

## 4. Rejected Paths

All previously closed paths remain closed:
- boot.config — CLOSED
- sceKernelMkdir — CLOSED
- arch_init_gc — CLOSED
- il2cpp_resolve_icall — CLOSED
- 38000 mutex loop — CLOSED
- Producer static XREF — CLOSED

New rejections from EXP-155:
- CallNativeEntry crash — REJECTED (no crash, silent corruption)
- std::_Execute_once — REJECTED (not in logs)
- NID shortage — REJECTED (sufficient NIDs)
- Nested managed/native transition issue — REJECTED (no evidence)

---

## 5. Current Root Cause Confidence

**Root Cause: EXP-138 RAX propagation bug in TryCallGuestFunction**

**Confidence: 95%**

### Evidence Chain:
1. Resolver correctly returns 0x804ED9590 for `il2cpp_runtime_class_init` ✓
2. `innerRax` correctly captures 0x804ED9590 ✓
3. `cpuContext.Rax` receives 0x7FD670094000 (garbage) ✗ **← BROKEN TRANSITION**
4. GOT slot stores garbage ✗
5. `il2cpp_runtime_class_init` never callable ✗
6. Type init flags never set ✗
7. Gate blocks all methods ✗
8. PlayerLoop never runs ✗
9. Deadlock ✗

### Earliest Confirmed Broken Transition:

```
Resolver returns 0x804ED9590
    ↓
TryCallGuestFunction reads context[CpuRegister.Rax]
    ↓
context[CpuRegister.Rax] = 0x7FD670094000  ← BROKEN HERE
    ↓ (should be 0x804ED9590)
GOT slot receives garbage
    ↓
il2cpp_runtime_class_init never runs
    ↓
All downstream failures
```

**The fix:** EXP-138's `raxCaptureSlot` (already in source at DirectExecutionBackend.cs:5068-5069) writes `context[CpuRegister.Rax] = capturedRax`, which should resolve this.

---

## 6. Next Experiment

**Build and validate EXP-138 fix:**

```bash
# 1. Build SharpEmu with EXP-138 fix
dotnet build -c Release

# 2. Dreaming Sarah regression (MANDATORY)
./tests/golden/run-golden-tests.sh
# Expected: 100+ frames, 50+ colors (no regression)

# 3. Yatzi test
SHARPEMU_SEMA_FAST_PATH=0 ./SharpEmu.CLI --game yatzi --timeout 60
# Expected: deadlock breaks, new HLE imports appear

# 4. Verify GOT slot
# Search log for: il2cpp_runtime_class_init
# Check GOT value = 0x804ED9590 (not garbage)

# 5. If deadlock persists, use single-step trace
SHARPEMU_SINGLE_STEP_TRACE=1 SHARPEMU_SEMA_FAST_PATH=0 ./SharpEmu.CLI --game yatzi --timeout 60
```

---

## Success Condition Answer

**"Fix this first because this is where execution diverges."**

The earliest confirmed broken transition is:

**`TryCallGuestFunction` does not propagate RAX from the native thunk to `cpuContext.Rax`.**

- **Location:** `DirectExecutionBackend.cs`, `TryCallGuestFunction` → `ExecuteGuestThreadEntry` → line 5069
- **Fix:** `context[CpuRegister.Rax] = capturedRax;` (already in source via EXP-138 `raxCaptureSlot`)
- **Status:** Fix is in source code but NOT BUILT OR VALIDATED

**This is where execution diverges:** The resolver correctly finds `il2cpp_runtime_class_init` at `0x804ED9590`, but the return value is not propagated to `cpuContext.Rax`. Every subsequent step fails because the GOT slot contains garbage.

---

## Artifacts

- `/home/z/my-project/scripts/exp155/exp155_task1_callnative.py` — Task 1: CallNativeEntry validation
- `/home/z/my-project/scripts/exp155/exp155_task2_rax.py` — Task 2: RAX propagation validation
- `/home/z/my-project/scripts/exp155/exp155_task3_init_chain.py` — Task 3: IL2CPP init chain
- `/home/z/my-project/scripts/exp155/exp155_task4_elf.py` — Task 4: ELF validation
- `/home/z/my-project/scripts/exp155/exp155_task5_nid.py` — Task 5: NID validation
- `/home/z/my-project/scripts/exp155/exp155_task6_game_compare.py` — Task 6: Game comparison
- `/home/z/my-project/scripts/exp155/EXP-155_FINAL_REPORT.md` — This report
