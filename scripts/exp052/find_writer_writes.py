#!/usr/bin/env python3
"""
EXP-052 Task A1h: Find all writes the hash table writer 0x8007F90A0 makes.
Specifically: where does it store the 0x118-byte hash table struct pointer?
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
    is_write = True  # destination operand
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

# Also find ALL call targets in writer
print("\n--- Call targets in writer ---")
for ins in insns:
    if ins.mnemonic == "call":
        print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# Also: find ALL references to 0x801C51900 (the wrapper's hash table source)
# This will tell us where this hash table is stored.
print()
print("=" * 78)
print("Searching for refs to 0x801C51900 (wrapper's hash table source)")
print("=" * 78)

# Use byte-level scan but only for this one address — fast
import struct
from analyze_hash_table_writes import parse_elf_segments, EBOOT_BASE

base = EBOOT_BASE
segments = parse_elf_segments(EBOOT, load_base=base)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

target = 0x801C51900
results = []
for seg in segments:
    if seg["type"] != 1 or not (seg["flags"] & 1):
        continue
    data = seg["content"]
    seg_base = seg["runtime_vaddr"]
    n = len(data)
    # For each position, try decode one instruction; check if RIP-relative to target
    for i in range(0, n - 15):
        try:
            ins_list = list(md.disasm(data[i:i+15], seg_base + i, count=1))
        except:
            continue
        if not ins_list:
            continue
        insn = ins_list[0]
        for op in insn.operands:
            if op.type != capstone.x86.X86_OP_MEM:
                continue
            if op.mem.base != capstone.x86.X86_REG_RIP:
                continue
            eff = insn.address + insn.size + op.mem.disp
            if eff == target:
                is_write = (op == insn.operands[0])
                role = "W" if is_write else "R"
                results.append((insn.address, role, str(insn)))
                break

print(f"Found {len(results)} refs to 0x{target:X}")
for addr, role, txt in results[:30]:
    print(f"  0x{addr:X} [{role}] {txt}")
