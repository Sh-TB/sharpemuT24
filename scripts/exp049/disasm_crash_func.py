#!/usr/bin/env python3
"""EXP-049 Task A: Disassemble 0x801431FB0 and find the NULL pointer source.

The crash is at 0x8014327CF: reads [reg+0xF4] where reg=NULL.
Find which register holds the NULL pointer and trace it back to its source.
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Function at 0x801431FB0
addr = 0x801431FB0
offset = addr - IMAGE_BASE + 0x4000
chunk = data[offset:offset+2048]  # 2KB

print(f"=== Function 0x{addr:X} (crash at 0x8014327CF) ===")
print(f"Looking for: instruction at 0x8014327CF that reads [reg+0xF4]")
print()

for insn in md.disasm(chunk, addr):
    annotation = ""
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:  # RIP-relative
            target = insn.address + insn.size + op.mem.disp
            annotation = f"  -> 0x{target:X}"
            break
    
    marker = ""
    if insn.address == 0x8014327CF:
        marker = " <<< CRASH HERE"
    
    # Highlight reads from [reg+0xF4]
    if "0xf4" in insn.op_str.lower() or "0xF4" in insn.op_str:
        marker += " [reads +0xF4]"
    
    # Highlight global reads (0x801E51240, etc.)
    if annotation and "0x801E" in annotation:
        marker += " *** GLOBAL ***"
    
    if insn.mnemonic in ("call", "ret", "je", "jne", "jae", "jb", "jmp"):
        print(f"  {insn.address:X}: {insn.mnemonic:8s} {insn.op_str}{annotation}{marker}")
    elif marker:
        print(f"  {insn.address:X}: {insn.mnemonic:8s} {insn.op_str}{annotation}{marker}")
    
    if insn.address > 0x801432830:
        break

# Also disassemble around the crash site specifically
print(f"\n=== Context around crash at 0x8014327CF ===")
addr2 = 0x8014327A0
offset2 = addr2 - IMAGE_BASE + 0x4000
chunk2 = data[offset2:offset2+128]
for insn in md.disasm(chunk2, addr2):
    annotation = ""
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:
            target = insn.address + insn.size + op.mem.disp
            annotation = f"  -> 0x{target:X}"
            break
    marker = " <<< CRASH" if insn.address == 0x8014327CF else ""
    print(f"  {insn.address:X}: {insn.mnemonic:8s} {insn.op_str}{annotation}{marker}")
    if insn.address > 0x801432800:
        break
