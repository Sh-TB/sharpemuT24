# EXP-030 — Intrinsic Lifetime / GOT Stale Pointer Investigation

**Date:** 2026-07-29
**Status:** PARTIALLY RESOLVED — root cause revised

## What was tried

### Option A: Skip ClearImportHandlerTrampolines in SetupImportStubs
- **Result:** Did NOT fix the issue. Resolver still returns 0/232.
- The intrinsic memory was still unmapped even without explicit freeing.
- Root cause: the /proc/self/maps check was misleading — 0x6FFFFD0005C0 is
  GUEST memory (managed by SharpEmu's VirtualMemory), not host memory.

### Option C: Route strcmp through HLE path (skip intrinsic)
- **Result:** Did NOT fix the issue. Resolver still returns 0/232.
- HLE strcmp handler IS being called (609 STRCMP-TRACE lines).
- But the STRCMP-TRACE addresses (0x808...) are from the EBOOT, not the PRX resolver.
- The resolver's own strcmp calls may not be reaching the HLE handler.

### Option A+C combined
- **Result:** Did NOT fix the issue. Still 0/232.

## Revised root cause

The original EXP-029 hypothesis (stale GOT pointer to freed memory) was
INCORRECT. The GOT value 0x6FFFFD0005C0 is a valid GUEST memory address
(import stub), not a host address. The /proc/self/maps check was misleading
because guest memory is managed separately by SharpEmu's VirtualMemory.

The real issue is more subtle:
1. The resolver runs inside TryCallGuestFunction (new CpuContext)
2. The resolver's strcmp PLT at 0x804fc2d40 goes through GOT 0x808924090
3. The GOT points to an import stub at 0x6FFFFD0005C0 (guest memory)
4. The import stub jumps to a trampoline (HLE or intrinsic)
5. The HLE strcmp handler IS called (609 STRCMP-TRACE lines)
6. But the STRCMP-TRACE addresses suggest the HLE handler is called from
   the EBOOT context, not from the PRX resolver context
7. The resolver's own strcmp calls may be going through a different path
   or the return value is not propagating correctly

## Key evidence

- PLT check: 0x804fc2d40 IS a PLT entry (FF 25 = jmp [rip+offset])
- STRCMP-TRACE: 609 calls logged, but addresses are 0x808... (EBOOT), not 0x200... (BST)
- GOT value: 0x6FFFFD0005C0 (guest memory, NOT host — /proc/self/maps was misleading)
- strcmp intrinsic: CORRECT (10/10 isolated tests match libc)
- Resolver: still returns 0/232 despite HLE strcmp being active

## Next step

Need to determine WHY the resolver's strcmp calls don't reach the HLE handler
(or if they do, why the return value doesn't propagate). Possible causes:
1. The import stub at 0x6FFFFD0005C0 was overwritten by a later module load
2. The HLE trampoline dispatch doesn't work inside TryCallGuestFunction
3. The resolver's PLT goes to a different GOT slot than 0x808924090

The most promising next step is to add a trace INSIDE TryCallGuestFunction
that logs whether the HLE strcmp handler is called with BST tree addresses
(0x200...) as arguments.
