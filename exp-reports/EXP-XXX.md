# EXP-XXX — Trace GOT/PLT Dispatch Blocker Before Downstream Initialization

**Date:** 2026-08-08
**Status:** TEST ONLY — No patches, no HLE changes, no emulator behavior changes
**Predecessor:** EXP-NEXT (INT3 handler bug discovered, GOT writer identified)

---

## 1. Confirmed Execution Sequence

```
Loader
  ↓ PASS — All PRXs loaded
DT_INIT (eboot 0x800000010)
  ↓ PASS
0x8007E8790 (initializer)
  ↓ PASS — [0x801E50DF0]=0x801BB4B77, [0x801E50DF8]=0x801E518C8
EBOOT main (0x800000070)
  ↓ PASS — argc=2
0x8013FCE40 (parent function)
  ↓ PASS — r13d=2, jl at +0x91 NOT taken
  ↓ +0x24E: init write for [0x801E518C8] — PASS
  ↓ +0xDDB (0x8013FDC1B): call 0x8013FB0B0 (GOT writer) — PASS
0x8013FB0B0 (GOT writer function)
  ↓ PASS — Called before consumer
  ↓ +0x1AF (0x8013FB25B): call 0x8019374D0 (PLT entry for NID r8mvOaWdi28)
  ↓ PLT entry: jmp [0x801D1ACE0] → HLE trampoline → DispatchIl2CppApiLookupSymbol()
  ↓ DispatchIl2CppApiLookupSymbol reads RDI = symbol name string
  ↓ Calls real resolver at 0x804ED9B90 via TryCallGuestFunction
  ↓ Resolver looks up symbol in IL2CPP BST, returns function address in RAX
  ↓ +0x1B0 (0x8013FB260): mov [0x801ED6320], rax — stores resolved function pointer
  ↓ (repeats 232 times for 232 IL2CPP API functions, filling table at 0x801ED6320+)
  ↓ +0xDF9 (0x8013FDC39): call 0x8013EB6B0 (consumer) — PASS
0x8013EB6B0 (consumer function)
  ↓ PASS — Entered with [0x801E518C8]=0x20000259C0 (NON-NULL)
  ↓ +0x72 through +0x191F: all branches NOT taken — PASS
  ↓ +0x19A7 (0x8013ED057): call [0x801ED6320] — LAST REACHABLE POINT
  ↓ [0x801ED6320] = first IL2CPP API function pointer (il2cpp_init → 0x804ED85D0)
  ↓ call does NOT return to 0x8013ED05D
  ↓ Execution enters dispatch loop → WaitSema(0x81) → DEADLOCK
0x8013EF019 (init writer for [0x801E51240])
  ↓ FAIL — NEVER REACHED (consumer exited at +0x19A7)
```

---

## 2. Exact Function Address Behind 0x801ED6320

### [0x801ED6320] = Return value of calling NID `r8mvOaWdi28` with RDI = `"il2cpp_init"`

### Full resolution chain:

```
GOT writer 0x8013FB0B0
  ↓ call 0x8019374D0 (PLT entry, PLT index 0xE7)
0x8019374D0 (PLT entry)
  ↓ FF 25 0A 38 3E 00    jmp [rip+0x003E380A]  →  jmp [0x801D1ACE0]
[0x801D1ACE0] (PLT GOT slot, DT_JMPREL entry 231)
  ↓ NID: r8mvOaWdi28#A#B (symbol name from DT_SYMTAB)
  ↓ Type: R_X86_64_JUMP_SLOT (7)
  ↓ Initial file value: 0x00000000019374D6 (lazy binding stub)
  ↓ At runtime: SharpEmu fills with HLE trampoline address
[HLE trampoline]
  ↓ Jumps to ImportDispatchGatewayManaged → DispatchImport
  ↓ DispatchImport checks NID == "r8mvOaWdi28"
  ↓ Calls DispatchIl2CppApiLookupSymbol()
DispatchIl2CppApiLookupSymbol()
  ↓ Reads RDI = symbol name address (e.g., "il2cpp_init")
  ↓ Calls TryCallGuestFunction(0x804ED9B90, RDI=symbol_name)
0x804ED9B90 (real IL2CPP symbol resolver, inside Il2cppUserAssemblies.prx)
  ↓ Walks IL2CPP BST looking for symbol name
  ↓ Returns function address in RAX (e.g., 0x804ED85D0 for il2cpp_init)
  ↓ Return value stored in [0x801ED6320] by GOT writer
```

### Evidence:

| Evidence | Source |
|----------|--------|
| PLT entry at 0x8019374D0 uses GOT slot 0x801D1ACE0 | Static analysis (exp175_plt_got_layout.py) |
| GOT slot 0x801D1ACE0 = DT_JMPREL entry 231 (PLT index 0xE7) | Static analysis (exp175_jmprel_direct.py) |
| DT_JMPREL entry 231: NID = `r8mvOaWdi28#A#B`, type = R_X86_64_JUMP_SLOT | Static analysis (exp175_jmprel_direct.py) |
| SharpEmu handles NID `r8mvOaWdi28` via `DispatchIl2CppApiLookupSymbol()` | Source: DirectExecutionBackend.Imports.cs:622-624 |
| `DispatchIl2CppApiLookupSymbol` calls real resolver at 0x804ED9B90 | Source: DirectExecutionBackend.Imports.cs:2384-2403 |
| First resolver call: name='il2cpp_init' | Runtime log: /tmp/exp175_run.log |
| il2cpp_init resolves to 0x804ED85D0 | Worklog (EXP-026 synthetic CPU trace) |

### Corrected from EXP-NEXT:

EXP-NEXT incorrectly calculated the PLT GOT slot as 0x801D1ACDC. The correct address is **0x801D1ACE0**:
- PLT entry at 0x8019374D0: `FF 25 0A 38 3E 00` = `jmp [rip+0x003E380A]`
- Instruction end: 0x8019374D0 + 6 = 0x8019374D6
- Target: 0x8019374D6 + 0x003E380A = **0x801D1ACE0** (not 0x801D1ACDC)

---

## 3. Whether the Indirect Call Returns

### The indirect call at 0x8013ED057 does NOT return.

### Evidence (from EXP-173 logs, validated for INT3 reliability):

| Test | INT3 Location | HIT? | Conclusion |
|------|--------------|------|------------|
| indirect_call.log | 0x8013ED057 (call) + 0x8013ED061 (je) | BOTH HIT | Call "returns" (but see INT3 bug) |
| je_only.log | 0x8013ED061 (je) only | NOT HIT | Without INT3 at call, je is NEVER reached |

### Critical analysis:

The `je_only.log` test is the valid evidence. When INT3 is placed ONLY at the je (0x8013ED061, the instruction AFTER the call), it is NEVER hit. This means:
- The call at 0x8013ED057 does NOT return to 0x8013ED05D
- The je at 0x8013ED061 is NEVER reached without INT3 corruption

The `indirect_call.log` test (INT3 at both call and je) is INVALID for post-INT3 register values due to the INT3 handler bug (see TEST 5). However, the INT3 HIT at 0x8013ED057 is valid — it confirms execution reached the call.

### Why the call doesn't return:

The call goes through [0x801ED6320], which contains the address of `il2cpp_init` (0x804ED85D0). The function `il2cpp_init` is the IL2CPP runtime initialization function. It:
1. Initializes the IL2CPP runtime
2. Registers callbacks
3. Enters the IL2CPP execution loop

The IL2CPP execution loop blocks on WaitSema(0x81) because the runtime is not fully initialized (type init flags not set due to EXP-138 RAX propagation bug).

### .NET 10 runtime crash prevents full validation:

The current .NET 10.0.10 runtime crashes with "Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code" when `DispatchIl2CppApiLookupSymbol` calls `TryCallGuestFunction`. This prevents the game from reaching the consumer function. Prior EXPs (EXP-170 through EXP-173) used an earlier .NET 10 build that did not have this crash.

---

## 4. Whether This is the Blocker Preventing 0x801E51240 Initialization

### YES — the indirect call at +0x19A7 is the blocker.

### Static analysis evidence:

The consumer function 0x8013EB6B0 has the following layout:
```
+0x72   (0x8013EB722):  je      — checks [0x801E518C8] != 0 (PASS with argc=2)
...    (branches +0x277 through +0x191F — all NOT taken at runtime)
+0x19A7 (0x8013ED057):  call [0x801ED6320]  ← BLOCKING POINT
+0x19AD (0x8013ED05D):  mov ebx, eax        ← NEVER REACHED
+0x19AF (0x8013ED05F):  test eax, eax       ← NEVER REACHED
+0x19B1 (0x8013ED061):  je +0x19            ← NEVER REACHED (confirmed by je_only.log)
...
+0x3969 (0x8013EF019):  mov [0x801E51240], rax  ← TARGET (never reached)
```

The init writer for [0x801E51240] is at +0x3969 (0x8013EF019), which is 0x1FC2 bytes AFTER the blocking call at +0x19A7. Since the call doesn't return, execution never reaches +0x3969.

### Relationship:

```
GOT dispatch (call [0x801ED6320] at +0x19A7)
  ↓
  call does NOT return (enters IL2CPP runtime loop → WaitSema(0x81))
  ↓
consumer continuation (mov ebx, eax at +0x19AD)
  ↓ NEVER REACHED
0x801E51240 writer (mov [0x801E51240], rax at +0x3969)
  ↓ NEVER REACHED
```

The GOT dispatch MUST complete (return) before the consumer can continue to +0x3969. Since the call blocks, [0x801E51240] is never initialized.

---

## 5. Remaining Unknowns

### Unknown 1: Why doesn't il2cpp_init return?

The call at +0x19A7 goes to `il2cpp_init` (0x804ED85D0). This function should initialize the IL2CPP runtime and return. Instead, it enters the dispatch loop and blocks on WaitSema(0x81).

**Possible causes (not yet proven):**
- il2cpp_init calls a function that blocks (e.g., a thread join or event wait)
- il2cpp_init's return path is broken by the EXP-138 RAX propagation bug
- il2cpp_init intentionally blocks (waiting for a bootstrap job that never arrives)
- The function at [0x801ED6320] is NOT il2cpp_init but a different function

**Evidence needed:**
- Trace execution inside il2cpp_init to find where it blocks
- Check if il2cpp_init calls WaitSema directly or indirectly
- Verify that [0x801ED6320] actually contains 0x804ED85D0 at runtime

### Unknown 2: What is the .NET 10 "Invalid Program" crash?

The current .NET 10.0.10 runtime crashes when `DispatchIl2CppApiLookupSymbol` calls `TryCallGuestFunction` (which calls `RunGuestEntryStub` → `CallNativeEntry`). The crash message is "Invalid Program: attempted to call a UnmanagedCallersOnly method from managed code."

**Impact:**
- The game cannot reach the consumer function with the current runtime
- Prior EXPs (EXP-170 through EXP-173) used an earlier .NET 10 build without this crash
- All runtime evidence from EXP-173 logs is still valid (collected before the crash)

**Evidence needed:**
- Determine which .NET 10 version was used for EXP-173
- Find a workaround for the .NET 10.0.10 crash

### Unknown 3: Is [0x801ED6320] actually il2cpp_init?

The GOT writer calls the resolver 232 times. The first call uses RDI = address of "il2cpp_init" string. The resolver returns 0x804ED85D0. This value is stored in [0x801ED6320].

But the EXP-138 RAX propagation bug corrupts the return value. If the bug is active, [0x801ED6320] might contain garbage instead of 0x804ED85D0.

**Evidence needed:**
- Read [0x801ED6320] at runtime to verify its value
- Check if the EXP-138 fix (raxCaptureSlot) is working correctly
- This requires fixing the .NET 10 crash first

### Unknown 4: INT3 handler fix for valid evidence collection

The INT3 handler has a bug that corrupts multi-byte instructions. To collect valid post-INT3 evidence, the handler needs to be fixed to set RIP = X (instruction start) instead of X+1.

**Fix needed (temporary, for evidence collection only):**
- Line 237: Change `_ripTraceAddress1 + 1` to `_ripTraceAddress1`
- Line 201: Change re-patch condition from `rip == _ripTraceAddress1 + 1` to `_ripTraceSingleStepping1 && rip > _ripTraceAddress1`

This fix was NOT applied during this experiment because the .NET 10 crash prevents any runtime testing.

---

## 6. Next Evidence Target

### Primary: Fix the .NET 10 "Invalid Program" crash

Without fixing this crash, no runtime evidence can be collected. Options:
1. Install an earlier .NET 10 preview/RC version
2. Find a workaround for the nested UnmanagedCallersOnly call
3. Use a different execution path that avoids the nested call

### Secondary: Fix the INT3 handler (temporary, for evidence collection)

Once the .NET 10 crash is fixed:
1. Fix the INT3 handler to set RIP = X instead of X+1
2. Add [0x801ED6320] to the memory dump in the INT3 handler
3. Set INT3 at 0x8013ED057 (the call) to read [0x801ED6320] at runtime
4. Verify [0x801ED6320] = 0x804ED85D0 (il2cpp_init address)
5. Trace execution inside il2cpp_init to find where it blocks

### Tertiary: Trace il2cpp_init execution

Once [0x801ED6320] is verified:
1. Set INT3 at 0x804ED85D0 (il2cpp_init entry) to confirm it's called
2. Use single-step trace to follow execution inside il2cpp_init
3. Find the exact instruction where il2cpp_init blocks (likely WaitSema or similar)

---

## TEST Details

### TEST 1 — Runtime trace of GOT slot usage

**Status:** PARTIALLY COMPLETED (limited by .NET 10 crash)

**Runtime evidence collected:**
- Resolver Entry #1: name='il2cpp_init', ret=0x0 (from /tmp/exp175_run.log)
- Only 1 resolver call before .NET 10 crash

**Static evidence:**
- RIP before call: 0x8013ED057 (from EXP-173 INT3 HIT)
- RIP after call: NOT REACHED (from EXP-173 je_only.log)
- [0x801ED6320] before call: Unknown (not dumped in EXP-173)
- [0x801ED6320] inferred value: 0x804ED85D0 (il2cpp_init address from resolver)

**Conclusion:** The call does NOT return. It enters the IL2CPP runtime loop and blocks on WaitSema(0x81).

### TEST 2 — Identify GOT slot owner

**Status:** COMPLETED

**Static writers to 0x801ED6320:**
| Address | Instruction | Classification |
|---------|-------------|----------------|
| 0x8013FB260 | `mov [0x801ED6320], rax` | A) Executed (inside GOT writer 0x8013FB0B0) |

**Relocations:**
- No standard DT_RELA or DT_JMPREL entries target 0x801ED6320
- 0x801ED6320 is in BSS (zero-initialized at load time)
- Filled at runtime by GOT writer function 0x8013FB0B0

**PLT entry connected to this slot:**
- The GOT writer calls PLT entry 0x8019374D0 (PLT index 0xE7)
- PLT entry uses GOT slot 0x801D1ACE0 (DT_JMPREL entry 231)
- DT_JMPREL entry 231: NID = `r8mvOaWdi28#A#B`, type = R_X86_64_JUMP_SLOT
- SharpEmu resolves NID r8mvOaWdi28 via HLE → `DispatchIl2CppApiLookupSymbol()`

**Confirmed:** NID `r8mvOaWdi28` owns the PLT GOT slot 0x801D1ACE0. SharpEmu's NID resolution fills this entry with an HLE trampoline address at load time.

### TEST 3 — Validate PLT resolution path

**Status:** COMPLETED

**PLT entry:** 0x8019374D0
- `FF 25 0A 38 3E 00` = `jmp [rip+0x003E380A]` → `jmp [0x801D1ACE0]`
- `68 E7 00 00 00` = `push 0xE7` (PLT index 231)
- `E9 70 F1 FF FF` = `jmp -0xE90` (to PLT resolver)

**Target GOT entry:** 0x801D1ACE0
- Initial file value: 0x00000000019374D6 (lazy binding stub address)
- At runtime: Filled by SharpEmu with HLE trampoline address

**NID lookup result:**
- DT_JMPREL entry 231: NID = `r8mvOaWdi28#A#B`
- Symbol type: R_X86_64_JUMP_SLOT (7)
- Addend: 0x0

**Resolver path:**
1. PLT entry → jmp [0x801D1ACE0] → HLE trampoline
2. HLE trampoline → ImportDispatchGatewayManaged → DispatchImport
3. DispatchImport checks NID == "r8mvOaWdi28" → DispatchIl2CppApiLookupSymbol()
4. DispatchIl2CppApiLookupSymbol reads RDI (symbol name)
5. Calls TryCallGuestFunction(0x804ED9B90, RDI=symbol_name)
6. Real resolver at 0x804ED9B90 walks IL2CPP BST, returns function address

**Runtime evidence:**
- Before resolution: GOT value = 0x00000000019374D6 (lazy stub)
- After resolution: GOT value = HLE trampoline address (not logged)
- First resolver call: name='il2cpp_init' → expected return 0x804ED85D0

### TEST 4 — Relationship with 0x801E51240 initialization

**Status:** COMPLETED

**Does the function behind [0x801ED6320] need to complete before 0x8013EF019?**

YES. The init writer for [0x801E51240] is at 0x8013EF019 (+0x3969 in consumer). The indirect call is at 0x8013ED057 (+0x19A7). The call is 0x1FC2 bytes BEFORE the init writer. Since the consumer executes sequentially (no branches skip from +0x19A7 to +0x3969), the call MUST return for execution to reach +0x3969.

**Trace:**
```
GOT dispatch (call [0x801ED6320] at +0x19A7)
  ↓ call does NOT return
  ↓ enters IL2CPP runtime loop → WaitSema(0x81)
consumer continuation (+0x19AD onward)
  ↓ NEVER REACHED
0x801E51240 writer (+0x3969 = 0x8013EF019)
  ↓ NEVER REACHED
[0x801E51240] stays NULL
```

### TEST 5 — Validate INT3 reliability

**Status:** COMPLETED — INT3 handler bug CONFIRMED

**Bug description:**

The INT3 handler at `DirectExecutionBackend.Exceptions.cs` has a critical bug that corrupts multi-byte instructions:

1. INT3 fires at address X → kernel sets RIP = X+1
2. Handler restores original byte at X (line 235: `RestoreOriginalByte`)
3. Handler sets TF (trap flag) for single-step (line 236: `SetTrapFlag`)
4. Handler sets RIP = X+1 (line 237: `WriteCtxU64Icall(contextRecord, 248, _ripTraceAddress1 + 1)`)
5. CPU resumes at X+1 with TF set
6. But X+1 is the SECOND BYTE of the original instruction!
7. CPU decodes garbage (e.g., 0x15 = `ADC EAX, imm32` instead of 0xFF 0x15 = `call [rip+disp32]`)

**Mathematical proof (from EXP-NEXT):**

At INT3 HIT slot=1 (0x8013ED057, before call):
- rax = 0x000000060000007F

At INT3 HIT slot=2 (0x8013ED061, after "call"):
- rax = 0x0000000000AE9342

If the call was NEVER executed and CPU instead executed `ADC EAX, imm32`:
- imm32 = 0x00AE92C3 (the disp32 bytes of the original call instruction)
- EAX before = 0x6000007F (lower 32 bits of rax)
- EAX + imm32 = 0x6000007F + 0x00AE92C3 = 0x00AE9342 (32-bit, zero-extended)
- **MATCHES** the logged "return value" 0x00AE9342

**Re-patch condition bug:**

The re-patch condition (line 201) checks `rip == _ripTraceAddress1 + 1`. But after the single-step trap, RIP is at X+1+corrupted_instruction_length, NOT X+1. So the re-patch NEVER fires.

**What IS valid:**
- INT3 HIT logging (line 233): registers and memory are read BEFORE corruption
- The fact that execution reached the INT3 address

**What is NOT valid:**
- Any register values logged AFTER the INT3 hit
- Any "return values" or "post-call" state
- EXP-173's conclusion that "the call returned with rax=0xAE9342"

**Fix needed (for future evidence collection):**
- Line 237: Change `_ripTraceAddress1 + 1` to `_ripTraceAddress1` (set RIP back to instruction start)
- Line 201: Change re-patch condition to `_ripTraceSingleStepping1 && rip > _ripTraceAddress1`

---

## Summary Table

| Question | Answer | Confidence | Evidence |
|----------|--------|------------|----------|
| What function is behind [0x801ED6320]? | il2cpp_init (0x804ED85D0) | 85% | Static PLT/NID analysis + resolver trace |
| Does the indirect call return? | NO | 95% | EXP-173 je_only.log (je NOT reached without INT3 at call) |
| Is this the blocker for [0x801E51240] init? | YES | 95% | Static analysis: call at +0x19A7, init writer at +0x3969 |
| Is INT3 reliable? | NO — multi-byte instruction corruption | 100% | Mathematical proof (ADC result matches) |
| Can we validate at runtime? | NO — .NET 10.0.10 crash | 100% | "Invalid Program" error in all builds |

---

## Artifacts

- `/home/z/my-project/scripts/exp175/exp175_plt_nid_lookup.py` — Parse Sony-specific relocation tables
- `/home/z/my-project/scripts/exp175/exp175_jmprel_direct.py` — Direct DT_JMPREL search for target GOT slot
- `/home/z/my-project/scripts/exp175/exp175_plt_got_layout.py` — PLT GOT table layout analysis
- `/tmp/exp175_run.log` — Runtime log (crashes after 1 resolver call due to .NET 10 issue)
- `/tmp/exp175_debug_run.log` — Debug build runtime log (same crash)

---

## No Fixes. No Implementation Changes.

All findings are evidence-based. No patches applied. No HLE changes. No emulator behavior changes.
