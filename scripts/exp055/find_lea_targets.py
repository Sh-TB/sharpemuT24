#!/usr/bin/env python3
"""
EXP-055 Tier A Task 1-2: Find LEA/MOV instructions loading CodeRegistration (0x8086E9000)
or MetadataRegistration (0x80885C580) addresses in PRX code.

Strategy:
  For each target address T, search the PRX code segment for the 4-byte LE
  pattern matching disp32 of a RIP-relative instruction targeting T.

  For a 7-byte LEA at address A: disp32 = T - A - 7
  For an 8-byte MOV at address A: disp32 = T - A - 8

  We scan every byte offset in the code segment, decode one instruction,
  and check if it has a RIP-relative operand targeting T.
  
  To make this fast, we use a sliding capstone decoder but only on the code
  segment (45MB — should take ~2-3 minutes).
"""
import struct
import sys
sys.path.insert(0, "/home/z/my-project/scripts/exp052")
from analyze_hash_table_writes import parse_elf_segments
import capstone

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

TARGETS = {
    0x8086E9000: "Il2CppCodeRegistration",
    0x80885C580: "Il2CppMetadataRegistration",
    0x80893E950: "types[] array",
    0x808791958: "methodPointers[] array",
}

segments = parse_elf_segments(PRX, load_base=PRX_BASE)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

print(f"Scanning PRX code for references to:")
for t, name in TARGETS.items():
    print(f"  0x{t:X} ({name})")
print()

for target_addr, target_name in TARGETS.items():
    results = []
    for seg in segments:
        if seg["type"] != 1 or not (seg["flags"] & 1):
            continue
        data = seg["content"]
        seg_base = seg["runtime_vaddr"]
        # Linear disasm with skipdata to handle embedded data
        for insn in md.disasm(data, seg_base):
            # Check if any operand is RIP-relative to target
            for op in insn.operands:
                if op.type != capstone.x86.X86_OP_MEM:
                    continue
                if op.mem.base != capstone.x86.X86_REG_RIP:
                    continue
                eff = insn.address + insn.size + op.mem.disp
                if eff == target_addr:
                    is_write = (op == insn.operands[0])
                    role = "W" if is_write else "R"
                    results.append((insn.address, role, str(insn)))
                    break
                # Also check if it's a LEA (eff would be loaded into a register)
                # We already capture this above since LEA's operand[1] is the mem ref
    
    print(f"=== References to 0x{target_addr:X} ({target_name}): {len(results)} ===")
    for addr, role, txt in results[:30]:
        print(f"  0x{addr:X} [{role}] {txt}")
    if len(results) > 30:
        print(f"  ... ({len(results)} total)")
    print()
