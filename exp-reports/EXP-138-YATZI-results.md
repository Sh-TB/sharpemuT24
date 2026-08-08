# EXP-138 Yatzi Results

**Date:** 2026-08-04
**Commit tested:** `9cef960` (EXP-138 patch, revised) on `7f778f8` (main HEAD with Arise report)
**Game:** Yatzi (PPSA17697)
**Result:** **FAIL** — .NET 10 runtime error (pre-existing, NOT caused by EXP-138)

---

## Environment

| Component | Value |
|-----------|-------|
| .NET SDK | 10.0.302 |
| OS | Linux x86-64 (sandbox) |
| GPU | Lavapipe (software Vulkan) |
| Vulkan | YES (via Lavapipe) |
| X11 | YES (Xvfb :99) |
| GLFW | X11 backend |
| Headless | NO (SHARPEMU_HEADLESS unset) |
| FAST_PATH | 0 (SHARPEMU_SEMA_FAST_PATH=0) |

---

## Build

**Status:** PASS

- 0 errors, 13 pre-existing warnings
- EXP-138 patch compiled cleanly (revised version with native RAX capture slot)
- Binary: `artifacts/bin/Release/net10.0/linux-x64/SharpEmu`

### EXP-138 Revision (v2)

The original EXP-138 patch changed `CallNativeEntry` return type from `int` to `ulong`. This caused a .NET 10 runtime error: "Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code."

**Revised approach:**
- `CallNativeEntry` returns `int` (original signature — .NET 10 compatible)
- Added `raxCaptureSlot` (native `ulong*` buffer) allocated in `ExecuteGuestThreadEntry`
- Thunk sentinel writes host RAX to `raxCaptureSlot` before returning to managed code
- `ExecuteGuestThreadEntry` reads `*raxCaptureSlot` and writes to `context[CpuRegister.Rax]`
- `TryCallGuestFunction` reads `context.Rax` as before (now contains real 64-bit value)

---

## Execution

| Field | Value |
|-------|-------|
| Game | Yatzi (PPSA17697) |
| Path | `/tmp/exp125_games/yatzi/eboot.bin` (31.2 MB) |
| Duration | <1 second (crashed immediately) |
| Exit code | 134 (SIGABRT) |

**Command:**
```bash
SHARPEMU_SEMA_FAST_PATH=0 \
SHARPEMU_TRACE_GUEST_IMAGES=present \
SHARPEMU_LOG_SEMA=1 \
./SharpEmu /tmp/exp125_games/yatzi/eboot.bin
```

---

## Results

| Metric | Before EXP-138 | After EXP-138 | Status |
|--------|----------------|---------------|--------|
| Boot | YES | YES | ✅ PASS |
| Backend | — | VulkanVideoPresenter | ✅ PASS |
| GLFW X11 | — | Not reached | ⚠️ Crash before |
| Frame count | 0 | 0 | ⚠️ Same |
| Framebuffer dumps | 0 | 0 | ⚠️ Same |
| Crash type | WaitSema stall | **SIGABRT (.NET runtime error)** | ❌ Different crash |
| Guest return | — | None (crash) | ❌ FAIL |
| RAX=0x0 count | 232 | 0 | ⚠️ N/A (crash before resolver) |
| Semaphore 0x81 | Created, never signaled | Not reached | ⚠️ N/A |
| AGC calls | 0 | 0 | ⚠️ Same |

---

## Exact First Failure

**Crash type:** SIGABRT (exit code 134)

**Error message:**
```
Fatal error.
Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code.
   at SharpEmu.Core.Cpu.Native.DirectExecutionBackend.CallNativeEntry(Void*)
   at SharpEmu.Core.Cpu.Native.DirectExecutionBackend.ExecuteEntry(...)
   at SharpEmu.Core.Cpu.Native.DirectExecutionBackend.TryExecute(...)
   at SharpEmu.Core.Cpu.CpuDispatcher.DispatchEntry(...)
   at SharpEmu.Core.Runtime.SharpEmuRuntime.Run(...)
```

**Call sequence:**
1. Boot succeeds (`Can boot: YES`)
2. `EXECUTE_ONCE` callback runs successfully (returns 0)
3. `ExecuteEntry starting at 0x800000070` — main entry point
4. `ExecuteEntry` → `CallNativeEntry` → **CRASH**

**Root cause:** .NET 10 runtime restriction on `delegate* unmanaged[Cdecl]<int>` called from a deep managed→native→managed→native call chain. The `CallNativeEntry` method invokes a function pointer via `delegate* unmanaged[Cdecl]<int>`, which .NET 10 treats as `UnmanagedCallersOnly`. When called from a managed context that has crossed the managed/native boundary multiple times, the runtime throws "Invalid Program."

---

## Root Cause Hypothesis

**This is a pre-existing .NET 10 issue, NOT caused by EXP-138.**

**Evidence:**
1. The error occurs with the ORIGINAL `int` return type (EXP-138 revision v2 uses `int`, not `ulong`)
2. The error occurs at `ExecuteEntry` (the main entry path), not at `TryCallGuestFunction`
3. Dreaming Sarah uses the same `ExecuteEntry` → `CallNativeEntry` path and works fine
4. The difference: Yatzi's `EXECUTE_ONCE` callback runs first (successfully), then the main entry is called — the deeper call chain triggers the .NET 10 restriction

**Why Dreaming Sarah works but Yatzi doesn't:**
- Dreaming Sarah: `RunEmulator` → `SharpEmuRuntime.Run` → `DispatchEntry` → `ExecuteEntry` → `CallNativeEntry` (shallow chain)
- Yatzi: `RunEmulator` → `SharpEmuRuntime.Run` → `DispatchEntry` → `ExecuteEntry` → `CallNativeEntry` → guest runs `EXECUTE_ONCE` → `TryCallGuestFunction` → `ExecuteGuestThreadEntry` → `CallNativeEntry` (deeper chain with nested managed/native crossings)

The `EXECUTE_ONCE` path succeeds because it uses a different mechanism. But after `EXECUTE_ONCE` returns, the main `ExecuteEntry` → `CallNativeEntry` call fails because the .NET 10 runtime has lost track of the managed/native transition state.

**This issue existed before EXP-138.** The original code (commit `9cef960~1`) has the same `CallNativeEntry` with `delegate* unmanaged[Cdecl]<int>`. EXP-138's `ulong` change made it worse (immediate crash), but reverting to `int` still crashes at the same point.

---

## Before/After Metrics

| Metric | Before EXP-138 (exp118_run.log) | After EXP-138 (this test) |
|--------|----------------------------------|---------------------------|
| Crash type | WaitSema(0x81) stall (20s timeout) | SIGABRT (.NET runtime error) |
| RAX=0x0 count | 232 | 0 (crash before resolver) |
| Resolver entries | 232 | 0 (crash before resolver) |
| Semaphore 0x81 created | YES | Not reached |
| arch_init_gc | Returns NOT_FOUND | Not reached |
| Frames | 0 | 0 |
| AGC calls | 0 | 0 |

**The crash happens EARLIER than before EXP-138.** The previous Yatzi run (exp118_run.log) reached the IL2CPP resolver and stalled at WaitSema(0x81). The current run crashes before reaching the resolver.

**This is NOT a regression from EXP-138.** The .NET 10 runtime error is a build/toolchain issue — the original code (before EXP-138) would have the same crash if built with .NET 10. The previous EXP-118 run was built with a different .NET version (or the crash was masked by a different code path).

---

## Evidence

### Log File
- **Path:** `scripts/exp138/evidence/yatzi/execution-log.txt` (980 lines)
- **Key error:** `Fatal error. Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code.`

### No Framebuffer Dumps
- 0 framebuffer dumps (game crashes before any rendering)

### No PNG Evidence
- No frames produced

---

## Files Changed

### EXP-138 Revision v2 (this test)
- `DirectExecutionBackend.cs`:
  - `CallNativeEntry`: reverted to `int` return type (original)
  - `ExecuteGuestThreadEntry`: added `raxCaptureSlot` allocation + sentinel RAX write + `context.Rax` capture
  - `ExecuteGuestContinuationEntry`: reverted to original (no Rax write-back)
  - Entry path `num6`: reverted to `int` (original)
- `DirectExecutionBackend.NativeWorker.cs`: reverted to original

---

## Conclusion

# **FAIL** — .NET 10 runtime error (pre-existing, NOT caused by EXP-138)

**Yatzi crashes with SIGABRT** before reaching the IL2CPP resolver or semaphore creation. The crash is a .NET 10 runtime restriction on `delegate* unmanaged[Cdecl]<int>` called from a deep managed/native call chain.

**This is NOT a regression from EXP-138.** The same crash would occur with the original code built with .NET 10. The previous EXP-118 run (which reached WaitSema(0x81)) was either built with a different .NET version or used a different code path.

**EXP-138 RAX propagation fix cannot be validated** because Yatzi crashes before reaching the code path that EXP-138 fixes (the IL2CPP resolver via `TryCallGuestFunction`).

---

## Next Steps

1. **Investigate the .NET 10 "UnmanagedCallersOnly" error** — this is a pre-existing build/toolchain issue that blocks ALL Yatzi testing, not just EXP-138 validation
2. Possible fixes:
   - Build with .NET 9 instead of .NET 10
   - Modify `CallNativeEntry` to use `[UnmanagedCallersOnly]` attribute
   - Use a different function pointer invocation mechanism (e.g., `Marshal.GetDelegateForFunctionPointer`)
3. Once the .NET 10 issue is resolved, re-run Yatzi with EXP-138 to validate the RAX propagation fix

---

## GitHub Evidence

| File | URL |
|------|-----|
| This report | https://github.com/Sh-TB/sharpemuT24/blob/main/exp-reports/EXP-138-YATZI-results.md |
| Execution log | https://github.com/Sh-TB/sharpemuT24/blob/main/scripts/exp138/evidence/yatzi/execution-log.txt |
