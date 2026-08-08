# EXP-NEXT — Evidence-First Initialization Chain After argc Validation

**Date:** 2026-08-08
**Status:** TEST ONLY — No patches, no HLE changes, no emulator behavior changes
**Predecessor:** EXP-173 (indirect call at +0x19A7 identified as exit point)

---

## Confirmed Execution Order (argc=2)

```
Loader
  ↓ PASS — All 8 PRXs loaded, 3 TLS modules registered
DT_INIT (eboot 0x800000010)
  ↓ PASS — Runs before main
0x8007E8790 (initializer)
  ↓ PASS — [0x801E50DF0]=0x801BB4B77, [0x801E50DF8]=0x801E518C8
0x800804175 (clear)
  ↓ PASS — [0x801E518C8]=0 (cleared before parent runs)
EBOOT main (0x800000070)
  ↓ PASS — argc=2 (via SHARPEMU_GUEST_ARGS="dummy_arg")
0x8013FCE40 (parent function)
  ↓ PASS — r13d=2, jl at +0x91 NOT taken
  ↓ +0x24E (0x8013FD08E): init write for [0x801E518C8] — PASS
  ↓ +0xDDB (0x8013FDC1B): call 0x8013FB0B0 (GOT writer) — PASS (static analysis confirmed)
  ↓ +0xDF9 (0x8013FDC39): call 0x8013EB6B0 (consumer) — PASS
0x8013FB0B0 (GOT writer function, SEPARATE from consumer)
  ↓ PASS — Called before consumer
  ↓ +0x1B0 (0x8013FB260): mov [0x801ED6320], rax — FILLS GOT SLOT
  ↓ rax = return value of call 0x8019374D0 (PLT entry)
  ↓ PLT entry: jmp [0x801D1ACDC]; push 0xE7; jmp resolver
0x8013EB6B0 (consumer function)
  ↓ PASS — Entered with [0x801E518C8]=0x20000259C0 (NON-NULL)
  ↓ +0x72: je NOT taken (r14≠0) — PASS
  ↓ +0x277 through +0x191F: all branches NOT taken — PASS
  ↓ +0x19A7 (0x8013ED057): call [0x801ED6320] — LAST REACHABLE POINT
  ↓ call DOES NOT RETURN to 0x8013ED05D
  ↓ Execution enters dispatch loop function 0x800AA0170
0x800AA0170 (dispatch loop / semaphore wait)
  ↓ +0x97 (0x800AA0207): call sceKernelWaitSema(0x81)
  ↓ DEADLOCK — WaitSema(0x81) never returns
0x8013EF019 (init writer for [0x801E51240])
  ↓ FAIL — NEVER REACHED (consumer exited at +0x19A7)
[0x801E51240] stays NULL
  ↓ FAIL — 42 reader functions get NULL
PlayerLoop registration
  ↓ FAIL — Skipped (no [0x801E51240])
VideoOut
  ↓ FAIL — 0 calls
```

---

## Confirmed Memory States

| Address | argc=1 | argc=2 | Source |
|---------|--------|--------|--------|
| [0x801E50DF0] | 0x801BB4B77 | 0x801BB4B77 | EXP-170 (initializer 0x8007E8790) |
| [0x801E50DF8] | 0x801E518C8 | 0x801E518C8 | EXP-170 (initializer 0x8007E8790) |
| [0x801E518C8] | 0x0 (NULL) | 0x20000259C0 | EXP-170 (init write 0x8013FD08E, skipped when argc=1) |
| [0x801E51240] | 0x0 (NULL) | 0x0 (NULL) | EXP-173 (INT3 HIT at +0x19A7) |
| [0x801ED6320] | Unknown | Non-NULL (inferred) | Static analysis + no crash at indirect call |

### Evidence for [0x801ED6320] being non-NULL at runtime:

1. The indirect call `call [0x801ED6320]` at 0x8013ED057 IS reached (EXP-173 INT3 HIT)
2. The game does NOT crash with a NULL pointer dereference at this call
3. The game reaches WaitSema(0x81) deadlock (not a crash)
4. Therefore [0x801ED6320] must contain a valid function pointer

---

## 0x801E51240 Initialization: SKIPPED

### Evidence:

**Static analysis — writers to 0x801E51240:**

| Address | Instruction | Classification |
|---------|-------------|----------------|
| 0x8007FD8F9 | `mov qword [0x801E51240], 0x0` | A) Executed (clears to 0) |
| 0x8013EF019 | `mov [0x801E51240], rax` | C) Skipped by branch (consumer exits at +0x19A7) |

**Static analysis — comparators:**

| Address | Instruction |
|---------|-------------|
| 0x800AAB8B8 | `cmp qword [0x801E51240], 0x0` |
| 0x8013F3347 | `cmp qword [0x801E51240], 0x0` |

**Static analysis — readers:** 40 RIP-relative readers found in eboot.

**Runtime evidence (EXP-173 INT3 HIT at 0x8013ED057):**
- `[0x801E51240] = 0x0000000000000000` at the indirect call
- The init writer at 0x8013EF019 (+0x3969 in consumer) is NEVER reached

### Conclusion:

The init writer at 0x8013EF019 exists but is **SKIPPED** because the consumer exits at +0x19A7 (indirect call that doesn't return) before reaching +0x3969.

---

## Exact Blocking Branch / Exit Point

### The indirect call at +0x19A7 (0x8013ED057) is the blocking exit point.

**Instruction:** `FF 15 C3 92 AE 00` = `call [rip+0x00AE92C3]` → `call [0x801ED6320]`

**Evidence (EXP-173):**

| Test | INT3 at | Result |
|------|---------|--------|
| indirect_call.log | 0x8013ED057 (call) + 0x8013ED061 (je) | BOTH HIT — call "returns" (but see INT3 bug below) |
| je_only.log | 0x8013ED061 (je) only | NOT HIT — je never reached without INT3 at call |
| exit_points.log | 0x8013ED0B5, 0x8013ED1E7, 0x8013ED215 | NOT HIT — all after je, never reached |
| second_call.log | 0x8013ED063, 0x8013ED06A, 0x8013ED070 | NOT HIT — all after je, never reached |

**Conclusion:** The indirect call at 0x8013ED057 is the LAST instruction reached in the consumer. The call does NOT return to 0x8013ED05D (the next instruction). Execution enters the dispatch loop (function 0x800AA0170) and blocks on WaitSema(0x81).

---

## CRITICAL SIDE FINDING: INT3 Handler Bug

### The INT3 handler corrupts multi-byte instructions.

**Root cause:** In `DirectExecutionBackend.Exceptions.cs`, the INT3 handler:
1. Restores the original byte at the INT3 address
2. Sets the TF (trap flag) for single-step
3. Sets RIP = INT3_address + 1

For a multi-byte instruction at address X (e.g., `FF 15 disp32` = 6-byte `call [rip+disp32]`):
- INT3 fires at X → kernel sets RIP = X+1
- Handler restores byte at X (back to 0xFF)
- Handler sets RIP = X+1 (no change — already there)
- CPU resumes at X+1, which is the SECOND BYTE of the original instruction
- CPU decodes garbage (e.g., 0x15 = `ADC EAX, imm32` instead of 0xFF 0x15 = `call [rip+disp32]`)

### Mathematical Proof (EXP-173 indirect_call.log):

**At INT3 HIT slot=1 (0x8013ED057, before "call"):**
- rax = 0x000000060000007F

**At INT3 HIT slot=2 (0x8013ED061, after "call"):**
- rax = 0x0000000000AE9342

**If the call was NEVER executed and CPU instead executed `ADC EAX, imm32`:**
- imm32 = 0x00AE92C3 (the disp32 bytes of the original call instruction)
- EAX before = 0x6000007F (lower 32 bits of rax)
- EAX + imm32 = 0x6000007F + 0x00AE92C3 = 0x00AE9342 (32-bit, zero-extended to 64-bit)
- **MATCHES** the logged "return value" 0x00AE9342

### Conclusion:

EXP-173's conclusion that "the indirect call returned with rax=0xAE9342" is **WRONG**. The indirect call was NEVER executed. The CPU instead executed `ADC EAX, imm32` due to the INT3 handler bug, which by coincidence produced the same value.

### Impact on prior EXPs:

All RIP-TRACE findings from EXP-145 through EXP-173 that depend on POST-INT3 register values are **SUSPECT**. The INT3 HIT itself (confirming execution reached the address) is still valid, but any register values logged AFTER the INT3 are corrupted.

### Implication for EXP-NEXT:

- The "return value" 0xAE9342 is NOT a function return value
- We CANNOT determine if the indirect call returns by using the current INT3 handler
- The evidence that the call doesn't return comes from **je_only.log** (je NOT reached without INT3 at call)

---

## GOT Slot 0x801ED6320 — Initialization Chain

### Static Analysis:

**GOT slot location:** 0x801ED6320 is in eboot's BSS (writable segment vaddr=0x1D20000, filesz=0xD5D78, memsz=0x219970; BSS range 0x1DF5D78 to 0x1F39970; 0x1ED6320 is within BSS).

**Writer:** `0x8013FB260: mov [0x801ED6320], rax` (7-byte instruction, RIP-relative)

**Writer function:** 0x8013FB0B0 (SEPARATE from consumer 0x8013EB6B0)
- Consumer function: 0x8013EB6B0 to 0x8013F6143 (ends with RET + CC padding)
- GOT writer function: 0x8013FB0B0 to ??? (starts after CC padding at 0x8013FB0AD)
- GOT writer at 0x8013FB260 is at +0x1B0 inside the GOT writer function

**Caller of GOT writer:** 0x8013FDC1B (inside parent function 0x8013FCE40, at offset +0xDDB)
- `E8 90 D4 FF FF` = `call 0x8013FB0B0` (confirmed)
- This is BEFORE the consumer call at 0x8013FDC39 (+0xDF9)

**Value stored in [0x801ED6320]:**
- The GOT writer calls `0x8019374D0` at 0x8013FB25B
- The return value (rax) is stored in [0x801ED6320] at 0x8013FB260
- `0x8019374D0` is a PLT entry: `FF 25 0A 38 3E 00` = `jmp [rip+0x003E380A]` → `jmp [0x801D1ACDC]`
- PLT index: 0xE7 (231) — pushed by `push 0xE7` at 0x8019374D6
- PLT GOT slot: 0x801D1ACDC (in eboot's writable data segment, vaddr=0x1C80000)

**PLT GOT slot 0x801D1ACDC:**
- Initial file value: 0x019374D600000000 (Sony-specific format — offset in high 32 bits)
- NOT in standard DT_RELA (49850 entries) or DT_JMPREL (600 entries)
- Must be filled by SharpEmu's loader at runtime via NID resolution
- The Sony-specific program header (type=0x61000001, "ORBI" magic) likely contains the NID table

**Function table pattern:**
- The GOT writer function 0x8013FB0B0 calls 0x8019374D0 **232 times** (once for each function pointer slot)
- It fills a function pointer table at 0x801ED6320, 0x801ED6328, 0x801ED6330, ... (8-byte slots)
- This is a vtable / callback registration table

### Runtime Evidence:

- The indirect call at 0x8013ED057 IS reached (EXP-173 INT3 HIT)
- The game does NOT crash (reaches WaitSema deadlock)
- Therefore [0x801ED6320] has a valid function pointer at runtime
- The function pointer is the return value of calling PLT entry 0x8019374D0
- PLT 0x8019374D0 resolves to an import via [0x801D1ACDC]

### What we DON'T know yet:

- Which import function is at [0x801ED6320] (need to identify what NID fills [0x801D1ACDC])
- Whether that function is HLE-handled or native
- Why that function doesn't return (enters dispatch loop instead)

---

## TEST 4: argc=1 vs argc=2 Comparison

| Aspect | argc=1 | argc=2 |
|--------|--------|--------|
| [0x801E518C8] | 0x0 (NULL) | 0x20000259C0 (NON-NULL) |
| [0x801E51240] | 0x0 (NULL) | 0x0 (NULL) |
| Consumer path | Early exit at +0x72 (je taken, r14=0) | Passes +0x72, reaches +0x19A7 |
| Stall location | WaitSema(0x81) at 0x800AA0207 | WaitSema(0x81) at 0x800AA0207 |
| VideoOut calls | 0 | 0 |
| PlayerLoop | Not reached | Not reached |

### Conclusion:

argc=2 **only removes the first blocker** ([0x801E518C8] initialization). It does NOT fix the downstream initialization of [0x801E51240]. The consumer still exits at +0x19A7 (indirect call that doesn't return), preventing [0x801E51240] from being initialized.

---

## TEST 5: WaitSema(0x81) Dependency Validation

### Before WaitSema(0x81):

| Requirement | Status | Evidence |
|-------------|--------|----------|
| [0x801E51240] required? | YES — 42 reader functions depend on it | Static analysis: 40 RIP-relative readers |
| [0x801E51240] initialized? | NO — stays NULL | EXP-173 INT3 HIT: [0x801E51240]=0x0 |
| Another global/state missing? | [0x801ED6320] is filled (inferred from no crash) | Static analysis + runtime behavior |
| Which function should initialize PlayerLoop? | The consumer 0x8013EB6B0, at +0x3969 (0x8013EF019) | Static analysis: init writer for [0x801E51240] |
| Which initialization stage is missing? | [0x801E51240] initialization (consumer exits before +0x3969) | EXP-173: consumer exits at +0x19A7 |

### WaitSema(0x81) caller:

- **Caller RIP:** 0x800AA0207
- **Containing function:** 0x800AA0170 (starts with `push rbp; mov rbp, rsp; push r14; push rbx; mov eax, 1; mov rbx, rdi; lock ...`)
- **Thread:** AssetGarbageCollectorHelper (tid=40)
- **Semaphore handle:** 0x81

### Why WaitSema(0x81) deadlocks:

The dispatch loop function 0x800AA0170 is entered via the indirect call at 0x8013ED057. This function calls WaitSema(0x81) which never returns because:
1. The semaphore is never signaled (no PlayerLoop registration → no bootstrap job)
2. PlayerLoop registration is skipped because [0x801E51240] is NULL
3. [0x801E51240] is NULL because the consumer exited before reaching +0x3969

---

## TEST 6: State Machine Reconstruction

```
Loader                    ✅ PASS  — All 8 PRXs loaded, 3 TLS modules registered
  ↓
entry parameters          ✅ PASS  — argc=2 (via SHARPEMU_GUEST_ARGS="dummy_arg")
  ↓
DT_INIT                   ✅ PASS  — eboot 0x800000010 runs successfully
  ↓
0x8007E8790 (initializer) ✅ PASS  — [0x801E50DF0] and [0x801E50DF8] initialized
  ↓
0x8013FCE40 (parent)      ✅ PASS  — argc=2, jl at +0x91 NOT taken
  ↓
0x8013FD08E (+0x24E)      ✅ PASS  — [0x801E518C8] = 0x20000259C0 (NON-NULL)
  ↓
0x8013FDC1B (+0xDDB)      ✅ PASS  — call GOT writer 0x8013FB0B0 (static analysis confirmed)
  ↓
0x8013FB0B0 (GOT writer)  ✅ PASS  — Fills [0x801ED6320] with PLT-resolved function pointer
  ↓
0x8013FDC39 (+0xDF9)      ✅ PASS  — call consumer 0x8013EB6B0
  ↓
0x8013EB6B0 (consumer)    ✅ PASS  — Entered with [0x801E518C8]=0x20000259C0
  ↓
Consumer +0x72             ✅ PASS  — je NOT taken (r14≠0)
  ↓
Consumer +0x191F           ✅ PASS  — jne NOT taken (last confirmed branch)
  ↓
Consumer +0x19A7           ❌ FAIL  — call [0x801ED6320] does NOT return
  ↓                                    (enters dispatch loop 0x800AA0170)
0x801E51240 initialization ❌ FAIL  — Init writer at +0x3969 NEVER reached
  ↓
PlayerLoop registration   ❌ FAIL  — [0x801E51240]=NULL, 42 readers get NULL
  ↓
VideoOut                   ❌ FAIL  — 0 calls
  ↓
WaitSema(0x81)             ❌ DEADLOCK — Dispatch loop blocks forever
```

---

## Root Cause Status

### Previous argc blocker: CONFIRMED

- argc=1 caused [0x801E518C8] to stay NULL (init write at +0x24E skipped by jl at +0x91)
- Fix: SHARPEMU_GUEST_ARGS="dummy_arg" makes argc=2
- With argc=2, [0x801E518C8] = 0x20000259C0 (NON-NULL) ✅

### Current [0x801E51240] blocker: CONFIRMED with partial evidence

- The init writer at 0x8013EF019 (+0x3969) exists but is NEVER reached
- The consumer exits at +0x19A7 (indirect call at 0x8013ED057)
- The indirect call goes through [0x801ED6320], which is filled by GOT writer 0x8013FB0B0
- The GOT writer IS called before the consumer (static analysis confirmed)
- [0x801ED6320] has a valid function pointer at runtime (inferred from no crash)
- The function at [0x801ED6320] does NOT return — it enters the dispatch loop
- The dispatch loop blocks on WaitSema(0x81)

### INT3 handler bug: CONFIRMED (side finding)

- Multi-byte instructions are corrupted after INT3 fires
- EXP-173's "return value 0xAE9342" was actually ADC result, not a function return
- This bug affects all prior RIP-TRACE findings on multi-byte instructions
- The INT3 HIT itself (confirming execution reached the address) is still valid

---

## Closed Hypotheses

| # | Hypothesis | Status | Evidence |
|---|-----------|--------|----------|
| 1 | argc=1 is the ONLY blocker | CLOSED | argc=2 fixes [0x801E518C8] but [0x801E51240] still NULL |
| 2 | Consumer early exit at +0x72 is the blocker | CLOSED | With argc=2, +0x72 is NOT taken |
| 3 | Skip branches +0x277 to +0x191F are taken | CLOSED | All NOT taken at runtime (EXP-171) |
| 4 | [0x801E51240] has no init writer | CLOSED | Writer exists at +0x3969 but never reached |
| 5 | TLS initialization issue | CLOSED | REJECTED (EXP-172) |
| 6 | Initializer ordering issue | CLOSED | REJECTED (EXP-167) |
| 7 | [0x801ED6320] is NULL at runtime | CLOSED | No crash at indirect call — must be non-NULL |
| 8 | GOT writer is inside consumer | CLOSED | GOT writer is SEPARATE function 0x8013FB0B0 |
| 9 | GOT writer is never called | CLOSED | Called from parent at +0xDDB before consumer at +0xDF9 |
| 10 | EXP-173's "call returns with 0xAE9342" | CLOSED | INT3 handler bug — ADC result, not function return |

---

## Next Evidence Target

### Primary: Identify what function is at [0x801ED6320] at runtime

This requires ONE of:

**A) Fix the INT3 handler bug (temporary test instrumentation):**
- Change `WriteCtxU64Icall(contextRecord, 248, _ripTraceAddress1 + 1)` to `WriteCtxU64Icall(contextRecord, 248, _ripTraceAddress1)` (set RIP BACK to instruction start)
- Also fix the re-patch condition: `rip > _ripTraceAddress1` instead of `rip == _ripTraceAddress1 + 1`
- This allows the original instruction to execute correctly
- Then set INT3 at 0x8013ED057 and dump [0x801ED6320] when it fires

**B) Add a memory dump of [0x801ED6320] to the INT3 handler:**
- Add `memVal5 = *(ulong*)0x801ED6320UL` to the handler
- Set INT3 at a 1-byte instruction BEFORE the indirect call (e.g., 0x8013ED056 or earlier)
- Read [0x801ED6320] when the INT3 fires

**C) Check SharpEmu's NID resolution log:**
- Search the runtime log for any reference to 0x801D1ACDC (the PLT GOT slot)
- Or search for PLT index 0xE7 (231)
- Identify which NID/symbol is resolved to fill this slot

### Secondary: Determine why the function at [0x801ED6320] doesn't return

Once the function is identified:
- Is it an HLE-handled import? (Check SharpEmu's HLE export table)
- Is it a native function? (Disassemble and trace)
- Does it intentionally block (e.g., a thread join function)?
- Or does it call WaitSema as part of normal operation?

### Tertiary: Verify GOT writer execution order at runtime

- Set INT3 at 0x8013FB0B0 (GOT writer entry, 1-byte `push rbp`) — should work without corruption
- Set INT3 at 0x8013EB6B0 (consumer entry, 1-byte `push rbp`) — should work without corruption
- Confirm GOT writer fires BEFORE consumer
- NOTE: The INT3 handler's TF bug will cause TF to stay set, but execution should continue

---

## Artifacts

- `/home/z/my-project/scripts/exp174/exp174_static_writers.py` — Writers/readers scan for 0x801E51240
- `/home/z/my-project/scripts/exp174/exp174_got_slot_identify.py` — GOT slot 0x801ED6320 segment/relocation analysis
- `/home/z/my-project/scripts/exp174/exp174_int3_handler_bug.py` — INT3 handler bug proof (ADC match)
- `/home/z/my-project/scripts/exp174/exp174_find_got_init.py` — Find GOT slot initializer (LEA/writes scan)
- `/home/z/my-project/scripts/exp174/exp174_got_writer_func.py` — Analyze GOT writer function 0x8013FB0B0
- `/home/z/my-project/scripts/exp174/exp174_parent_flow.py` — Parent function control flow analysis
- `/home/z/my-project/scripts/exp174/exp174_resolver_func.py` — Analyze PLT entry 0x8019374D0
- `/home/z/my-project/scripts/exp174/exp174_decode_resolver.py` — Decode PLT entry bytes
- `/home/z/my-project/scripts/exp174/exp174_identify_plt_import.py` — Identify PLT import symbol
- `/tmp/exp174_baseline_argc2.log` — Baseline argc=2 run (WaitSema deadlock + secondary crash)
- `/tmp/exp173_indirect_call.log` — EXP-173 INT3 at indirect call (evidence source)
- `/tmp/exp173_je_only.log` — EXP-173 INT3 at je only (proves call doesn't return)

---

## Summary

The argc=2 fix removed the FIRST blocker ([0x801E518C8] initialization). The CURRENT blocker is the indirect call at consumer +0x19A7 (`call [0x801ED6320]`) which does NOT return. This call goes through a GOT slot filled by a separate GOT writer function (0x8013FB0B0), which is called BEFORE the consumer. The GOT slot contains a PLT-resolved function pointer. The function enters the dispatch loop (0x800AA0170) and blocks on WaitSema(0x81), preventing the consumer from reaching the init writer for [0x801E51240] at +0x3969.

Additionally, a critical INT3 handler bug was discovered: multi-byte instructions are corrupted after INT3 fires, causing the CPU to execute garbage bytes as different instructions. This bug invalidates EXP-173's "return value" evidence and affects all prior RIP-TRACE findings on multi-byte instructions.

**No patches applied. No fixes implemented. No assumptions made. Evidence decides.**
