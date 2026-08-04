#!/usr/bin/env python3
"""EXP-051: Get exact bytes of all 15 conditional jumps to NOP.

From EXP-050, these jumps skip the hash lookup at 0x8013EEFE0.
Range: 0x8013ED05C (after il2cpp_init) to 0x8013EEFE0 (hash lookup).
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()

# All jumps from EXP-050 that target > 0x8013EEFE0
jumps = [
    (0x8013EDA99, "JMP", 0x8493F5D93),  # Likely misaligned, skip
    (0x8013EDDF3, "JMP", 0x8463DE46A),  # Likely misaligned, skip
    (0x8013EE0CE, "Jcc", 0x8013EF25E),
    (0x8013EE1AE, "Jcc", 0x8013EF308),
    (0x8013EE768, "JMP", 0x84D6A288E),  # Likely misaligned, skip
    (0x8013EEABA, "Jcc", 0x8013EF061),
    (0x8013EEAC5, "JMP", 0x8013EF07B),
    (0x8013EEB4F, "Jcc", 0x8013F58D1),
    (0x8013EEE4B, "JMP", 0x8013EF46E),  # Likely misaligned, skip
    (0x8013EEE94, "Jcc", 0x8013EF3C4),
    (0x8013EEEAE, "Jcc", 0x8013EF3C4),
    (0x8013EEECA, "Jcc", 0x8013EF3CB),
    (0x8013EEEDB, "JMP", 0x8753F9A6F),  # Likely misaligned, skip
    (0x8013EEF44, "Jcc", 0x8013EF3C4),
    (0x8013EEF5C, "Jcc", 0x8013EF3C4),
    (0x8013EEF81, "Jcc", 0x8013EF3CB),
]

# Filter: only keep jumps with reasonable targets (< 0x810000000)
valid_jumps = [(addr, typ, target) for addr, typ, target in jumps if target < 0x810000000]
print(f"Valid jumps to NOP: {len(valid_jumps)}")

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

for addr, typ, target in valid_jumps:
    offset = addr - IMAGE_BASE + 0x4000
    bytes_at = data[offset:offset+8]
    print(f"  0x{addr:X}: {bytes_at[:6].hex()} -> 0x{target:X} (type={typ})")
    
    # Verify with capstone
    chunk = data[offset:offset+8]
    for insn in md.disasm(chunk, addr):
        if insn.address == addr:
            print(f"    Capstone: {insn.mnemonic} {insn.op_str} ({insn.size} bytes)")
            break
