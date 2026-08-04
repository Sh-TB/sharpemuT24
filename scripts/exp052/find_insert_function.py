#!/usr/bin/env python3
"""
EXP-052 Task A1b: Find the hash table INSERT function.

Strategy:
  1. The probe loop ends at 0x800806930 (ret). The next function at 0x800806940
     is likely the INSERT function (sibling pattern).
  2. Disassemble it.
  3. Find writers that match the insert pattern: read [0x801EF7610], then
     write to [reg+offset] where reg holds the entries base.
  4. Find callers of the insert function — these are the actual fillers.
"""
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX, find_rip_rel_refs_to, parse_elf_segments, EBOOT_BASE, PRX_BASE
import capstone

print("=" * 78)
print("EXP-052 Task A1b: Hash table INSERT function search")
print("=" * 78)

# Disassemble the function right after the probe loop
print("\n--- Function at 0x800806940 (likely INSERT) ---")
insns = disasm_at(EBOOT, 0x800806940, size=0x1000, label="hash_insert_candidate")
for ins in insns[:200]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

print("\n--- Also re-check probe loop fully (0x800806930 backwards) ---")
# Get earlier code
insns = disasm_at(EBOOT, 0x800806700, size=0x100, label="probe_pre")
for ins in insns[:30]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# Now: find all CALL sites targeting 0x800806940 (if it's the insert)
print("\n--- Searching for calls to 0x800806940 in eboot ---")
segments = parse_elf_segments(EBOOT, load_base=EBOOT_BASE)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True
callers = []
for seg in segments:
    if seg["type"] != 1 or not (seg["flags"] & 1):
        continue
    data = seg["content"]
    seg_base = seg["runtime_vaddr"]
    for insn in md.disasm(data, seg_base):
        if insn.mnemonic != "call":
            continue
        if not insn.operands:
            continue
        op = insn.operands[0]
        if op.type == capstone.x86.X86_OP_IMM and op.imm == 0x800806940:
            callers.append(insn.address)
        # Also check the probe function and other candidates
        if op.type == capstone.x86.X86_OP_IMM and op.imm in (0x800806800, 0x800806700, 0x800806780, 0x800806940, 0x800806990):
            print(f"  call to 0x{op.imm:X} at 0x{insn.address:X}")

print(f"\n  Found {len(callers)} direct callers of 0x800806940")
for c in callers[:30]:
    print(f"    0x{c:X}")

# Now: find ALL reads of 0x801EF7610 (entries base)
print("\n--- ALL references to 0x801EF7610 (entries array base) in eboot ---")
results = find_rip_rel_refs_to(EBOOT, 0x801EF7610, max_results=500)
print(f"  Found {len(results)} references")
for addr, role, txt in results[:60]:
    print(f"  0x{addr:X} [{role}] {txt}")

# Also check the hash table struct pointer at 0x801E51618
print("\n--- ALL references to 0x801E51618 (hash table struct) in eboot ---")
results = find_rip_rel_refs_to(EBOOT, 0x801E51618, max_results=500)
print(f"  Found {len(results)} references")
for addr, role, txt in results[:60]:
    print(f"  0x{addr:X} [{role}] {txt}")
