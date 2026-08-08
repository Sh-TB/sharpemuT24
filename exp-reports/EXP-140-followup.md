# EXP-140 Follow-up — Native Resolver Path + global-metadata.dat Location Fix

**Date:** 2026-08-04
**Status:** ✅ ORIGINAL EXP-124 DEADLOCK REACHED — all blockers resolved

---

## Summary

The IL2CPP initialization crash (SIGSEGV at NULL+0x98) was caused by `global-metadata.dat` being in the wrong directory. The file was at `Media/Modules/global-metadata.dat` but the IL2CPP runtime expects it at `Media/Metadata/global-metadata.dat`.

After fixing the file location:
- SIGSEGV: **GONE** (0 occurrences)
- IL2CPP metadata: **LOADED** successfully
- Original EXP-124 deadlock: **REACHED** (WaitSema(0x81) stall)
- Exit code: 4 (stall timeout)

---

## Native Resolver Path Confirmed

### Old run (no PRXs, EXP-118):
- `r8mvOaWdi28` called as Import#2083 → HLE dispatch → `DispatchIl2CppApiLookupSymbol` → `TryCallGuestFunction(0x804ED9B90)` → BST resolver → 232 symbols resolved
- EXP-138 RAX propagation bug: resolver returned 0 (RAX not propagated)

### New run (PRXs loaded, EXP-139.4+):
- `r8mvOaWdi28` is **direct-bridged** to the real PRX function (not HLE-dispatched)
- The guest calls the resolver **natively** (no `TryCallGuestFunction` involved)
- The BST resolver at `0x804ED9B90` executes directly in the guest's native code
- Return values go directly to the guest in RAX — **no HLE interception**
- No `RESOLVER-TRACE Entry/Exit` lines because the resolver doesn't go through HLE

### This is EXPECTED behavior:
When PRXs are properly loaded, the IL2CPP runtime uses its own native resolver path. The HLE resolver dispatch (`DispatchIl2CppApiLookupSymbol`) was a **fallback** for when PRXs were not loaded. The native path is the CORRECT path.

### EXP-138 RAX propagation:
- **NOT needed** for the native resolver path — the resolver runs natively, RAX goes directly to the guest
- EXP-138 was designed for the HLE path (`TryCallGuestFunction`) which is no longer used when PRXs are loaded
- EXP-138 is **neutral** — it doesn't help or hurt the native path

---

## global-metadata.dat Location

### Wrong location (EXP-139.4):
```
/tmp/exp125_games/yatzi/Media/Modules/global-metadata.dat
```
→ IL2CPP runtime couldn't find metadata → type system uninitialized → NULL pointers → SIGSEGV

### Correct location (EXP-140 follow-up):
```
/tmp/exp125_games/yatzi/Media/Metadata/global-metadata.dat
```
→ IL2CPP runtime found metadata → type system initialized → reached WaitSema(0x81) deadlock

### Evidence:
```
[LOADER][TRACE] fopen: guest='/app0/Media/boot.config' -> FAILED (file not found)
Boot Dependency Report:
  Media/Metadata/global-metadata.dat — Exists: YES
```

---

## Current State: EXP-124 Deadlock Reached

### Stall snapshot (identical to EXP-118/EXP-124):
```
Stall snapshot: rip=0x00006FFFFD001150 rdi=0x00006FFF00000081
Stall import-stub: nid=Zxa0VhQVTsk -> libKernel:sceKernelWaitSema
Stall stack: [rsp]=0x0000000804F6E9EB
```

### Worker threads (identical to EXP-118/EXP-124):
- 13 `AssetGarbageCollectorHelper` workers blocked on 0x5C-0x74
- 1 `Thread-XXX` blocked on 0x83 (SuspendSemaphore)
- Main thread blocked on 0x81 (Baselib_SystemSemaphore)

### This is the EXACT same deadlock as EXP-118/EXP-124.

---

## Root Cause Classification

### Previous blockers (ALL RESOLVED):
1. ✅ PRX files not loaded → fixed by directory structure (EXP-139.4)
2. ✅ .NET 10 "Invalid Program" → was secondary error from SIGSEGV at unmapped resolver address
3. ✅ SIGSEGV at NULL+0x98 → was caused by missing global-metadata.dat
4. ✅ global-metadata.dat wrong location → fixed by moving to `Media/Metadata/`

### Current blocker:
- **WaitSema(0x81) deadlock** — the original EXP-124 issue
- The bootstrap job that should signal semaphore 0x81 is never submitted
- This is the SAME issue investigated in EXP-124 through EXP-137

### Reconnecting with EXP-026→028:
- The BST resolver is NOT involved in the native path (PRXs loaded)
- EXP-026's "232 NULL returns" was from the HLE fallback path (no PRXs)
- The native resolver path works correctly — no RAX propagation issue
- The deadlock is downstream of the resolver — it's in the Unity Job System bootstrap

---

## Files Changed

**NONE.** Only the game dump directory structure was fixed (moving `global-metadata.dat` to `Media/Metadata/`).

---

## Next Steps

The investigation is back to EXP-124's WaitSema(0x81) deadlock, but now with:
- All PRXs properly loaded ✅
- global-metadata.dat properly loaded ✅
- IL2CPP type system initialized ✅
- Native resolver path working ✅

The next investigation should focus on:
1. Why the bootstrap job is never submitted (EXP-127/128)
2. Whether `arch_init_gc` (NID `XAKDgxcra6k`) is still returning NOT_FOUND
3. Whether the `arch_raise_user` (NID `J3edELK4FvM`) abort path is triggered
4. Whether missing HLE exports (`sceKernelVirtualQuery`, `sceKernelDirectMemoryQuery`) affect IL2CPP initialization

---

## Golden Gate Status

Dreaming Sarah: ✅ PASS (23/23/744 colors) — no regression
