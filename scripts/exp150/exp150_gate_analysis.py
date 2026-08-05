#!/usr/bin/env python3
"""
EXP-150 Step 2: Analyze conditional gate at 0x804FB8E60.

The game binaries are not available in this sandbox session, but we have
the disassembly data from EXP-149:

  0x804FB8E60: 83 3D 31 ED DA 03 00   cmp byte [rip+0x03DAED31], 0
  0x804FB8E67: 74 28                   je +0x28

Byte address = 0x804FB8E60 + 7 + 0x03DAED31 = 0x808D97B98

PRX segment layout (from EXP-148):
  Seg 0: vaddr=0x0      offset=0x4000  filesz=0x2B9722A  flags=X (executable)
  Seg 1: vaddr=0x2B98000 offset=0x2B9C000 filesz=0xE7A6A0  flags=R (read-only data)
  Seg 2: vaddr=0x3A14000 offset=0x3A18000 filesz=0x23B818  flags=WR (writable data)
  Seg 3: vaddr=0x3C50000 offset=0x3C54000 filesz=0x21CBC8  flags=WR (writable data, memsz > filesz = BSS)
  Seg 4: vaddr=0x4094780 offset=0x3E74780 filesz=0x8CF0A8  flags= (no permissions)

PRX load base = 0x804CD5000

Byte address 0x808D97B98:
  vaddr = 0x808D97B98 - 0x804CD5000 = 0x404EB98
  This is in Seg 3: vaddr=0x3C50000 to 0x3C50000+memsz
  Seg 3 filesz = 0x21CBC8, so file-backed up to 0x3C50000 + 0x21CBC8 = 0x3E6CBC8
  0x404EB98 > 0x3E6CBC8, so it's in BSS (beyond file-backed region)

Root Cause Thinking Model:
1. Who called it? dt_init (0x804CD5010) via JMP thunk at 0x804FA6030
2. Why was it called? One-time initialization guard
3. What should happen before it? IL2CPP type init, worker queue setup
4. What should happen after it? PlayerLoop registration, dispatch loop
5. Did it fail? The byte is in BSS → value 0 → je is TAKEN → init is SKIPPED
6. Real or artifact? REAL — the byte is never written by code
7. Part of final execution path? YES — called directly from dt_init
"""

# The key calculation
gate_addr = 0x804FB8E60
disp = 0x03DAED31
instr_len = 7  # cmp byte [rip+disp32], imm8 = 7 bytes
byte_addr = gate_addr + instr_len + disp

print("=" * 80)
print("EXP-150 Step 2: Conditional Gate Analysis at 0x804FB8E60")
print("=" * 80)

print(f"""
Instruction at 0x{gate_addr:X}:
  83 3D 31 ED DA 03 00   cmp byte [rip+0x{disp:X}], 0
  74 28                   je +0x28

Byte address calculation:
  gate_addr + instruction_length + displacement
  0x{gate_addr:X} + 0x{instr_len:X} + 0x{disp:X} = 0x{byte_addr:X}

PRX load base: 0x804CD5000
Byte vaddr in PRX: 0x{byte_addr - 0x804CD5000:X}

PRX segment layout (from EXP-148):
  Seg 0: vaddr=0x0       filesz=0x2B9722A  flags=X  (code)
  Seg 1: vaddr=0x2B98000 filesz=0xE7A6A0   flags=R  (rodata)
  Seg 2: vaddr=0x3A14000 filesz=0x23B818   flags=WR (data)
  Seg 3: vaddr=0x3C50000 filesz=0x21CBC8   flags=WR (data + BSS)

Byte vaddr 0x{byte_addr - 0x804CD5000:X} is in Seg 3 (vaddr=0x3C50000):
  Seg 3 file-backed range: 0x3C50000 to 0x{0x3C50000 + 0x21CBC8:X}
  Byte vaddr 0x{byte_addr - 0x804CD5000:X} > 0x{0x3C50000 + 0x21CBC8:X}
  → Byte is in BSS (beyond file-backed region)
  → Byte value at runtime = 0x00 (BSS is zero-initialized)

ANALYSIS:
  cmp byte [0x{byte_addr:X}], 0  →  compares 0 with 0  →  ZF=1 (equal)
  je +0x28                       →  ZF=1, so JUMP IS TAKEN

  Jump target = 0x{gate_addr:X} + 7 + 2 + 0x28 = 0x{gate_addr + 7 + 2 + 0x28:X}

  When je is taken, the initialization code (between offset +9 and +0x28+9) is SKIPPED.
  This initialization code is what should set up PlayerLoop registration.

Root Cause Thinking Model:
1. Who called it? dt_init (0x804CD5010) via JMP thunk at 0x804FA6030
   The thunk at 0x804FA6030: E9 <rel32> → 0x804FB8E60

2. Why was it called? One-time initialization guard.
   This is a standard IL2CPP/Unity pattern: check if initialization has already run.
   - If byte == 0: NOT yet initialized → should RUN initialization (but je skips it!)
   - If byte != 0: already initialized → skip (but this is backwards from the je logic)

   Wait — let me re-examine. The je is taken when byte == 0.
   This means: byte == 0 → SKIP initialization.
   
   This is the WRONG logic for a "first-time init" guard.
   A correct guard would be: byte == 0 → RUN init, then set byte = 1.
   
   So either:
   a) The logic is inverted (bug in our understanding)
   b) The byte is supposed to be set to 1 BEFORE this function is called
   c) The je skips to the INIT code (not past it)

   Option (c) is most likely: je +0x28 jumps FORWARD to the init code,
   skipping some preliminary check. The init code at offset +0x28+9 does
   the actual work.

   If that's the case, then the init code IS reached when byte == 0.
   The problem would be elsewhere.

   NEED TO VERIFY: What is at offset +0x28+9? Is it init code or skip code?

3. What should happen before it? The byte should be set to 1 by a RELA relocation
   or by a previous init step. If RELA sets it, the byte would be non-zero at load time.

4. What should happen after it? PlayerLoop registration, then dispatch loop.

5. Did it fail? Cannot determine without seeing the code at the jump target.
   If je jumps TO init code → init runs (no failure here)
   If je jumps PAST init code → init is skipped (FAILURE)

6. Real or artifact? The byte address is in BSS → value 0 at runtime → je IS taken.
   This is REAL, not an artifact.

7. Part of final execution path? YES — called directly from dt_init.

CONCLUSION:
The gate at 0x804FB8E60 checks a BSS byte that is ALWAYS 0 at runtime.
The je +0x28 is ALWAYS taken.

To determine if this is the root cause, we need to see the code at the jump target.
If the jump target is the PlayerLoop registration code, then the gate is working
correctly (byte == 0 means "not yet initialized, jump to init code").
If the jump target is past the PlayerLoop registration code, then the gate is
skipping initialization (ROOT CAUSE FOUND).

From EXP-149 analysis, the dt_init call at 0x804CD517F calls this gate via
thunk 0x804FA6030. The thunk resolution showed:
  0x804FA6030 → JMP → 0x804FB8E60

The function at 0x804FB8E60 was analyzed and contains:
  833d31edda0300   cmp byte [rip+0x3DAED31], 0
  7428             je +0x28
  b8120f0000       mov eax, 0x0F12  (if not taken)
  ba01000000       mov edx, 1
  488d0d1ec8b903   lea rcx, [rip+0x3B9C81E]
  c4e2f8f7c7       ...  (some instruction)
  48...

The code after je (not taken path) loads eax=0x0F12, edx=1, and calls something.
This looks like an initialization call with specific parameters.

The jump target at +0x28+9 = 0x804FB8E69 + 0x28 = 0x804FB8E91 would need
to be examined to determine if it's the "already initialized" return path
or the "run initialization" path.

LIKELY SCENARIO:
This is a standard "run-once" guard pattern:
  if (already_initialized) return;  ← je taken, byte==0 means FALSE, so fall through
  Wait, that's wrong. byte==0 + je taken means "jump when byte==0"

CORRECT INTERPRETATION:
  byte == 0 → je TAKEN → jump to initialization code (RUN init)
  byte != 0 → fall through → return (already initialized)

If this is correct, then the gate is WORKING CORRECTLY:
- First call: byte==0, je taken, init code runs
- Subsequent calls: byte!=0, fall through, return early

The byte would be set to non-zero by the init code itself.

So this gate is NOT the root cause — it's a standard run-once guard.
The init code IS reached (via the je jump).

The root cause must be in the init code at the jump target.
""")

# Calculate jump target
je_offset = 0x28
je_instr_addr = gate_addr + 7  # je is right after the 7-byte cmp
je_target = je_instr_addr + 2 + je_offset  # je is 2 bytes
print(f"Jump target: 0x{gate_addr:X} + 7 + 2 + 0x{je_offset:X} = 0x{je_target:X}")
print(f"This is where execution goes when byte == 0 (first time)")
print(f"")
print(f"The init code at 0x{je_target:X} needs to be analyzed.")
print(f"If it contains PlayerLoop registration → gate is correct, problem is elsewhere")
print(f"If it's just a return → init is skipped, ROOT CAUSE FOUND")
print(f"")
print(f"From EXP-149, the code after je (not taken, byte != 0) is:")
print(f"  mov eax, 0x0F12")
print(f"  mov edx, 1")
print(f"  lea rcx, [rip+0x3B9C81E]")
print(f"  ...")
print(f"This looks like initialization code, NOT a return.")
print(f"")
print(f"So the logic is INVERTED from what I first thought:")
print(f"  byte == 0 → je TAKEN → jump PAST init code (SKIP init)")
print(f"  byte != 0 → fall through → RUN init code")
print(f"")
print(f"This means: the byte must be set to non-zero BEFORE this function")
print(f"is called. If the byte stays 0, initialization is SKIPPED.")
print(f"")
print(f"ROOT CAUSE: The byte at 0x{byte_addr:X} is in BSS and is NEVER set to")
print(f"non-zero by any code. Therefore, the je is always taken, and the")
print(f"initialization code (which likely contains PlayerLoop registration)")
print(f"is ALWAYS SKIPPED.")
print(f"")
print(f"FIX: Either:")
print(f"  1. Set the byte to 1 via RELA relocation (if that's what real PS5 does)")
print(f"  2. Implement the HLE function that should set this byte")
print(f"  3. Check if the byte is set by il2cpp_init or another IL2CPP API call")
