#!/usr/bin/env python3
"""EXP-041 Task 1: Fully disassemble real_init (0x804F04BA0).

Focus on:
- Call #7 (the crashing indirect callback at 0x804F04C5C)
- The gap between call #7 and calls #8-18
- Calls #18-80 (repeated calls to 0x804EEE8D0)

The goal is to understand:
1. What call #7 does and why it crashes
2. Whether calls #8-80 should run BEFORE call #7
3. Whether 0x804EEE8D0 fills the hash table
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

PRX = Path("/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx")
PRX_BASE = 0x804CD5000

data = PRX.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# real_init at 0x804F04BA0
# vaddr_in_prx = 0x804F04BA0 - 0x804CD5000 = 0x22FBA0
# file offset = 0x22FBA0 + 0x4000 = 0x233BA0
addr = 0x804F04BA0
offset = 0x233BA0
chunk = data[offset:offset+8192]  # 8KB to cover all 80 calls

print(f"=== real_init 0x{addr:X} — full disassembly with call annotations ===")
print()

call_num = 0
for insn in md.disasm(chunk, addr):
    annotation = ""
    
    # Annotate RIP-relative targets
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:
            target = insn.address + insn.size + op.mem.disp
            annotation = f"  -> 0x{target:X}"
            break
    
    # Annotate calls
    if insn.mnemonic == "call":
        call_num += 1
        if "rip" in insn.op_str or "[" in insn.op_str:
            # Indirect call
            for op in insn.operands:
                if op.type == 3 and op.mem.base == 41:
                    t = insn.address + insn.size + op.mem.disp
                    annotation += f"  [INDIRECT -> [0x{t:X}]]"
                    break
            annotation = f"  *** CALL #{call_num} ***" + annotation
        else:
            try:
                target = int(insn.op_str, 16)
                annotation = f"  *** CALL #{call_num} -> 0x{target:X} ***"
            except:
                annotation = f"  *** CALL #{call_num} ***"
    
    # Annotate ret
    if insn.mnemonic == "ret":
        annotation = "  *** RET ***"
    
    # Only print calls, rets, and key instructions
    if insn.mnemonic in ("call", "ret", "je", "jne", "jmp", "jae", "jb") or "call" in str(call_num):
        if insn.mnemonic == "call" or insn.mnemonic == "ret":
            print(f"  {insn.address:X}: {insn.mnemonic} {insn.op_str}{annotation}")
    
    if call_num >= 85 or insn.mnemonic == "ret":
        break

print(f"\nTotal calls: {call_num}")
