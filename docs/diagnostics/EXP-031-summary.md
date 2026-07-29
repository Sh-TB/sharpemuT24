# EXP-031 — Inner CpuContext strcmp Dispatch Investigation

**Date:** 2026-07-29
**Status:** ROOT CAUSE NARROWED — not freed memory, not inaccessible memory

## Summary

EXP-031 investigated why the resolver's strcmp calls inside TryCallGuestFunction
return 0 instead of the correct comparison result.

## Tests Performed

### Task 1: PLT/GOT trace
- Added EXP031-STRCMP-DISPATCH trace for Ovb2dSJOAuE (strcmp NID)
- Result: **0 dispatches** — strcmp NID is NEVER dispatched through HLE
- The strcmp intrinsic IS being used (not HLE path)

### Task 2: Resolver-specific strcmp tracing
- Added EXP031-RESOLVER-STRCMP filter for 0x200... (BST) and 0x804... (PRX) addresses
- Result: **0 resolver-specific strcmp calls** in HLE handler
- Confirms: resolver's strcmp goes through intrinsic, NOT HLE

### Task 3: Import stub verification
- Read import stub bytes at GOT target (0x6FFFFD0005C0)
- Result: stub contains valid `mov rax, 0x7F66FD76F000; jmp rax`
- Intrinsic address IS present in the stub

### Task 4: Memory free tracing
- Added EXP031-FREE trace to PosixHostMemory.Free
- Result: **0 frees** during Yatzi run
- VirtualFree/Free is NEVER called — intrinsic memory is NOT freed

### Task 5: /proc/self/maps verification
- Checked if intrinsic address is in /proc/self/maps
- Result: NOT FOUND — but this is because /proc/self/maps was read from a
  DIFFERENT process (Python script), not the SharpEmu process
- The /proc/self/maps check was **misleading** — the intrinsic IS valid

## Key Findings

1. **strcmp HLE dispatch is NEVER called** — the intrinsic path is used
2. **Import stub is valid** — contains correct `mov rax, <intrinsic>; jmp rax`
3. **No memory freeing** — VirtualFree is never called during runtime
4. **/proc/self/maps was misleading** — checked from wrong process
5. **Guest memory at 0x200... IS real mmap'd** — PhysicalVirtualMemory uses mmap
6. **DefaultMapSearchBase = 0x2000000000** — BST nodes at 0x2000027440 are in this range

## Revised Root Cause

The root cause is NOT:
- ❌ Freed intrinsic memory (no frees occur)
- ❌ Inaccessible guest memory (0x200... is real mmap'd)
- ❌ Stale GOT pointer (GOT value is stable and valid)
- ❌ Incorrect intrinsic code (tested correct in isolation)

The root cause IS inside TryCallGuestFunction's execution context:
- The resolver runs inside a NEW CpuContext (inner)
- The strcmp intrinsic runs natively on the host CPU
- Something in the execution thunk or context setup causes the
  resolver to return 0

## Next Step (EXP-032)

Add per-instruction tracing INSIDE TryCallGuestFunction:
1. Log the inner context's RAX, RDI, RSI, RIP after ExecuteGuestThreadEntry returns
2. Check if the resolver's strcmp call actually executes or faults
3. Check if the inner context's register state is correct at entry

The most promising approach is to add logging to ExecuteGuestThreadEntry
that captures the exit reason and register state.
