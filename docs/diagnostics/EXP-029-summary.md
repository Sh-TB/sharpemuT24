# EXP-029 — Native strcmp Investigation Summary

**Date:** 2026-07-29
**Status:** ROOT CAUSE CONFIRMED
**Confidence:** HIGH (95%)

---

## Root Cause

The strcmp GOT slot (0x808924090) points to FREED memory (0x6FFFFD0005C0).
The strcmp intrinsic stub was allocated via VirtualAlloc during module setup,
used to patch the GOT, then the memory was freed. The GOT was never updated
to point to a persistent implementation.

When the resolver calls strcmp through PLT -> GOT -> 0x6FFFFD0005C0,
it jumps to UNMAPPED memory, causing a SIGSEGV that is silently recovered
by SharpEmu's POSIX signal handler. Recovery sets RAX=0, so the resolver
returns 0 instead of the correct func_impl pointer.

## Evidence

1. strcmp intrinsic code: CORRECT (isolated test: 10/10 match with libc)
2. GOT slot value: 0x6FFFFD0005C0 (readable, points to freed memory)
3. Memory map check: 0x6FFFFD0005C0 NOT in /proc/self/maps (UNMAPPED)
4. Intrinsic address 0x7F65ABF55000: also NOT in /proc/self/maps (UNMAPPED)
5. INTRINSIC-CHECK: intrinsic re-patched 5 times (once per module load pass)
6. Resolver error='': SIGSEGV silently recovered, RAX=0 returned

## First Divergence

RIP: 0x804ED9BF0 (call strcmp via PLT -> GOT -> freed memory)
Expected: strcmp returns 0 for equal strings → return func_impl
Actual: SIGSEGV at unmapped address → silent recovery → RAX=0 → return 0

## Next Step

Fix: Make intrinsic stub memory persistent OR use HLE strcmp for PRX imports.
