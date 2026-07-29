# EXP-032 — TryCallGuestFunction / Native Execution Context Investigation

**Date:** 2026-07-29
**Status:** ROOT CAUSE FOUND — 100% confidence

## Root Cause

**TryCallGuestFunction reads `context[CpuRegister.Rax]` instead of `nativeReturn`**

The resolver DOES execute correctly inside `ExecuteGuestThreadEntry`:
- The native thunk calls the resolver at 0x804ED9B90
- The resolver traverses the BST tree, finds the candidate, calls strcmp
- The resolver returns the correct `func_impl` pointer in RAX
- `CallNativeEntry` captures this as `nativeReturn` (int)

BUT: `ExecuteGuestThreadEntry` does NOT write `nativeReturn` back to `CpuContext`.
`TryCallGuestFunction` then reads `context[CpuRegister.Rax]` (which is still 0)
instead of using `nativeReturn`.

## Evidence

```
[EXP032-NATIVE] nativeReturn=0x04ED85D0 contextRax=0x0000000000000000
[EXP032-NATIVE] nativeReturn=0x04ED8600 contextRax=0x0000000000000000
[EXP032-NATIVE] nativeReturn=0x04ED86D0 contextRax=0x0000000000000000
```

- `nativeReturn=0x04ED85D0` = lower 32 bits of `0x804ED85D0` (func_impl for il2cpp_init) ✅
- `contextRax=0x0000000000000000` = CpuContext.Rax was NEVER updated ❌

## The Bug Location

File: `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs`

In `ExecuteGuestThreadEntry` (line ~5072):
```csharp
var nativeReturn = CallNativeEntry(ptr);
// nativeReturn has the resolver's RAX (e.g., 0x04ED85D0)
// BUT: context[CpuRegister.Rax] is NEVER set to nativeReturn!
reason = $"returned 0x{nativeReturn:X8}";
return GuestNativeCallExitReason.Returned;
```

In `TryCallGuestFunction` (line ~3502):
```csharp
returnValue = context[CpuRegister.Rax];
// Reads 0 (initial value), NOT nativeReturn!
```

## The Fix

In `ExecuteGuestThreadEntry`, after `CallNativeEntry` returns:
```csharp
context[CpuRegister.Rax] = (ulong)(uint)nativeReturn;
```

This writes the resolver's return value to the CpuContext, so
`TryCallGuestFunction` can read it correctly.

## Answer to EXP-032 Question

**B) CpuContext register propagation failure**

The resolver executes correctly (nativeReturn has the correct value),
but the return value is lost because CpuContext.Rax is never updated
from nativeReturn.
