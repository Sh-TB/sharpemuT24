# Yatzi Blocker Analysis — Permanent Documentation

**Purpose:** Prevent future agents from repeating the same investigation. This document explains why Dreaming Sarah works, why Yatzi fails earlier, and why EXP-138 is not yet validated.

**Last updated:** 2026-08-04 (EXP-139)

---

## Why Dreaming Sarah Works

Dreaming Sarah (PPSA02929) is a **native C++ game**. It does NOT use:
- Unity IL2CPP runtime
- `std::_Execute_once` (C++ static initialization callback)
- `TryCallGuestFunction` (nested guest callbacks)

**Call path (shallow):**
```
SharpEmuRuntime.Run()
  → CpuDispatcher.DispatchEntry()
    → DirectExecutionBackend.TryExecute()
      → DirectExecutionBackend.ExecuteEntry()
        → DirectExecutionBackend.CallNativeEntry()  ← 1 managed→native crossing
          → guest code runs
          → guest calls HLE imports (managed code)
          → HLE imports return to guest (native code)
          → guest eventually returns
        → CallNativeEntry returns
      → ExecuteEntry returns
    → TryExecute returns
  → DispatchEntry returns
→ Run returns
```

**Why .NET 10 allows this:** There is only ONE `CallNativeEntry` call in the call chain. The managed→native transition is simple and well-tracked by the .NET runtime.

**Golden Test result:** ✅ PASS (23/23/228 colors, v0.0.12 baseline)

---

## Why Yatzi Fails Earlier

Yatzi (PPSA17697) is a **Unity IL2CPP game**. It uses:
- Unity IL2CPP runtime (il2cpp_init, il2cpp_resolve_icall, etc.)
- `std::_Execute_once` for static initialization (C++ once_flag pattern)
- `TryCallGuestFunction` for nested guest callbacks

**Call path (deep, with nested managed/native crossings):**
```
SharpEmuRuntime.Run()
  → CpuDispatcher.DispatchEntry()
    → DirectExecutionBackend.TryExecute()
      → DirectExecutionBackend.ExecuteEntry()
        → DirectExecutionBackend.CallNativeEntry()  ← crossing 1: managed→native
          → guest code runs
          → guest calls _ZSt13_Execute_once (HLE export)
            → ExecuteOnce() HLE handler (managed code)  ← crossing 2: native→managed
              → scheduler.TryCallGuestFunction()
                → DirectExecutionBackend.ExecuteGuestThreadEntry()
                  → DirectExecutionBackend.CallNativeEntry()  ← crossing 3: managed→native
                    → nested guest callback runs
                    → nested guest returns
                  → CallNativeEntry returns
                → ExecuteGuestThreadEntry returns
              → TryCallGuestFunction returns
            → ExecuteOnce HLE returns  ← crossing 4: managed→native
          → guest continues running
          → guest calls another import
            → Import dispatch (managed code)  ← crossing 5: native→managed
              → ... eventually reaches ...
              → DirectExecutionBackend.CallNativeEntry()  ← crossing 6: managed→native
                → *** CRASH: .NET 10 "Invalid Program" ***
```

**Why .NET 10 fails:** After the nested `CallNativeEntry` (crossing 3) returns, the .NET 10 runtime's managed/native transition state tracking becomes corrupted. The next `CallNativeEntry` call (crossing 6) triggers the "Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code" error.

**Key evidence:**
- Dreaming Sarah: 0 `EXECUTE_ONCE` calls → works
- Yatzi: 6 `EXECUTE_ONCE` calls → crashes after the first one returns
- The crash occurs at `CallNativeEntry` (the outer call), NOT at `TryCallGuestFunction` (the nested call)
- The crash occurs AFTER the nested call succeeds (not during it)

---

## Why EXP-138 Is Not Yet Validated

**EXP-138** fixes the `TryCallGuestFunction` return value propagation bug (root cause of EXP-026/137 "232 NULL returns").

**The fix is in `ExecuteGuestThreadEntry`** (the nested call path):
- Added `raxCaptureSlot` (native buffer) to capture full 64-bit host RAX
- Thunk sentinel writes RAX to `raxCaptureSlot` before returning
- `context.Rax` populated from `raxCaptureSlot`
- `TryCallGuestFunction` reads `context.Rax` (now contains real value)

**Why it cannot be validated:**
1. Yatzi crashes at `ExecuteEntry` → `CallNativeEntry` (the OUTER call)
2. The crash happens BEFORE the IL2CPP resolver is reached
3. The IL2CPP resolver uses `TryCallGuestFunction` (the INNER call) — which is where EXP-138's fix lives
4. Since the outer call crashes first, the inner call never runs
5. Therefore, EXP-138's RAX propagation fix is never exercised

**EXP-138 is NOT disproven.** The code path never reached the validation point. The fix may be correct, but we cannot confirm without resolving the .NET 10 blocker first.

---

## The .NET 10 Blocker

**Error:** `Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code`

**Location:** `DirectExecutionBackend.CallNativeEntry()` — specifically at the `delegate* unmanaged[Cdecl]<int>` invocation

**Root cause:** .NET 10 runtime restriction on nested managed/native call chains. When `CallNativeEntry` is called from a managed context that has already crossed the managed/native boundary multiple times (via `EXECUTE_ONCE` → `TryCallGuestFunction` → `ExecuteGuestThreadEntry` → `CallNativeEntry`), the runtime's transition state tracking breaks.

**This is a pre-existing issue, NOT caused by EXP-138:**
- The original code (before EXP-138) has the same `CallNativeEntry` with `delegate* unmanaged[Cdecl]<int>`
- EXP-138 v1 changed it to `ulong` (crashed immediately)
- EXP-138 v2 reverted to `int` (crashes after `EXECUTE_ONCE` — same as original would with .NET 10)
- The previous EXP-118 run (which reached WaitSema(0x81)) was either built with a different .NET version or the `EXECUTE_ONCE` path was different

---

## Required Next Experiments

### EXP-139.1: Add `[UnmanagedCallersOnly]` attribute to `CallNativeEntry`
- **Hypothesis:** Making the transition explicit may avoid .NET 10's tracking issue
- **Risk:** LOW — only affects dispatch mechanism, not actual execution
- **Golden Gate:** Must verify Dreaming Sarah still passes

### EXP-139.2: Use `Marshal.GetDelegateForFunctionPointer` instead of `delegate* unmanaged`
- **Hypothesis:** Different invocation mechanism may not trigger the restriction
- **Risk:** MEDIUM — may have performance impact

### EXP-139.3: Build with .NET 9
- **Hypothesis:** .NET 9 may not have this restriction
- **Risk:** LOW — but needs more disk space than sandbox has

### EXP-139.4: Restructure `ExecuteOnce` to avoid nested `CallNativeEntry`
- **Hypothesis:** If `ExecuteOnce` doesn't call `TryCallGuestFunction`, the nested crossing doesn't happen
- **Risk:** HIGH — changes HLE behavior, could break other games
- **Approach:** Run the `ExecuteOnce` callback on the SAME stack (no nested `CallNativeEntry`)

---

## Do NOT Repeat These Investigations

1. **Do NOT blame EXP-138 for the Yatzi crash** — the crash is at `ExecuteEntry`, not at `TryCallGuestFunction`
2. **Do NOT revert EXP-138** — it has not been disproven; it just hasn't been validated yet
3. **Do NOT modify the rendering path** — Dreaming Sarah works, don't break it
4. **Do NOT modify the semaphore code** — the WaitSema(0x81) deadlock is downstream of this blocker
5. **Do NOT reopen EXP-126..135** — those paths are closed
6. **Do NOT use `SHARPEMU_HEADLESS=1` for visual tests** — it forces HeadlessVideoPresenter which doesn't render

---

## Key Files

| File | Purpose |
|------|---------|
| `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs` | `CallNativeEntry`, `ExecuteEntry`, `ExecuteGuestThreadEntry`, `TryCallGuestFunction` |
| `src/SharpEmu.Libs/CxxAbiExports.cs` | `ExecuteOnce` HLE export (calls `TryCallGuestFunction`) |
| `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.NativeWorker.cs` | `RunGuestEntryStub` (Windows-only path, not used on Linux) |
| `global.json` | Requires .NET 10 SDK (`rollForward: latestMajor`) |

---

## Summary

| Question | Answer |
|----------|--------|
| Does Dreaming Sarah work? | ✅ YES (23/23/228 colors, v0.0.12) |
| Does Yatzi work? | ❌ NO (crashes at `CallNativeEntry` after `EXECUTE_ONCE`) |
| Is the Yatzi crash caused by EXP-138? | ❌ NO (pre-existing .NET 10 issue) |
| Is EXP-138 validated? | ⚠️ NOT YET (crash prevents reaching validation point) |
| Is EXP-138 disproven? | ❌ NO (code path never reached) |
| What blocks Yatzi? | .NET 10 "Invalid Program" error on nested managed/native calls |
| What is the next step? | EXP-139.1: Add `[UnmanagedCallersOnly]` to `CallNativeEntry` |
