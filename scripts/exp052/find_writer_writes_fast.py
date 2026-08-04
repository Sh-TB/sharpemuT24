#!/usr/bin/env python3
"""
EXP-052 Task A1h (fast): Find all RIP-relative writes in writer 0x8007F90A0.
"""
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX
import capstone

# Full disassembly of writer
print("=" * 78)
print("Full disassembly of hash table writer 0x8007F90A0")
print("=" * 78)
insns = disasm_at(EBOOT, 0x8007F90A0, size=0x1200, label="writer_full")

# Find all RIP-relative writes and their effective addresses
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

print("\n--- RIP-relative writes in writer ---")
for ins in insns:
    if not ins.operands:
        continue
    op0 = ins.operands[0]
    if op0.type != capstone.x86.X86_OP_MEM:
        continue
    if op0.mem.base != capstone.x86.X86_REG_RIP:
        continue
    eff = ins.address + ins.size + op0.mem.disp
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str:50s} -> [0x{eff:X}]")

print("\n--- RIP-relative reads in writer ---")
for ins in insns:
    for i, op in enumerate(ins.operands):
        if op.type != capstone.x86.X86_OP_MEM:
            continue
        if op.mem.base != capstone.x86.X86_REG_RIP:
            continue
        if i == 0:
            continue  # already shown as write
        eff = ins.address + ins.size + op.mem.disp
        print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str:50s} -> [0x{eff:X}]")

# Also: find ALL call targets in writer
print("\n--- Call targets in writer ---")
for ins in insns:
    if ins.mnemonic == "call":
        print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
