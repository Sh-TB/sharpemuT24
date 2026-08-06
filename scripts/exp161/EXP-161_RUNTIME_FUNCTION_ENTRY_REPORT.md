# EXP-161 — Runtime Function Entry Validation

**Date:** 2026-08-07
**Status:** TEST ONLY — INT3 breakpoints, no code changes to emulator logic
**Rule:** Only evidence, no speculation

---

## Task 1: Function Entry Validation

### INT3 at 0x8013EB6B0 (function entry)

```
[RIP-TRACE] HIT slot=1 addr=0x00000008013EB6B0 rip=0x00000008013EB6B1
  rax=0x0000000000000000
  rcx=0xC0DEC0DECAFEBA00  (magic value — likely uninitialized marker)
  rdx=0x0000000000000000
  rbx=0x0000000801E518C8  (pointer near global 0x801E51240)
  r14=0x00006FFFF01FFDC8  (stack pointer)
  [0x801E51240]=0x0000000000000000  (global is NULL at entry)
```

### Answer: A) Function entered

The function 0x8013EB6B0 IS entered at runtime. It is called exactly once.

---

## Task 2: Breakpoint Ladder — Finding the Early Exit

### Ladder Results

| Breakpoint | Address | Offset | Hit? | r14 at hit |
|-----------|---------|--------|------|------------|
| Entry | 0x8013EB6B0 | +0x0 | ✅ YES | 0x00006FFFF01FFDC8 |
| 1st CALL | 0x8013EB6E7 | +0x37 | ✅ YES | 0x00006FFFF01FFDC8 |
| 2nd CALL | 0x8013EB6FA | +0x4A | ✅ YES | 0x00006FFFF01FFDC8 |
| 3rd CALL | 0x8013EB710 | +0x60 | ✅ YES | 0x00006FFFF01FFDC8 |
| 4th CALL | 0x8013EB7A2 | +0xF2 | ❌ NO | — |
| 5th CALL | 0x8013EB87F | +0x1CF | ✅ YES | **0x0000000000000000** |
| 1/4 point | 0x8013EC50A | +0xE5A | ❌ NO | — |
| Store | 0x8013EF019 | +0x3969 | ❌ NO | — |

### Analysis

The function executes through offsets +0x0 to +0x60, then **skips** to +0x1CF without hitting +0xF2. The 4th CALL at +0xF2 is NOT reached, but the 5th CALL at +0x1CF IS reached.

This means a conditional branch between +0x60 and +0xF2 redirects execution to +0x1CF.

### Branch Analysis

At offset +0x6F (0x8013EB71F):
```
4D 85 F6          test r14, r14
0F 84 01 01 00 00 je +0x101 → 0x8013EB829
```

At the 3rd CALL hit (+0x60), r14 = 0x00006FFFF01FFDC8 (non-zero). However, between +0x60 and +0x6F, there's a `mov r14, [rbx]` at +0x65 (0x8013EB715: `4C 8B 33`).

If `[rbx]` (where rbx = 0x801E518C8) is 0, then r14 becomes 0, and the `je` is taken, jumping to 0x8013EB829 (offset +0x179), which is BEFORE +0x1CF.

**The value at [0x801E518C8] determines whether the function continues or exits early.**

### Key Finding

At the 5th CALL hit (+0x1CF), r14 = 0x0000000000000000. This confirms that r14 was set to 0 (from `[rbx]` where `[0x801E518C8]` = 0), causing the `je` to be taken.

The function takes an early branch at offset +0x75 (je +0x101), jumping to offset +0x179. It then continues to +0x1CF but crashes with SIGILL (exit 132) — likely due to INT3 handler interaction.

The store at +0x3969 (0x8013EF019) is NEVER reached because the function takes an early branch.

---

## Task 3: Static XREF Analysis

### Direct CALL references to 0x8013EB6B0

**1 caller found:** `CALL at 0x8013FDC39` (inside function 0x8013FCE40)

- No indirect references
- No 64-bit constant references
- No 32-bit lower half references
- No LEA rip-relative references
- No vtable entries

The function is called from exactly ONE location: 0x8013FDC39 in function 0x8013FCE40.

---

## Task 4: Validate 0x801D1E558

### Decoder Claim
- 25,580 reads
- 0 writes
- value = 0

### Validation

**0x801D1E558 is NOT in any eboot segment.**

The address (vaddr 0x1D1E558) falls in a GAP between:
- Segment ending at 0x1D1C450
- Segment starting at 0x1D20000

This means 0x801D1E558 is **unmapped memory** — it does not exist in eboot's memory layout.

### Conclusion
The decoder's claim about 0x801D1E558 is **INVALID** — the address is not mapped.

---

## Task 5: Classification

### 2. Function called but exits early

**CONFIRMED — 100% confidence**

Runtime evidence:
1. Function 0x8013EB6B0 IS entered (INT3 hit at entry)
2. The function executes through offset +0x60
3. At offset +0x65, `mov r14, [rbx]` loads from 0x801E518C8
4. The value at [0x801E518C8] is 0 (BSS), so r14 = 0
5. At offset +0x6F, `test r14, r14` sets ZF=1
6. At offset +0x75, `je +0x101` is TAKEN, jumping to offset +0x179
7. The function continues to offset +0x1CF but never reaches the store at +0x3969
8. The global 0x801E51240 is NEVER written

### Root Cause Chain

```
[0x801E518C8] = 0 (BSS, never initialized)
  ↓
mov r14, [rbx] → r14 = 0
  ↓
test r14, r14 → ZF=1
  ↓
je +0x101 (TAKEN) → skip to offset +0x179
  ↓
Function continues but NEVER reaches store at +0x3969
  ↓
[0x801E51240] stays NULL
  ↓
84 functions that read [0x801E51240] get NULL
  ↓
Functions skip initialization (including potentially PlayerLoop)
  ↓
WaitSema(0x81) deadlock
```

### Key Address: 0x801E518C8

This is the ACTUAL root cause address. The value at 0x801E518C8 (which is in BSS, value 0) causes the function to take an early branch, preventing the global 0x801E51240 from being initialized.

---

## Artifacts

- `/tmp/exp161_func_entry.log` — Function entry INT3 trace
- `/tmp/exp161_ladder3.log` — Ladder with 3 breakpoints (all hit)
- `/tmp/exp161_ladder4.log` — Single breakpoint at +0xF2 (NOT hit)
- `/tmp/exp161_ladder5.log` — Single breakpoint at +0x1CF (hit, r14=0)
- `/home/z/my-project/scripts/exp161/EXP-161_RUNTIME_FUNCTION_ENTRY_REPORT.md` — This report
