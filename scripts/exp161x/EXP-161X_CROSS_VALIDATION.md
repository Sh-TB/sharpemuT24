# EXP-161X — Cross Validation: Chain A vs Chain B

**Date:** 2026-08-07
**Status:** TEST ONLY — No emulator behavior changes
**Rule:** Runtime evidence decides

---

## Test 1: INT3 on 0x801E518C8 Writes

### Static Analysis: Write Instructions to 0x801E518C8

| Address | Instruction | Value Written |
|---------|-------------|---------------|
| 0x800804175 | `mov qword [0x801E518C8], 0` | **0** (clear) |
| 0x80080455E | `mov [0x801E518C8], r15` | r15 (initialization) |
| 0x80080459B | `mov qword [0x801E518C8], 0` | **0** (clear) |

### Runtime Results

| Slot | Address | Hit? | [0x801E518C8] at hit |
|------|---------|------|---------------------|
| 1 | 0x800804175 (clear) | **YES** | 0x0000000000000000 (before write) |
| 2 | 0x80080455E (init r15) | **NO** | — |
| 3 | 0x8013EB6B0 (func entry) | **YES** | 0x0000000000000000 (still 0) |

### Analysis

- The **clear** instruction at 0x800804175 IS executed — writes 0 to the global
- The **initialization** instruction at 0x80080455E is **NEVER executed**
- When function 0x8013EB6B0 is entered, [0x801E518C8] is still 0

**The initialization write (mov [0x801E518C8], r15) is never reached.** The global stays at 0.

---

## Test 2: INT3 on 0x801D1E558

### Static Analysis

**0x801D1E558 is NOT MAPPED in any eboot or PRX segment.**

The address (eboot vaddr 0x1D1E558) falls in a GAP between:
- Segment ending at 0x1D1C450
- Segment starting at 0x1D20000

**0 writes, 0 reads in both eboot and PRX.**

### Decoder's Claimed Read Addresses

The decoder claims reads at:
- 0x80135DC74: `mov rcx, [0x801D1E558]`
- 0x80135DC81: `mov rax, [rcx]`

**Verification:** The bytes at 0x80135DC74 are `02 B4 00 48 C7 05...` — byte 0 is 0x02 (ADD opcode), NOT 0x48 (REX prefix). This is NOT a `mov rcx, [rip+disp32]` instruction. The decoder used incorrect ELF offset mapping.

### Conclusion

**Chain B (0x801D1E558) is INVALID.** The address is unmapped, and the decoder's claimed read instructions are at wrong offsets.

---

## Test 3: Timing Comparison

### Does 0x801D1E558 initialization happen before 0x8013EB6B0?

**N/A — 0x801D1E558 is unmapped. No initialization can occur.**

### Does 0x801E518C8 initialization happen before 0x8013EB6B0?

**NO.** The initialization write (0x80080455E: `mov [0x801E518C8], r15`) is NEVER executed. Only the clear write (0x800804175: `mov qword [0x801E518C8], 0`) executes, and it runs BEFORE function 0x8013EB6B0 is entered. When 0x8013EB6B0 is entered, [0x801E518C8] = 0.

---

## Test 4: PRX Analysis

### PRX references to target addresses

| Address | PRX Writes | PRX Reads | PRX Constants |
|---------|-----------|-----------|---------------|
| 0x801E518C8 | 0 | 0 | 0 |
| 0x801D1E558 | 0 | 0 | 0 |
| 0x801E51240 | 0 | 0 | 0 |

**The PRX does NOT reference any of these addresses.** All three are eboot-only globals.

---

## Test 5: Cross-Validation Summary

### Chain A (0x801E518C8) — CONFIRMED

- Address IS mapped in eboot BSS
- 10 write instructions exist (5 unique, mix of clear-to-0 and init-from-r15)
- The clear write IS executed at runtime
- The init write (mov [0x801E518C8], r15) is NEVER executed
- When function 0x8013EB6B0 runs, [0x801E518C8] = 0
- This causes the early branch (je) that skips the store to 0x801E51240

### Chain B (0x801D1E558) — REJECTED

- Address is NOT MAPPED in any segment
- 0 writes, 0 reads in both binaries
- Decoder's claimed read instructions are at wrong file offsets (byte 0x02, not 0x48)
- The 25,580 reads claim is impossible — the address doesn't exist

### Winning Chain: A (0x801E518C8)

Runtime evidence confirms Chain A. Chain B is invalid.

---

## Root Cause Chain (Updated)

```
0x801E518C8 is in BSS (initial value 0)
  ↓
Clear instruction (0x800804175: mov qword [0x801E518C8], 0) executes — keeps it 0
  ↓
Init instruction (0x80080455E: mov [0x801E518C8], r15) NEVER executes
  ↓
[0x801E518C8] = 0 when function 0x8013EB6B0 is entered
  ↓
mov r14, [rbx] → r14 = 0 (where rbx = 0x801E518C8)
  ↓
test r14, r14 → ZF=1
  ↓
je +0x101 (TAKEN) → early exit
  ↓
Store to 0x801E51240 NEVER executes
  ↓
[0x801E51240] = NULL
  ↓
84 functions that read [0x801E51240] get NULL
  ↓
Functions skip initialization (potentially including PlayerLoop)
  ↓
WaitSema(0x81) deadlock
```

### Next Investigation Target

**Why is the init write at 0x80080455E (mov [0x801E518C8], r15) never executed?**

This instruction is in a function that is either:
1. Never called
2. Called but exits before reaching this instruction
3. Behind a conditional branch that is not taken

Finding why this initialization is skipped will reveal the TRUE first divergence point.

---

## Artifacts

- `/home/z/my-project/scripts/exp161x/exp161x_static.py` — Static cross-validation
- `/tmp/exp161x_chain_a.log` — Runtime INT3 trace for 0x801E518C8 writes
- `/home/z/my-project/scripts/exp161x/EXP-161X_CROSS_VALIDATION.md` — This report
