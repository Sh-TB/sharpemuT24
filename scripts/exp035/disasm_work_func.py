#!/usr/bin/env python3
"""Disassemble the work function at 0x800AA0170 (the [obj+0x28] field)."""
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = "/tmp/games/yatzi/eboot.bin"
IMAGE_BASE = 0x800000000
FILE_OFFSET_DELTA = 0x4000

data = open(EBOOT, "rb").read()
md = Cs(CS_ARCH_X86, CS_MODE_64)

# Disassemble the work function at 0x800AA0170
# This is [obj+0x28] — called from the thread entry at 0x800BB074B
start_vaddr = 0x800AA0170
start_offset = (start_vaddr - IMAGE_BASE) + FILE_OFFSET_DELTA
chunk = data[start_offset:start_offset + 256]

print(f"=== Work function at 0x{start_vaddr:X} ([obj+0x28]) ===")
for insn in md.disasm(chunk, start_vaddr):
    print(f"  {insn.address:X}: {insn.mnemonic} {insn.op_str}")
    if insn.mnemonic == "ret" or insn.address > start_vaddr + 200:
        break

print()

# Also disassemble a wider range around 0x800AA01B0 (the dispatch loop)
# to understand the full loop structure
print(f"=== Dispatch loop context (0x800AA00F0..0x800AA0260) ===")
loop_start = 0x800AA00F0
loop_offset = (loop_start - IMAGE_BASE) + FILE_OFFSET_DELTA
chunk = data[loop_offset:loop_offset + 0x180]
for insn in md.disasm(chunk, loop_start):
    print(f"  {insn.address:X}: {insn.mnemonic} {insn.op_str}")
    if insn.address > loop_start + 0x160:
        break
