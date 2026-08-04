#!/usr/bin/env python3
"""EXP-042 Task 1: Full callback chain disassembly.

Disassemble completely:
- 0x80134FA00 (the eboot.bin callback entry, called from PRX real_init call #7)
- 0x800C66B40 (metadata lookup, called via [0x801EA49D8])
- 0x80135DDD0 (crash function, called via vtable[0])

For each function, report:
- Every conditional branch (JE, JNE, JAE, etc.)
- Every CMP/TEST instruction
- Every global variable involved
- Every memory read before reaching 0x801E51240
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

def disasm_function(addr, label, max_insns=100):
    offset = addr - IMAGE_BASE + 0x4000
    if offset >= len(data) or offset < 0:
        print(f"\n{'='*70}")
        print(f"=== {label} at 0x{addr:X} — OUT OF RANGE ===")
        return
    chunk = data[offset:offset + max_insns * 16]
    print(f"\n{'='*70}")
    print(f"=== {label} at 0x{addr:X} ===")
    print(f"{'='*70}")
    count = 0
    for insn in md.disasm(chunk, addr):
        annotation = ""
        # Annotate RIP-relative
        for op in insn.operands:
            if op.type == 3 and op.mem.base == 41:  # RIP
                target = insn.address + insn.size + op.mem.disp
                annotation = f"  -> 0x{target:X}"
                break
        
        # Mark branches
        branch_note = ""
        if insn.mnemonic in ("je", "jne", "jae", "jb", "ja", "jbe", "jg", "jge", "jl", "jle", "jne", "jo", "jno", "js", "jns", "jmp"):
            branch_note = "  [BRANCH]"
        elif insn.mnemonic in ("cmp", "test"):
            branch_note = "  [COMPARE]"
        elif insn.mnemonic == "call":
            if "rip" in insn.op_str or "[" in insn.op_str:
                branch_note = "  [INDIRECT CALL]"
            else:
                branch_note = "  [CALL]"
        elif insn.mnemonic == "ret":
            branch_note = "  [RET]"
        
        print(f"  {insn.address:X}: {insn.mnemonic:8s} {insn.op_str}{annotation}{branch_note}")
        count += 1
        if count >= max_insns or insn.mnemonic == "ret":
            break

# Disassemble the three functions
disasm_function(0x80134FA00, "Callback entry (called from PRX real_init call #7)", 80)
disasm_function(0x800C66B40, "Metadata lookup (called via [0x801EA49D8])", 60)
disasm_function(0x80135DDD0, "Crash function (vtable[0], reads 0x801E51240)", 80)
