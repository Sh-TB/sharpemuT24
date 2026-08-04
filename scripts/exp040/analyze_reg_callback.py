#!/usr/bin/env python3
"""EXP-040 Task 1: Analyze a registration callback function.

From EXP-039, the registration iterator at 0x800B8D530 calls each entry's
function pointer at [rax+0x10] with argument [rax+0x8].

The linked list head is at 0x801E9DF28. The entries are built by 895
registration functions (like 0x800454530).

Let me disassemble a registration function to see EXACTLY what it does:
1. Does it call il2cpp_add_internal_call?
2. Does it write to the hash table entries?
3. What does it register?
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Registration function at 0x800454530 (from EXP-039)
func_addr = 0x800454530
offset = func_addr - IMAGE_BASE + 0x4000
chunk = data[offset:offset+512]

print(f"=== Registration function at 0x{func_addr:X} ===")
for insn in md.disasm(chunk, func_addr):
    # Annotate RIP-relative targets
    annotation = ""
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:  # RIP
            target = insn.address + insn.size + op.mem.disp
            annotation = f"  -> 0x{target:X}"
            break
    
    # Highlight calls
    call_target = ""
    if insn.mnemonic == "call":
        if "rip" in insn.op_str:
            for op in insn.operands:
                if op.type == 3 and op.mem.base == 41:
                    t = insn.address + insn.size + op.mem.disp
                    call_target = f"  [INDIRECT CALL -> 0x{t:X}]"
                    break
        else:
            call_target = "  [DIRECT CALL]"
    
    print(f"  {insn.address:X}: {insn.mnemonic} {insn.op_str}{annotation}{call_target}")
    if insn.mnemonic == 'ret' or insn.address > func_addr + 300:
        break

# Also check: what global does this function write to?
# From EXP-039, registration functions write to 0x801E9DF28 (list head)
# Let me verify this function does too.
print(f"\n=== Checking if 0x{func_addr:X} writes to list head 0x801E9DF28 ===")
target_global = 0x801E9DF28
for insn in md.disasm(chunk, func_addr):
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:
            t = insn.address + insn.size + op.mem.disp
            if t == target_global:
                is_write = "," in insn.op_str and "[" in insn.op_str.split(",")[0]
                print(f"  0x{insn.address:X}: {insn.mnemonic} {insn.op_str} [{'WRITE' if is_write else 'READ'}]")
    if insn.mnemonic == 'ret':
        break
