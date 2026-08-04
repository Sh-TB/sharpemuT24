#!/usr/bin/env python3
"""
EXP-052 Task A1g: Disassemble 0x8004bd620 to find what hash table it reads.
Also check 0x800ce3aa0 (hash generator) and the full sequence at 0x8013EEF00.
"""
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX

# Disassemble 0x8004bd620 — the actual lookup function
print("=" * 78)
print("0x8004bd620 — IL2CPP metadata lookup function (called from 0x8013EEFE7)")
print("=" * 78)
insns = disasm_at(EBOOT, 0x8004bd620, size=0x800, label="metadata_lookup_func")
for ins in insns[:120]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# Disassemble 0x800ce3aa0 — hash key generator
print()
print("=" * 78)
print("0x800ce3aa0 — hash key generator (called before lookup)")
print("=" * 78)
insns = disasm_at(EBOOT, 0x800ce3aa0, size=0x400, label="hash_key_gen")
for ins in insns[:60]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# Also re-disassemble the init function around 0x8013EEF00 to see the full picture
print()
print("=" * 78)
print("Init function around 0x8013EEF00 — full sequence")
print("=" * 78)
insns = disasm_at(EBOOT, 0x8013EEE00, size=0x300, label="init_func_around_lookup")
for ins in insns[:120]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
