# EXP-138-final — TryCallGuestFunction RAX Propagation Fix: Applied + Runtime Validation Plan

**Date:** 2026-08-04
**Task ID:** 138-final
**Predecessor:** EXP-138 (patch design), EXP-137 Phase 5 (bug identification)
**Priority:** 🔴 P0 — highest blast radius fix in the entire investigation
**Status:** PATCH APPLIED — build + runtime tests PENDING (no dotnet SDK in sandbox)

---

## Honest Status

| Step | Status | Notes |
|------|--------|-------|
| 1. Apply EXP-138 patch | ✅ COMPLETE | 5 changes applied to DirectExecutionBackend.cs + 1 to NativeWorker.cs |
| 2. Build (`dotnet build -c Release`) | ⏸ CANNOT DO | No dotnet SDK in sandbox |
| 3. Golden Regression #1: Dreaming Sarah | ⏸ CANNOT DO | Requires build first |
| 4. Golden Regression #2: Arise | ⏸ CANNOT DO | Requires build first |
| 5. Run Yatzi FAST_PATH=0 | ⏸ CANNOT DO | Requires build + regression pass |

**The patch is applied to source code and committed to GitHub. The maintainer must build and run the tests on a machine with dotnet SDK.**

---

## Patch Applied (6 changes across 2 files)

### File 1: `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs`

#### Change 1 (line 879): `CallNativeEntry` return type `int` → `ulong`

```diff
- private unsafe static int CallNativeEntry(void* entry)
- {
-     var nativeEntry = (delegate* unmanaged[Cdecl]<int>)entry;
-     return nativeEntry();
- }
+ // EXP-138: Return type changed from int -> ulong to preserve full 64-bit
+ // guest function pointers (e.g. il2cpp_* resolver returns 0x804ED9B90).
+ // The previous int return truncated the upper 32 bits, and combined with
+ // the missing context.Rax write-back in the thunks below, caused every
+ // nested guest callback to return 0 to the outer guest (EXP-026/137).
+ private unsafe static ulong CallNativeEntry(void* entry)
+ {
+     var nativeEntry = (delegate* unmanaged[Cdecl]<ulong>)entry;
+     return nativeEntry();
+ }
```

#### Change 2 (line 5037-5054): `ExecuteGuestThreadEntry` — write host RAX back into `context.Rax`

```diff
  try
  {
      var nativeReturn = CallNativeEntry(ptr);
+     // EXP-138: Write host RAX back into inner CpuContext.Rax so
+     // TryCallGuestFunction (line ~3505) can read it. Without this
+     // write-back, the inner context's Rax stays at its construction-
+     // time default of 0, causing every nested guest callback to
+     // return 0 to the outer guest (EXP-026/EXP-137 root cause).
+     context[CpuRegister.Rax] = nativeReturn;
      if (ActiveGuestThreadYieldRequested)
      {
          reason = ActiveGuestThreadYieldReason ?? "guest thread blocked";
          return GuestNativeCallExitReason.Blocked;
      }
      ...
-     reason = $"returned 0x{nativeReturn:X8}";
+     reason = $"returned 0x{nativeReturn:X16}";
      return GuestNativeCallExitReason.Returned;
  }
```

#### Change 3 (line 5211-5227): `ExecuteGuestContinuationEntry` — same Rax write-back

```diff
  try
  {
      var nativeReturn = CallNativeEntry(ptr);
+     // EXP-138: Same Rax write-back as ExecuteGuestThreadEntry above.
+     // The continuation path already sets Rax going IN via
+     // EmitMovR64Imm(0x48, 0xB8, ...) at line ~5187; this captures
+     // the new Rax value coming OUT after the continuation runs.
+     context[CpuRegister.Rax] = nativeReturn;
      ...
-     reason = $"returned 0x{nativeReturn:X8}";
+     reason = $"returned 0x{nativeReturn:X16}";
      return GuestNativeCallExitReason.Returned;
  }
```

#### Change 4 (line 5504-5547): Entry path `num6` type `int` → `ulong`

```diff
- int num6 = -1;
+ // EXP-138: num6 type changed int -> ulong for CallNativeEntry signature change.
+ // Use ulong.MaxValue as the "error" sentinel (was -1 as int).
+ ulong num6 = ulong.MaxValue;
  try
  {
      num6 = CallNativeEntry(ptr);
-     Console.Error.WriteLine($"[LOADER][INFO] Guest returned: {num6}");
+     Console.Error.WriteLine($"[LOADER][INFO] Guest returned: 0x{num6:X16}");
      ...
  }
  catch (AccessViolationException ex)
  {
      ...
-     num6 = -1;
+     num6 = ulong.MaxValue;
  }
  catch (Exception ex2)
  {
      ...
-     num6 = -1;
+     num6 = ulong.MaxValue;
  }
  ...
  if (num6 == 0)
  {
      result = OrbisGen2Result.ORBIS_GEN2_OK;
      LastError = null;
      return true;
  }
  result = OrbisGen2Result.ORBIS_GEN2_ERROR_CPU_TRAP;
  if (string.IsNullOrEmpty(LastError))
  {
-     LastError = $"Guest entry point returned non-zero: {num6}";
+     LastError = $"Guest entry point returned non-zero: 0x{num6:X16}";
  }
```

**Note on Change 4:** The sentinel probe at line 5498 (`CallNativeEntry((void*)65534)`) discards the return value, so no type change needed at the call site.

### File 2: `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.NativeWorker.cs`

#### Change 5 (line 59-91): `RunGuestEntryStub` return type `int` → `ulong`

```diff
- private unsafe int RunGuestEntryStub(void* entryStub, ulong hostRspSlot)
+ private unsafe ulong RunGuestEntryStub(void* entryStub, ulong hostRspSlot)
  {
      var worker = RentNativeGuestExecutor();
      if (worker is null)
      {
          TlsSetValue(_hostRspSlotTlsIndex, (nint)hostRspSlot);
          return CallNativeEntry(entryStub);  // now returns ulong
      }
      try
      {
          var nativeReturn = worker.Run(...);  // still returns int
          ...
-         return nativeReturn;
+         // EXP-138: Cast int -> ulong for type consistency with CallNativeEntry.
+         // NOTE: The Windows native worker stub (line ~378) currently captures
+         // eax (32-bit) not rax (64-bit), so the upper 32 bits are already lost
+         // before this cast. The native stub fix (mov edx,eax -> mov rdx,rax)
+         // is a separate follow-up for Windows correctness; on Linux the native
+         // worker path is not used (RentNativeGuestExecutor returns null).
+         return (ulong)nativeReturn;
      }
      ...
  }
```

**Note on Change 5:** `RunGuestEntryStub` is dead code (grep found zero callers). The change is for compilation consistency only. On Linux (our test platform), `RentNativeGuestExecutor` returns `null`, so the direct `CallNativeEntry` path is used — which is already fixed by Change 1.

The Windows native worker stub has a separate 32-bit truncation bug at line 378 (`mov edx, eax` — captures EAX not RAX). This is documented in the code comment but NOT fixed in this patch. It's a Windows-only follow-up that doesn't affect Linux/Yatzi testing.

---

## All `CallNativeEntry` Callers (verified)

| File | Line | Caller | Return value used? | Fixed? |
|------|------|--------|-------------------|--------|
| DirectExecutionBackend.cs | 879 | Definition | N/A (definition) | ✅ |
| DirectExecutionBackend.cs | 5037 | `ExecuteGuestThreadEntry` | Yes → `context.Rax` | ✅ |
| DirectExecutionBackend.cs | 5211 | `ExecuteGuestContinuationEntry` | Yes → `context.Rax` | ✅ |
| DirectExecutionBackend.cs | 5498 | Sentinel probe | No (discarded) | N/A |
| DirectExecutionBackend.cs | 5509 | Entry path (`num6`) | Yes → success/fail check | ✅ |
| NativeWorker.cs | 65 | `RunGuestEntryStub` (dead code) | Yes → return to caller (dead) | ✅ |

**All callers verified. No other files reference `CallNativeEntry`.**

---

## Maintainer Instructions (Required to Complete EXP-138)

### Step 1: Build

```bash
cd <sharpemu-source-root>
git pull origin main
dotnet build -c Release
```

**If build fails:** Check for type mismatch errors. The most likely issue is a caller of `CallNativeEntry` or `RunGuestEntryStub` that I missed. Search:
```bash
grep -rn "CallNativeEntry\|RunGuestEntryStub" src/
```

### Step 2: Golden Regression Test #1 — Dreaming Sarah (MANDATORY)

```bash
# Run Dreaming Sarah for 30 seconds (or until first frame)
./SharpEmu.CLI --game dreaming-sarah --timeout 30

# Collect:
# - frame count (golden baseline: 138 frames in 30s)
# - framebuffer checksum (golden baseline: 167+ distinct colors)
# - color count
# - crashes (should be 0)
# - NULL execute faults (should be 0)
# - resolver return values (should be non-zero for il2cpp_* symbols)
```

**PASS criteria:**
- Frame count ≥ 138 (no regression from baseline)
- Color count ≥ 167 (no regression)
- 0 crashes
- 0 NULL execute faults
- Resolver returns non-zero for il2cpp_* symbols (if Dreaming Sarah uses IL2CPP — it's native C++, so this may not apply)

**If FAIL:** REVERT the patch immediately. The fix has a regression. Investigate whether the `context.Rax` write-back has unintended side effects on the continuation path or the blocking-resume path.

### Step 3: Golden Regression Test #2 — Arise (MANDATORY)

```bash
# Run Arise for 30 seconds (or until first frame)
./SharpEmu.CLI --game arise --timeout 30

# Collect:
# - GPU memory faults (should be 0 or same as baseline)
# - unresolved NIDs (should be same as baseline)
# - crash address (should be 0 or same as baseline)
# - framebuffer state (should be non-zero if baseline was non-zero)
```

**PASS criteria:**
- No new GPU memory faults (compared to baseline)
- No new unresolved NIDs
- No new crash addresses
- Framebuffer state matches or exceeds baseline

**If FAIL:** REVERT the patch immediately.

### Step 4: Run Yatzi FAST_PATH=0 (ONLY after Steps 2 + 3 PASS)

```bash
# Run Yatzi with FAST_PATH=0 (no semaphore bypass)
SHARPEMU_SEMA_FAST_PATH=0 ./SharpEmu.CLI --game yatzi --timeout 60

# Collect and check:
```

#### A) Resolver returns
```bash
# Search log for resolver traces
grep "\[RESOLVER-TRACE\]" yatzi.log | head -20

# EXPECTED (after fix):
# - il2cpp_init return value: non-zero (e.g., 0x804ED85D0)
# - il2cpp_resolve_icall return value: non-zero (e.g., 0x804ED8780)
# - NULL return count: should drop from 232 to ~0

# Search for NULL returns
grep "RAX=0x0000000000000000" yatzi.log | wc -l
# EXPECTED: 0 (was 232 before fix)
```

#### B) RAX propagation
```bash
# Search for non-zero callback returns
grep "returned 0x" yatzi.log | grep -v "0x0000000000000000" | head -20
# EXPECTED: many non-zero returns (was 0 before fix)

# Search for nested guest call results
grep "returnValue=" yatzi.log | head -20
# EXPECTED: non-zero returnValue for il2cpp_* API lookups
```

#### C) Unity bootstrap
```bash
# Check semaphore 0x81 lifecycle
grep "handle=0x00000081" yatzi.log
# EXPECTED:
# - sema.create handle=0x81 (same as before)
# - sema.wait handle=0x81 (same as before)
# - sema.signal handle=0x81 (NEW — should appear after fix if bootstrap job runs)

# Check semaphore 0x84 (ResumeSemaphore)
grep "handle=0x00000084" yatzi.log
# EXPECTED:
# - sema.create handle=0x84 (same as before)
# - sema.signal handle=0x84 (NEW — should appear if PlayerLoop runs)

# Check worker thread resume
grep "AssetGarbageCollectorHelper" yatzi.log | grep -v "Blocked"
# EXPECTED: workers should transition from Blocked to Running after fix
```

#### D) Rendering
```bash
# Check pipeline counters
grep "PIPELINE-COUNTS" yatzi.log | tail -5
# EXPECTED (after fix):
# - AgcInit > 0
# - VideoOutOpen > 0
# - AgcDcbDrawIndexAuto > 0 (was 0 before fix)
# - VideoOutSubmitFlip > 0 (was 0 before fix)

# Check for Frame #2
grep "frame" yatzi.log | tail -10
# EXPECTED: frame count ≥ 2

# Check framebuffer
grep "framebuffer" yatzi.log | tail -10
# EXPECTED: non-zero framebuffer writes
```

### Step 5: Create EXP-138-results.md

After running all tests, create `exp-reports/EXP-138-results.md` with:
- Dreaming Sarah results (PASS/FAIL + metrics)
- Arise results (PASS/FAIL + metrics)
- Yatzi results (PASS/FAIL + metrics for A/B/C/D above)
- Verdict: FIX CONFIRMED / FIX REJECTED / PARTIAL
- If PARTIAL: which downstream EXPs (139-145) are still needed

---

## What This Fix Does (Expected Behavior Change)

### Before fix
1. `il2cpp_init` calls `il2cpp_api_lookup_symbol("il2cpp_resolve_icall")`
2. SharpEmu's `DispatchIl2CppApiLookupSymbol` calls `TryCallGuestFunction`
3. `TryCallGuestFunction` creates inner `CpuContext` (Rax = 0)
4. `ExecuteGuestThreadEntry` calls Yatzi's resolver at `0x804ED9B90`
5. Yatzi's resolver finds BST match, loads function pointer into host RAX (e.g., 0x804ED8780)
6. Thunk returns; `CallNativeEntry` captures EAX (low 32 bits = 0xF4ED8780, truncated)
7. `TryCallGuestFunction` reads `context.Rax` = 0 (inner context never updated)
8. `DispatchIl2CppApiLookupSymbol` writes 0 to outer guest's RAX
9. Yatzi's `il2cpp_init` sees 0 for every `il2cpp_*` API → 232 NULL returns

### After fix
1. Same steps 1-5
6. Thunk returns; `CallNativeEntry` captures full RAX (0x804ED8780, 64-bit)
7. `ExecuteGuestThreadEntry` writes `context.Rax = 0x804ED8780`
8. `TryCallGuestFunction` reads `context.Rax` = 0x804ED8780
9. `DispatchIl2CppApiLookupSymbol` writes 0x804ED8780 to outer guest's RAX
10. Yatzi's `il2cpp_init` sees real function pointer → calls it → registers icalls → Unity Job System works → bootstrap job submitted → semaphore 0x81 signaled → deadlock breaks

### Risk assessment
- **Highest blast radius:** This fix touches `CallNativeEntry` which is on the hot path of every guest entry, every nested callback, and every continuation resume. Any subtle error here will break ALL games, not just Yatzi.
- **Regression risk:** The `context.Rax` write-back in `ExecuteGuestThreadEntry` is NEW behavior. Before the fix, the inner context's Rax was never written back (it was always 0). Some code might depend on this behavior (e.g., if a caller reads `context.Rax` after `TryCallGuestFunction` returns and expects 0 for some reason). The continuation path already had a form of Rax write-back (via `EmitMovR64Imm` going IN), so it's less risky there.
- **Mitigation:** The mandatory Dreaming Sarah + Arise regression gate will catch any regression before Yatzi is tested.

---

## If The Fix Doesn't Work

If Yatzi still deadlocks after this fix (and Dreaming Sarah + Arise pass), proceed to:

1. **EXP-139:** Implement `arch_init_gc` HLE stub (may still be needed independently)
2. **EXP-140:** Implement Unity Job System icall HLE stubs (`Schedule_Injected`, `ScheduleBatchedJobs`, `ResetJobWorkerCount`)
3. **EXP-145:** Emergency workarounds (`SHARPEMU_UNITY_NO_JOBS=1`, resolver bypass, metadata shortcut)

The fix may be necessary but not sufficient — `arch_init_gc` returning NOT_FOUND is an independent issue that could still block the GC initialization path even after the RAX propagation is fixed.

---

## Commit Information

**Commit hash:** (will be filled after commit)
**Files changed:**
- `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs` (5 changes)
- `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.NativeWorker.cs` (1 change)
- `exp-reports/EXP-138-final.md` (this file)
- `scripts/exp138/EXP-138-final.md` (mirror)

**Commit message:**
```
EXP-138: Apply TryCallGuestFunction RAX propagation fix — 5 changes to
DirectExecutionBackend.cs + 1 to NativeWorker.cs

Root cause fix for EXP-026/EXP-137 "232 NULL returns":
- CallNativeEntry: int -> ulong (preserve 64-bit function pointers)
- ExecuteGuestThreadEntry: write context.Rax = nativeReturn after thunk
- ExecuteGuestContinuationEntry: same Rax write-back
- Entry path (num6): int -> ulong, -1 -> ulong.MaxValue
- NativeWorker RunGuestEntryStub: int -> ulong (dead code, type consistency)

MANDATORY regression gate: Dreaming Sarah → Arise → Yatzi (in order).
Do NOT skip regression gate — highest blast radius fix in project.

Build + runtime tests PENDING (no dotnet SDK in sandbox).
See EXP-138-final.md for maintainer instructions.
```
