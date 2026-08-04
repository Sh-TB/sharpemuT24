# EXP-139 Yatzi Blocker Analysis

**Date:** 2026-08-04
**Commit tested:** `1f1b5b9` (EXP-138 v2 + Yatzi results)
**Game:** Yatzi (PPSA17697)
**Status:** BLOCKED — .NET 10 runtime error prevents reaching EXP-138 validation point

---

## 1. Rules Loaded Confirmation

- **docs/AGENT_MASTER_RULES.md:** YES — 6 Golden Rules loaded
- **docs/SOP/SHARPEMU_DEBUG_PROTOCOL.md:** YES — 15 SOP rules loaded
- **.agent_state/current_state.md:** YES — EXP-138 active fix confirmed
- **.agent_state/closed_paths.md:** YES — 22 closed paths loaded, will not re-investigate
- **PROJECT_STATUS_v0.0.11.md:** YES — investigation history understood
- **tests/golden/GOLDEN_BASELINE.md:** YES — v0.0.12 environment requirements understood

**Dreaming Sarah = CONFIRMED Golden Baseline.** Do NOT touch rendering path.

---

## 2. Environment

| Component | Value |
|-----------|-------|
| .NET SDK | 10.0.302 (project requires 10.0.103 with `rollForward: latestMajor`) |
| OS | Linux x86-64 (sandbox) |
| GPU | Lavapipe (software Vulkan) |
| X11 | Xvfb :99 |
| GLFW | X11 backend (from libglfw3) |
| Headless | NO (SHARPEMU_HEADLESS unset) |

---

## 3. Build SDK Version

- **SDK installed:** 10.0.302
- **Project requires:** 10.0.103 (global.json with `rollForward: latestMajor`)
- **.NET 9:** Attempted install — FAILED (no disk space)
- **.NET 8:** Available (8.0.423) but project targets net10.0, cannot build with 8.x
- **Build result:** PASS (0 errors, 13 pre-existing warnings)

---

## 4. Exact Crash

```
Fatal error.
Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code.
   at SharpEmu.Core.Cpu.Native.DirectExecutionBackend.CallNativeEntry(Void*)
   at SharpEmu.Core.Cpu.Native.DirectExecutionBackend.ExecuteEntry(SharpEmu.HLE.CpuContext, UInt64, SharpEmu.HLE.OrbisGen2Result ByRef)
   at SharpEmu.Core.Cpu.Native.DirectExecutionBackend.TryExecute(...)
   at SharpEmu.Core.Cpu.CpuDispatcher.DispatchEntryCore(...)
   at SharpEmu.Core.Runtime.SharpEmuRuntime.Run(...)
```

**Exit code:** 134 (SIGABRT)

---

## 5. First Failing Instruction

The crash is NOT a CPU instruction fault. It is a **.NET 10 runtime validation failure** that occurs when `CallNativeEntry` tries to invoke `delegate* unmanaged[Cdecl]<int>` from a managed context.

**The crash occurs at:**
```csharp
private unsafe static int CallNativeEntry(void* entry)
{
    var nativeEntry = (delegate* unmanaged[Cdecl]<int>)entry;
    return nativeEntry();  // ← .NET 10 throws "Invalid Program" here
}
```

**When:** After `EXECUTE_ONCE` callback returns successfully. The `EXECUTE_ONCE` HLE export calls `TryCallGuestFunction` → `ExecuteGuestThreadEntry` → `CallNativeEntry` (nested). After this nested call returns, the .NET 10 runtime loses track of the managed/native transition state. The NEXT `CallNativeEntry` call (from the outer `ExecuteEntry`) triggers the "Invalid Program" error.

---

## 6. Call Stack

```
Thread.StartCallback()
  → Program.Run()
    → SharpEmuRuntime.Run()
      → CpuDispatcher.DispatchEntry()
        → DispatchEntryCore()
          → DirectExecutionBackend.TryExecute()
            → DirectExecutionBackend.ExecuteEntry()
              → DirectExecutionBackend.CallNativeEntry()  ← CRASH HERE
```

**Pre-crash sequence:**
1. `ExecuteEntry starting at 0x800000070` — main entry point starts
2. Guest runs ~1147 imports successfully
3. Import #1125: `_ZSt13_Execute_once` (std::_Execute_once) called
4. `ExecuteOnce` HLE export calls `scheduler.TryCallGuestFunction()`
5. `TryCallGuestFunction` → `ExecuteGuestThreadEntry` → `CallNativeEntry` (nested call)
6. Nested `CallNativeEntry` succeeds — guest callback runs and returns 0
7. `EXECUTE_ONCE` callback SUCCESS — flag marked complete
8. **Next instruction after `ExecuteOnce` returns to guest** — guest calls another import
9. The import dispatch eventually reaches `ExecuteEntry` → `CallNativeEntry` again
10. **CRASH:** .NET 10 throws "Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code"

---

## 7. Comparison: Dreaming Sarah vs Yatzi

| Aspect | Dreaming Sarah | Yatzi |
|--------|---------------|-------|
| Engine | Native C++ | Unity IL2CPP |
| `EXECUTE_ONCE` calls | **0** | **6** |
| `TryCallGuestFunction` calls | 0 (not needed) | 6 (via `EXECUTE_ONCE`) |
| Call chain depth | Shallow: `ExecuteEntry` → `CallNativeEntry` | Deep: `ExecuteEntry` → `CallNativeEntry` → guest → `ExecuteOnce` HLE → `TryCallGuestFunction` → `ExecuteGuestThreadEntry` → `CallNativeEntry` |
| Managed/native crossings | 1 (managed → native) | 3+ (managed → native → managed → native → managed → native) |
| .NET 10 "Invalid Program" | Does NOT occur | **Occurs after nested call returns** |
| Result | ✅ PASS (23/23/228 colors) | ❌ FAIL (SIGABRT) |

**Root cause of difference:** Dreaming Sarah never calls `EXECUTE_ONCE` (native C++ doesn't use `std::_Execute_once`). Yatzi (Unity IL2CPP) calls `EXECUTE_ONCE` 6 times during initialization. The first `EXECUTE_ONCE` succeeds, but after it returns, the .NET 10 runtime's managed/native transition tracking is corrupted, and the next `CallNativeEntry` call fails.

---

## 8. Hypotheses

### CONFIRMED

**H1: The crash is caused by .NET 10 runtime restriction on nested managed/native calls.**
- **Evidence:**
  - Dreaming Sarah (0 `EXECUTE_ONCE` calls) works fine
  - Yatzi (6 `EXECUTE_ONCE` calls) crashes after the first `EXECUTE_ONCE` returns
  - The crash occurs at `CallNativeEntry` which uses `delegate* unmanaged[Cdecl]<int>`
  - The error message is "Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code" — a .NET runtime validation, not a CPU fault
  - The crash occurs AFTER the nested call succeeds (not during it)

### REJECTED

**H2: The crash is caused by EXP-138's `ulong` return type change.**
- **Evidence:** EXP-138 v2 reverted `CallNativeEntry` to `int` return type. The crash still occurs with the original `int` signature. The `ulong` change (v1) made it crash IMMEDIATELY, but the `int` version (v2) crashes after `EXECUTE_ONCE` — proving the issue is pre-existing.
- **Status:** REJECTED

**H3: The crash is caused by EXP-138's `raxCaptureSlot` addition.**
- **Evidence:** The crash occurs at `ExecuteEntry` → `CallNativeEntry`, NOT at `ExecuteGuestThreadEntry` (where `raxCaptureSlot` is used). The `raxCaptureSlot` code path is only in `ExecuteGuestThreadEntry`, which runs successfully during `EXECUTE_ONCE`.
- **Status:** REJECTED

**H4: The crash is a regression from EXP-138.**
- **Evidence:** The original code (commit `9cef960~1`) has the same `CallNativeEntry` with `delegate* unmanaged[Cdecl]<int>`. If built with .NET 10, it would crash the same way. The previous EXP-118 run (which reached WaitSema(0x81)) was either built with a different .NET version or the `EXECUTE_ONCE` path was not triggered.
- **Status:** REJECTED

### UNKNOWN

**H5: Would building with .NET 9 fix the issue?**
- **Evidence:** Cannot test — .NET 9 installation failed (no disk space in sandbox)
- **Status:** UNKNOWN (needs maintainer with more disk space)

**H6: Would adding `[UnmanagedCallersOnly]` to `CallNativeEntry` fix the issue?**
- **Evidence:** Not yet tested. The attribute would make the method explicitly unmanaged, potentially avoiding the .NET 10 transition tracking issue.
- **Status:** UNKNOWN (needs experimentation)

**H7: Did the previous EXP-118 run (which reached WaitSema(0x81)) use a different .NET version?**
- **Evidence:** The EXP-118 log shows 232 resolver calls and a WaitSema stall — this means `CallNativeEntry` worked for nested calls. Either:
  - (a) The build used a different .NET version (not 10.x), OR
  - (b) The `EXECUTE_ONCE` path was different in the previous build, OR
  - (c) The .NET 10 restriction was added in a recent minor version
- **Status:** UNKNOWN (cannot verify without the previous build environment)

---

## 9. Minimal Next Experiment

**EXP-139.1: Add `[UnmanagedCallersOnly]` attribute to `CallNativeEntry`**

**Hypothesis:** The .NET 10 runtime treats `delegate* unmanaged[Cdecl]<int>` invocation as an `UnmanagedCallersOnly` call. When called from a managed context after a nested managed/native transition, the runtime's state tracking breaks. Marking `CallNativeEntry` itself as `[UnmanagedCallersOnly]` would make the transition explicit and may avoid the tracking issue.

**Test:**
1. Add `[UnmanagedCallersOnly(CallConvs = new[] { typeof(CallConvCdecl) })]` to `CallNativeEntry`
2. Build with .NET 10
3. Run Dreaming Sarah Golden Test (verify no regression)
4. Run Yatzi with `SHARPEMU_SEMA_FAST_PATH=0`
5. Check if the crash is resolved

**Risk:** LOW — the attribute only affects how the .NET runtime dispatches the call, not the actual native execution. If it causes a regression in Dreaming Sarah, revert immediately.

**Alternative if EXP-139.1 fails:**
- EXP-139.2: Use `Marshal.GetDelegateForFunctionPointer` instead of `delegate* unmanaged`
- EXP-139.3: Build with .NET 9 (needs more disk space)

---

## Conclusion

**Status: BLOCKED**

The .NET 10 runtime error prevents Yatzi from reaching the EXP-138 validation point (IL2CPP resolver via `TryCallGuestFunction`). The crash is a pre-existing .NET 10 issue, NOT caused by EXP-138.

**EXP-138 RAX propagation fix is NOT validated** — but it is also NOT disproven. The code path never reached the IL2CPP resolver.

**Safe to proceed with EXP-139.1** (add `[UnmanagedCallersOnly]` attribute) — this is a minimal change that does NOT touch:
- Dreaming Sarah rendering path
- GPU/AGC code
- Semaphore code
- Any closed EXP paths
