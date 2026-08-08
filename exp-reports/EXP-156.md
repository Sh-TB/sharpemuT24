# EXP-156 — EXP-138 Fix Validation Report

**Date:** 2026-08-06
**Status:** EXP-138 fix is NOT SUFFICIENT — deadlock persists. Resolver runs natively, not through TryCallGuestFunction.
**Rule:** TEST ONLY — no code changes, no HLE, no architecture modifications.

---

## 1. Build Status: SUCCEEDED

- Dotnet SDK: 10.0.302 (installed via dotnet-install.sh)
- Build: 0 errors, 14 warnings
- Output: SharpEmu executable at artifacts/bin/Release/net10.0/linux-x64/SharpEmu

## 2. EXP-138 Fix Detected: YES

Source verified at DirectExecutionBackend.cs:4891-5106 (raxCaptureSlot).

## 3. RAX Comparison: N/A

The new build does not produce EXP028/EXP032 resolver traces because the IL2CPP resolver runs NATIVELY inside the PRX, not through TryCallGuestFunction. The resolver NID r8mvOaWdi28 does NOT appear in the import trace.

## 4. GOT Slot: N/A

No GOT traces in new build.

## 5. IL2CPP Init: SAME AS BEFORE

dt_init returns 0, BST populated, but type init flags never set.

## 6. PlayerLoop: NOT REACHED

0 VideoOut/Agc calls, same deadlock.

## 7. Final Conclusion: B) EXP-138 fix NOT SUFFICIENT

The EXP-138 fix is correctly implemented but does not resolve the deadlock because:
1. The resolver runs NATIVELY (not through TryCallGuestFunction)
2. EXP-138 only affects TryCallGuestFunction return propagation
3. The RAX corruption from EXP-118 was in the OLD HLE-dispatched resolver path
4. The deadlock is IDENTICAL (same RIP, same semaphore 0x81)

### Exact Next Divergence Point:
PlayerLoop registration is SKIPPED during IL2CPP type initialization. The type init flags (0x808D67B98, 0x808D67BB8) are NEVER set because the writer functions have chicken-and-egg guards.
