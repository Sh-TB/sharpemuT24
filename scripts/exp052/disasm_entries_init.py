#!/usr/bin/env python3
"""
EXP-052 Task A1i: Disassemble entries_init 0x8007F9690.
This is called by the writer to initialize the entries array.
It probably allocates the entries array and updates struct[0] and struct[8].
"""
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX
import capstone

# Disassemble 0x8007F9690
print("=" * 78)
print("0x8007F9690 — entries_init function (called by writer)")
print("=" * 78)
insns = disasm_at(EBOOT, 0x8007F9690, size=0x600, label="entries_init")
for ins in insns[:120]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# Find all RIP-relative writes
print()
print("--- RIP-relative writes in entries_init ---")
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

# Find all CALL targets
print()
print("--- Call targets in entries_init ---")
for ins in insns:
    if ins.mnemonic == "call":
        print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
