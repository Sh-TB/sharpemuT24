#!/usr/bin/env python3
"""EXP-040 Task 3: Analyze real_init (0x804F04BA0) call sequence.

The real_init function calls many sub-functions. One of them should
populate the hash table at 0x801EF7610. Let me disassemble real_init
and list all its CALL instructions.
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
# vaddr in PRX = 0x804F04BA0 - 0x804CD5000 = 0x22FBA0
# file offset = 0x22FBA0 + 0x4000 = 0x233BA0
addr = 0x804F04BA0
offset = 0x233BA0
chunk = data[offset:offset+4096]  # 4KB

print(f"=== real_init 0x{addr:X} — first 80 CALL instructions ===")
call_count = 0
for insn in md.disasm(chunk, addr):
    if insn.mnemonic == "call":
        call_count += 1
        # Determine target
        target_str = insn.op_str
        is_indirect = "rip" in target_str or "[" in target_str
        annotation = ""
        
        if is_indirect:
            for op in insn.operands:
                if op.type == 3 and op.mem.base == 41:  # RIP-relative
                    t = insn.address + insn.size + op.mem.disp
                    annotation = f"  -> [0x{t:X}] (indirect)"
                    break
        else:
            # Direct call
            try:
                target = int(target_str, 16)
                annotation = f"  -> 0x{target:X}"
            except:
                annotation = f"  -> {target_str}"
        
        print(f"  [{call_count:3d}] 0x{insn.address:X}: call {target_str}{annotation}")
        
        if call_count >= 80:
            break
    
    if insn.address > addr + 4000:
        break

print(f"\nTotal calls found: {call_count}")
