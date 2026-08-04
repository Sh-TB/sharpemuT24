#!/usr/bin/env python3
"""EXP-050 Task 1: Find ALL writes to 0x801EA4E80 (metadata list lazy-init pointer).

The metadata list at [0x801EA4E80] is populated by registration functions.
0x800C66670 creates the initial list (empty, self-referencing).
Something else adds entries with flag=0.

Search for ALL writes to 0x801EA4E80 in eboot.bin.
"""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000
TARGET = 0x801EA4E80

data = EBOOT.read_bytes()

# Fast scan for RIP-relative writes (MOV [rip+disp32], reg)
text_start = 0x4000
text_size = 0x1938C2C
writes = []
reads = []

for i in range(text_start, text_start + text_size - 7):
    insn_vaddr = i - 0x4000 + IMAGE_BASE
    if data[i] in (0x48, 0x4C):
        if data[i+1] == 0x89:  # MOV [rip+disp32], reg (WRITE)
            modrm = data[i+2]
            if (modrm & 0xC7) == 0x05:
                disp32 = struct.unpack_from('<i', data, i+3)[0]
                effective = insn_vaddr + 7 + disp32
                if effective == TARGET:
                    reg_idx = ((modrm >> 3) & 7)
                    reg_names = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']
                    reg = reg_names[reg_idx + (8 if data[i] == 0x4C else 0)]
                    writes.append((insn_vaddr, reg))
        elif data[i+1] == 0x8B:  # MOV reg, [rip+disp32] (READ)
            modrm = data[i+2]
            if (modrm & 0xC7) == 0x05:
                disp32 = struct.unpack_from('<i', data, i+3)[0]
                effective = insn_vaddr + 7 + disp32
                if effective == TARGET:
                    reads.append(insn_vaddr)

print(f"=== Writes to 0x{TARGET:X} (metadata list lazy-init pointer) ===")
print(f"Total writes: {len(writes)}")
for addr, reg in writes:
    # Find containing function
    target_foff = addr - IMAGE_BASE + 0x4000
    pattern = b'\x55\x48\x89\xe5'
    pos = data.rfind(pattern, max(0, target_foff - 0x2000), target_foff)
    func_name = f"0x{pos - 0x4000 + IMAGE_BASE:X}" if pos >= 0 else "unknown"
    print(f"  0x{addr:X}: MOV [0x{TARGET:X}], {reg}  (in func {func_name})")

print(f"\nTotal reads: {len(reads)}")
print(f"First 5 reads:")
for addr in reads[:5]:
    print(f"  0x{addr:X}")

# Also check: does 0x800C66670 write to 0x801EA4E80?
# From EXP-042: 0x800C666F0: mov [0x801EA4E80], rbx
# This is the ONLY write. rbx is the allocated structure.
# But the METADATA LIST ENTRIES are added to the structure, not to 0x801EA4E80 itself.
# The entries are added to the linked list INSIDE the structure (at [rbx+8]).
# So writes to 0x801EA4E80 = 1 (the initial setup by 0x800C66670).
# The entries are added via writes to [rbx+8] or similar.

# Let me check: what does 0x800C66670 store in the structure?
print(f"\n=== 0x800C66670 structure setup ===")
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

addr = 0x800C66670
offset = addr - IMAGE_BASE + 0x4000
chunk = data[offset:offset+256]
for insn in md.disasm(chunk, addr):
    annotation = ""
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:
            target = insn.address + insn.size + op.mem.disp
            annotation = f"  -> 0x{target:X}"
            break
    if insn.mnemonic in ("mov", "call", "ret", "lea"):
        print(f"  {insn.address:X}: {insn.mnemonic:8s} {insn.op_str}{annotation}")
    if insn.mnemonic == "ret":
        break
