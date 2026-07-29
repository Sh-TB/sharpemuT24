# EXP-033 — Post-Resolver Boot Investigation

**Date:** 2026-07-29
**Status:** Next blocker identified

## Summary

After EXP-032 fix (resolver returns correct func_impl), Yatzi progresses
past IL2CPP resolver initialization but crashes due to NULL execute fault
recovery limit (100000) being exceeded.

## Root Cause of Crash

The IL2CPP fake heap stubs return 0 for all function calls. The game's
AssetGarbageCollectorHelper threads call IL2CPP API functions that return 0
(from fake heap stubs), then call through those 0 return values → NULL
execute fault → recovered → game continues → repeat.

After 100000 recoveries, TryRecoverNullExecuteFault returns false →
SIGSEGV not recovered → process killed.

## EXP-033 Details

```
Module: Il2cppUserAssemblies.prx (IL2CPP fake heap)
NID: N/A (not a missing HLE function)
Function: IL2CPP API functions called through fake heap stubs
Caller: AssetGarbageCollectorHelper threads (entry=0x800BB06A0)
Guest RIP: 0x0000000000000000 (NULL)
Reason: IL2CPP fake heap returns 0 → game calls through 0 → NULL fault
Category: B) Unity runtime dependency
```

## Boot Progress (before crash)

1. ✅ ELF loaded
2. ✅ Kernel initialized
3. ✅ HLE ready
4. ✅ IL2CPP resolver initialized (232/232 symbols resolved)
5. ✅ GOT populated with real func_impl pointers
6. ✅ AssetGarbageCollectorHelper threads spawned
7. ❌ NULL execute fault limit exceeded (100000+)

## Next Step (EXP-034)

The IL2CPP fake heap needs to be replaced with real IL2CPP API
implementations. The resolver now returns correct func_impl pointers
(e.g., 0x804ED85D0 for il2cpp_init), but the fake heap stubs still
return 0 for all other IL2CPP API calls.

Options:
A. Route ALL IL2CPP API calls through the resolver results (not fake heap)
B. Implement real IL2CPP API functions for the most-called APIs
C. Increase the NULL execute fault recovery limit (temporary workaround)
