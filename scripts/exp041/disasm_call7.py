#!/usr/bin/env python3
"""EXP-041 Task 2: Disassemble around call #7 to understand the indirect callback.

Call #7 is at 0x804F04C5C: call [rax]
We need to understand:
1. What sets rax before this call
2. What [rax] points to
3. Why the callback crashes
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

PRX = Path("/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx")
PRX_BASE = 0x804CD5000

data = PRX.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Disassemble from call #6 to call #8 (around call #7)
# Call #6 is at 0x804F04C50
# Call #7 is at 0x804F04C5C
# Call #8 is at 0x804F04C5E (immediately after!)
addr = 0x804F04C40
offset = addr - PRX_BASE + 0x4000  # 0x22FC40 + 0x4000 = 0x233C40
chunk = data[offset:offset+128]

print(f"=== Context around call #7 (0x804F04C5C) ===")
for insn in md.disasm(chunk, addr):
    annotation = ""
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:
            target = insn.address + insn.size + op.mem.disp
            annotation = f"  -> 0x{target:X}"
            break
    
    marker = ""
    if insn.address == 0x804F04C5C:
        marker = "  *** CALL #7 (CRASH) ***"
    elif insn.address == 0x804F04C5E:
        marker = "  *** CALL #8 ***"
    
    print(f"  {insn.address:X}: {insn.mnemonic} {insn.op_str}{annotation}{marker}")
    if insn.address > 0x804F04C70:
        break

# Also check: what sets rax before call #7
print(f"\n=== Instructions setting rax before call #7 ===")
addr = 0x804F04C50
offset = addr - PRX_BASE + 0x4000
chunk = data[offset:offset+32]
for insn in md.disasm(chunk, addr):
    if "rax" in insn.op_str or "eax" in insn.op_str:
        annotation = ""
        for op in insn.operands:
            if op.type == 3 and op.mem.base == 41:
                target = insn.address + insn.size + op.mem.disp
                annotation = f"  -> 0x{target:X}"
                break
        print(f"  {insn.address:X}: {insn.mnemonic} {insn.op_str}{annotation}")
    if insn.address >= 0x804F04C5C:
        break
