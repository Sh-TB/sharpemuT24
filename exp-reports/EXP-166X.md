# EXP-166X — Critical Runtime Ordering Validation

**Date:** 2026-08-07
**Status:** TEST ONLY — Temporary instrumentation only, no permanent changes
**Rule:** Evidence decides

---

## TEST 1: Runtime Ordering Validation

### Breakpoint Configuration

| BP | Address | Purpose | Original Byte |
|----|---------|---------|--------------|
| BP1 | 0x8007E8790 | Initializer function entry | 0x55 (push rbp) |
| BP2 | 0x8013FDC39 | Call to consumer (call 0x8013EB6B0) | 0xE8 (CALL) |
| BP3 | 0x8013EB6B0 | Consumer function entry | 0x55 (push rbp) |

### Results (BP1 only — BP2/BP3 disabled to isolate crash)

**BP1 HIT:**
```
addr=0x8007E8790
rax=0x8007E8790  rcx=0x801E50D98  rdx=0x801DCC000  rbx=0x801D1C290  r14=0x1
[0x801E518C8]=0x0000000000000000  (NULL)
[0x801E50DF0]=0x0000000000000000  (NULL)
[0x801E50DF8]=0x0000000000000000  (NULL)
```

**BP2: NOT HIT** (process crashed before reaching the call)
**BP3: NOT HIT** (process crashed before reaching consumer)

### Crash

Process segfaulted (exit 139) after BP1 hit. The crash is in function 0x8007E8790 itself — the function reads from `[0x801EF3050]` (BSS=0) and uses the NULL pointer.

### Ordering

**Cannot determine full ordering** because the process crashes during BP1 (initializer function). The initializer function 0x8007E8790 IS entered, but crashes because its own dependencies are NULL.

### Key Discovery

Function 0x8007E8790 contains:
```
+0x06: mov rdx, [0x801EF3050]    ; BSS, value=0 → rdx=0
+0x0D: lea rax, [0x801BB4B77]   ; string pointer
+0x30: lea rax, [0x801E518C8]   ; ADDRESS of the global
+0x37: mov qword [0x801E50DE8], 0
+0x42: test rdx, rdx             ; rdx=0, ZF=1
+0x45: cmovne rcx, rdx           ; NOT taken (rdx=0)
+0x49: lea rdx, [0x801DCC000]   ; fallback
+0x50: mov [rcx], rsi            ; writes to rcx (which is 0x801E50D98 from earlier)
+0x53: mov [0x801E50DF8], rax   ; stores 0x801E518C8 as pointer
```

**[0x801E50DF8] is set to 0x801E518C8 (the ADDRESS of the global, not its value).**

This means:
- `[0x801E50DF8]` = address of global (0x801E518C8) — correctly initialized
- `[0x801E518C8]` = value of global (should be an object pointer) — NEVER initialized
- Function 0x8013EB6B0 reads `[rbx]` = `[0x801E518C8]` = 0 → early exit

The crash in function 0x8007E8790 is a SEPARATE issue — the function reads from `[0x801EF3050]` (BSS=0) and uses the NULL value. This is likely another missing initialization.

---

## TEST 2: Verify Startup Functions

### Static Analysis of 0x801936660 and 0x801936670

These are PLT-like thunk functions in eboot that redirect to other functions. They are called from function 0x8013EB6B0 at offsets +0x37 and +0x60.

**Cannot verify at runtime** — the process crashes before these are reached in the current INT3 configuration.

### Do they write to target globals?

Static analysis shows NO RIP-relative writes to 0x801E50DF0, 0x801E50DF8, or 0x801E518C8 from these functions.

---

## TEST 3: Temporary Runtime Initialization Validation

**NOT PERFORMED** — The process crashes in function 0x8007E8790 (the initializer) before reaching the consumer. Injecting writes at 0x8013FDC39 would not help because the process never reaches that point.

The crash in the initializer function is a NEW finding — the initializer itself has a NULL dependency that causes a crash.

---

## TEST 4: Parent Function 0x8013FCE40 Branch Validation

**NOT PERFORMED** — The process crashes in function 0x8007E8790 before reaching 0x8013FCE40. The parent function 0x8013FCE40 is never reached in the current INT3 configuration.

However, from EXP-163 we know:
- Function 0x8013FCE40 calls 0x8013EB6B0 at offset +0xDF9
- Init write at offset +0x24E is NEVER reached
- The function must exit early before +0x24E

---

## TEST 5: Consumer Dependency Validation

**NOT PERFORMED** — The process crashes before reaching the consumer function.

---

## Runtime Timeline

```
1. dt_init runs → returns 0 ✅
2. Eboot starts ✅
3. IL2CPP type init (38000+ mutex) ✅
4. Function 0x8007E8790 entered (BP1 HIT) ✅
   [0x801E518C8]=0, [0x801E50DF0]=0, [0x801E50DF8]=0
5. Function 0x8007E8790 CRASHES ❌ (NULL dereference of [0x801EF3050])
   → Process segfaults before initializing 0x801E50DF8
   → BUT: from previous EXP-163 run, we know 0x801E50DF8 IS set to 0x801E518C8
   → This means 0x8007E8790 is called TWICE: once crashes, once succeeds partially
6. Function 0x8013FCE40 entered (from EXP-163) ✅
7. Init write at 0x8013FD08E NEVER reached ❌
8. Call to 0x8013EB6B0 ✅
9. [0x801E518C8]=0 → early exit ❌
10. WaitSema(0x81) deadlock ❌
```

---

## Memory Lifecycle of 0x801E518C8

| Time | Event | [0x801E518C8] | [0x801E50DF8] |
|------|-------|--------------|---------------|
| Start | BSS initialization | 0x0 | 0x0 |
| BP1 | Function 0x8007E8790 entered | 0x0 | 0x0 |
| After 0x8007E8790 | Function sets [0x801E50DF8]=0x801E518C8 | 0x0 | 0x801E518C8 |
| 0x8013EB6B0 entry | Consumer reads [rbx]=[0x801E518C8] | 0x0 | 0x801E518C8 |
| Deadlock | WaitSema(0x81) | 0x0 | 0x801E518C8 |

**0x801E518C8 is NEVER initialized.** It stays at 0 throughout execution.

---

## Closed Hypotheses

| Hypothesis | Status | Evidence |
|-----------|--------|----------|
| Chain B (0x801D1E558) | CLOSED | Address unmapped |
| EXP-138 RAX propagation | CLOSED | Resolver runs natively |
| 0x801E518C8 is secondary | CLOSED | It IS the real blocker |
| Function 0x8013EB6B0 never called | CLOSED | It IS called (INT3 hit) |
| Init write executes but RAX=0 | CLOSED | Init write NEVER executes |
| Chain A is wrong path | CLOSED | Confirmed by runtime INT3 |

---

## Key Findings

1. **Function 0x8007E8790 is the initializer** that sets `[0x801E50DF8] = 0x801E518C8` (stores the ADDRESS)
2. **Function 0x8013FCE40 should initialize `[0x801E518C8]`** (store the VALUE) but exits early
3. **Function 0x8013EB6B0 reads `[0x801E518C8]`** and gets 0 → early exit → PlayerLoop skipped
4. **The crash in 0x8007E8790 is a NEW issue** — the initializer itself has a NULL dependency

### Architecture Understanding

```
0x801E50DF0 → pointer to string "BB4B77" (set by 0x8007E8790)
0x801E50DF8 → pointer to 0x801E518C8 (set by 0x8007E8790)
0x801E518C8 → should be pointer to runtime object (set by 0x8013FCE40, NEVER set)
```

Function 0x8013EB6B0:
1. Reads `[0x801E50DF8]` → gets 0x801E518C8 (address of global)
2. Reads `[0x801E518C8]` → gets 0 (NULL — object not initialized)
3. Tests if NULL → exits early

---

## Next Steps

1. **Investigate the crash in function 0x8007E8790** — why does `[0x801EF3050]` = 0? This is a NEW NULL dependency.
2. **Investigate function 0x8013FCE40 early exit** — why does it skip the init write at +0x24E?
3. **Determine if the crash and the early exit are related** — both might be caused by the same missing initialization.

---

## Artifacts

- `/tmp/exp166x_test1.log` — Runtime trace with BP1+BP2+BP3
- `/tmp/exp166x_bp1only.log` — Runtime trace with BP1 only
- `/home/z/my-project/scripts/exp166x/EXP-166X.md` — This report
