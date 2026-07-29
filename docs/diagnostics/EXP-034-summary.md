# EXP-034 — IL2CPP Fake Heap Investigation

**Date:** 2026-07-29
**Status:** Findings documented, next blocker identified

## Summary

The IL2CPP fake heap stubs return 0 for most API calls. After EXP-032 fix,
the resolver correctly returns real func_impl pointers (232/232 non-zero).
The wrapper stores them in global variables (verified: 10/10 globals populated).

## Key Findings

1. **Globals ARE populated:** After resolver completes, global variables at
   0x801ED6320+ contain real func_impl pointers (e.g., 0x804ED85D0 for il2cpp_init).

2. **Fake heap stubs are still used for import resolution:** TryResolveIl2CppApiAddress
   returns fake stubs for il2cpp_* functions during SetupImportStubs (before resolver runs).

3. **Import stub re-patching failed:** 0/232 stubs patched because il2cpp_* functions
   are NOT in _importEntries (they're resolved through the wrapper, not import stubs).

4. **NULL execute faults still hit 100000:** The real il2cpp_init code (at 0x804ED85D0)
   runs but calls internal functions that return 0 (from fake heap or unimplemented APIs),
   then calls through those 0 return values → NULL execute fault.

## Architecture

```
EBOOT wrapper (0x8013FB0B0)
  → calls resolver (r8mvOaWdi28) 232 times
  → stores results in 125 global variables (0x801ED6320+)
  → game calls il2cpp_* through globals → real func_impl (0x804ED85D0+)
  → real il2cpp_init runs → calls internal functions
  → some internal calls return 0 → NULL execute fault → recovery → repeat
  → after 100000 recoveries → crash
```

## Next Step (EXP-035)

The real IL2CPP runtime code needs proper runtime support. The fake heap
provides fake objects (Domain, Thread, Class, etc.) but the real code
needs:
- Real memory allocation (malloc/free)
- Real thread management
- Real garbage collection
- Real metadata loading (global-metadata.dat)

Options:
A. Implement real IL2CPP API functions for the most-called APIs
B. Trace which specific il2cpp_* calls return 0 and cause NULL calls
C. Load and parse global-metadata.dat for real class/method info
