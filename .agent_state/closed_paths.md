# Closed Paths — SharpEmuT24 Investigation

**Last updated:** 2026-08-04

These hypotheses have been tested and REJECTED with concrete evidence. Do NOT re-investigate without new evidence.

---

## CPU / Backend Layer

### EXP-027 — CPU instruction correctness
- **Theory:** cmovns/test/lea/branch logic emulation has a bug
- **Evidence:** 768/768 fuzz PASS against Unicorn gold standard
- **Status:** CLOSED

### EXP-026 — BST resolver algorithm
- **Theory:** Red-Black tree has violations causing resolver to return 0
- **Evidence:** 239 nodes, 0 violations, RB tree valid, inverted tree correct
- **Status:** CLOSED (algorithm correct; root cause was elsewhere — see EXP-137/138)

### EXP-028 — Synthetic resolver
- **Theory:** Synthetic resolver fails to resolve some symbols
- **Evidence:** 239/239 symbol resolve PASS
- **Status:** CLOSED

---

## Loader / RELA Layer

### EXP-131 — TryLoadTableBytes failure
- **Theory:** TryLoadTableBytes fails for [---] segment, RELA table not applied
- **Evidence:** Runtime log confirms "loaded from guest memory at 0x801F435F0", 50,450 relocations processed
- **Rejected by:** EXP-132
- **Status:** CLOSED

### EXP-130 — Producer pointer NULL in file
- **Theory:** File value at offset 0x1d00cb0 = 0x0 means producer pointer is NULL
- **Evidence:** File value is pre-relocation (expected 0x0); SharpEmu applies relocations to guest memory, not file
- **Rejected by:** EXP-132
- **Status:** CLOSED

### EXP-133 — Producer at 0x801028d80
- **Theory:** Function at 0x801028d80 is the producer that should signal semaphore 0x81
- **Evidence:** Zero direct callers, zero LEA references, zero reads from 0x1cfccb0 — unreachable dead code
- **Status:** CLOSED

---

## IL2CPP Layer

### EXP-038 — SharpEmu passes rdx=0 to PRX DT_INIT
- **Theory:** SharpEmu passes wrong rdx value to PRX module_start
- **Evidence:** rdx=0 is correct for this PRX
- **Rejected by:** EXP-039
- **Status:** CLOSED

### EXP-052 — Static table at 0x1CC0080 is Il2CppMetadataRegistration
- **Theory:** Static table is metadata registration
- **Evidence:** Static table is string fragment pool, not metadata
- **Rejected by:** EXP-053
- **Status:** CLOSED

### EXP-055 — PRX DT_INIT is INVALID
- **Theory:** PRX DT_INIT (imageBase+0x10) is ELF padding, would crash
- **Evidence:** All 3 PRXs had module_start successfully dispatched and returned 0 (exp118_run.log:468-933)
- **Rejected by:** EXP-137 Phase 6-D
- **Status:** CLOSED (OVERTURNED)

### EXP-135 — [r14+0x90] never incremented by any binary code
- **Theory:** No producer increment exists, missing HLE primitive
- **Evidence:** Producer `inc dword [r14+0x90]` EXISTS at eboot.bin @ 0x159d52 in func@0x159cd0
- **Rejected by:** EXP-137 Phase 2C
- **Status:** CLOSED (OVERTURNED — EXP-135 only scanned PRX modules, missed eboot.bin)

---

## Semaphore / Threading Layer

### EXP-072 — 9-byte NOP insufficient
- **Theory:** 9-byte NOP (cmp+jne) would fix SignalSema
- **Evidence:** Didn't NOP unconditional jmp at 0x800AA0210; SignalSema reported as "1 call" was patch log msg
- **Rejected by:** EXP-073
- **Status:** CLOSED

### EXP-076 — GPU init missing
- **Theory:** GPU init is the blocker
- **Evidence:** GPU init is NOT the blocker; main thread reaches sceKernelAllocateDirectMemory then stalls on semaphore
- **Rejected by:** EXP-077
- **Status:** CLOSED

### EXP-080 — Odd/even handle split is a real SharpEmu bug
- **Theory:** Odd/even split indicates broken semaphore handling
- **Evidence:** Odd/even split was artifact of earlier NOP-contamination, not a real bug
- **Status:** CLOSED

### EXP-126 — Vblank/event hypothesis
- **Theory:** Vblank or event-flag driven dispatch is missing
- **Evidence:** No sceVideoOutAddVblankEvent, no sceKernelWaitEventFlag in either binary
- **Status:** CLOSED

### EXP-128 — FAST_PATH is a fix (not a bypass)
- **Theory:** FAST_PATH=1 resolves the deadlock
- **Evidence:** FAST_PATH=1 crashes at RIP=0 (NULL call), pipeline counters still zero
- **Rejected by:** EXP-119
- **Status:** CLOSED

### EXP-134 — Dispatch loop reached via corrupted function pointer
- **Theory:** Function pointer corruption prevents dispatch loop from running
- **Evidence:** Direct CALL instruction at 0x804F4560E → 0x804F6E510
- **Status:** CLOSED

### EXP-135 — HLE semaphore ignores guest init count
- **Theory:** HLE forces init=0 regardless of guest request
- **Evidence:** HLE reads init from guest registers correctly; semaphore 0x81 created with init=0 (expected for producer-consumer)
- **Status:** CLOSED

### EXP-137 Phase 3A — ABI mismatch in semaphore exports
- **Theory:** CreateSema/WaitSema/SignalSema have wrong argument order
- **Evidence:** All 3 exports match Sony ABI exactly (rdi/rsi/rdx/rcx/r8/r9 mapping verified)
- **Status:** CLOSED

### EXP-137 Phase 3B — Worker scheduling bug
- **Theory:** Workers created but never scheduled
- **Evidence:** All 14 workers reached entry functions and blocked on WaitSema — not a scheduling bug
- **Status:** CLOSED

---

## HLE Layer

### EXP-136 H7 — sceKernelGetCompiledSdkVersion returning 0
- **Theory:** IL2CPP refuses to init on SDK < 0x0500000
- **Evidence:** Yatzi doesn't import this NID at all
- **Status:** CLOSED

### EXP-136 H7 — sceKernelSyncOnAddressWait broken
- **Theory:** Futex primitive broken, causes IL2CPP starvation
- **Evidence:** Yatzi doesn't import this NID at all
- **Status:** CLOSED

### EXP-136 H4 — _Cnd_init stub breaks Unity Baselib
- **Theory:** C11 threads.h cnd_t lifecycle broken
- **Evidence:** Yatzi uses POSIX pthread_cond_* instead (all implemented)
- **Status:** CLOSED

### EXP-136 H3 — powf/log2f unimplemented cause deadlock
- **Theory:** Math functions missing cause bootstrap failure
- **Evidence:** Called 80K+ times in 2s, loop is finite (~2s), REFUTED by user's non-zero return experiment
- **Rejected by:** CHECKPOINT §17
- **Status:** CLOSED

### EXP-137 Phase 4 — il2cpp_resolve_icall fake-object stub is the cause
- **Theory:** Line 2569 returns fake-object stub for every icall
- **Evidence:** TryResolveIl2CppApiAddress is private and never called — the fake-stub path is dead code
- **Status:** CLOSED (the actual cause is the TryCallGuestFunction RAX bug — see EXP-137 Phase 5, EXP-138)

---

## Summary

**Total closed paths:** 22
**Closed by direct refutation:** 14
**Closed by superseding evidence:** 5
**Closed by overturning (previous rejection was wrong):** 3 (EXP-055, EXP-135 — both overturned BY EXP-137)

**Do NOT re-investigate any of these without new evidence.**
