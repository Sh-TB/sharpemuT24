#!/usr/bin/env python3
"""
EXP-052 Task A1f: Verify what hash table is read by the lookup at 0x8013EEFE0.

The lookup at 0x8013EEFE0 is what the init function uses to set metadata
globals. We need to identify:
  1. What RIP-relative address is loaded as the hash table base?
  2. Is it 0x801EF7610 (P/Invoke) or something else (metadata)?
"""
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX

# Disassemble around 0x8013EEFE0 — the hash lookup that's being skipped
print("=" * 78)
print("Hash lookup at 0x8013EEFE0 — disassemble around it")
print("=" * 78)
insns = disasm_at(EBOOT, 0x8013EEF00, size=0x400, label="hash_lookup_at_EEFE0")
for ins in insns[:120]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# Also: disassemble the callback 0x80134FA00 (stubbed in EXP-048)
print()
print("=" * 78)
print("Callback function 0x80134FA00 — what does it actually do?")
print("=" * 78)
insns = disasm_at(EBOOT, 0x80134FA00, size=0x800, label="callback_func")
for ins in insns[:120]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# And the crash function 0x80135DDD0
print()
print("=" * 78)
print("Crash function 0x80135DDD0 — what does it read?")
print("=" * 78)
insns = disasm_at(EBOOT, 0x80135DDD0, size=0x800, label="crash_func")
for ins in insns[:80]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
