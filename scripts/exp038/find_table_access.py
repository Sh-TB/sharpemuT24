#!/usr/bin/env python3
"""EXP-038 Task 3e: Find what accesses the metadata table.

The table at 0x1CC0080..0x1CE0000 has 13905 function pointers but no
direct code references. Find what reads it.

Strategy:
1. Search for RELATIVE relocations whose ADDEND is in the table range
   but whose r_offset is OUTSIDE the table — these are global pointers
   that point INTO the table.
2. Search for code that reads those global pointers.
3. Also search for il2cpp_codegen_register in the PRX exports.
"""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()

e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

dyn_foff = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type == 2:
        dyn_foff = struct.unpack_from('<Q', data, off + 8)[0]
        dyn_size = struct.unpack_from('<Q', data, off + 32)[0]
        break

rela_addr = rela_size = 0
i = 0
while i < dyn_size:
    d_tag, d_val = struct.unpack_from('<qQ', data, dyn_foff + i)
    if d_tag == 0: break
    if d_tag == 7: rela_addr = d_val
    elif d_tag == 8: rela_size = d_val
    i += 16

def vaddr_to_foff(vaddr):
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type != 1: continue
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        if p_vaddr <= vaddr < p_vaddr + p_filesz:
            return p_offset + (vaddr - p_vaddr)
    return None

rela_foff = vaddr_to_foff(rela_addr)

# Find ALL relocations pointing INTO the table range (0x1CC0080..0x1CE0000)
# but whose r_offset is OUTSIDE the table
TABLE_START = 0x1CC0080
TABLE_END = 0x1CE0000

print("=== Relocations pointing INTO table but located OUTSIDE table ===")
ptrs_into_table = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
    rel_type = r_info & 0xFFFFFFFF
    if rel_type == 8:  # R_X86_64_RELATIVE
        if TABLE_START <= r_addend < TABLE_END:
            if not (TABLE_START <= r_offset < TABLE_END):
                ptrs_into_table.append((r_offset, r_addend))

print(f"Found {len(ptrs_into_table)} relocations pointing into table from outside")
# Group by r_offset proximity
ptrs_into_table.sort()
for r_off, addend in ptrs_into_table[:30]:
    print(f"  [0x{r_off:X}] -> 0x{IMAGE_BASE + addend:X} (table+0x{addend - TABLE_START:X})")

# These r_offsets are global variables that point into the table.
# Now find code that reads these globals.
if ptrs_into_table:
    print(f"\n=== Searching for code that reads these global pointers ===")
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    
    # Get unique r_offsets (global variable addresses)
    global_addrs = sorted(set(r_off for r_off, _ in ptrs_into_table))
    print(f"Unique global addresses: {len(global_addrs)}")
    for g in global_addrs[:20]:
        print(f"  0x{g:X}")
    
    # Search for code references to these globals
    target_set = set(IMAGE_BASE + g for g in global_addrs)
    text_start = 0x4000
    text_size = 0x1938C2C
    chunk_size = 0x200000
    
    code_refs = []
    for chunk_start in range(text_start, text_start + text_size, chunk_size):
        chunk_end = min(chunk_start + chunk_size, text_start + text_size)
        chunk = data[chunk_start:chunk_end]
        chunk_vaddr = chunk_start - 0x4000 + IMAGE_BASE
        
        for insn in md.disasm(chunk, chunk_vaddr):
            for op in insn.operands:
                if op.type == 3:  # X86_OP_MEM
                    if op.mem.base == 41:  # RIP
                        target = insn.address + insn.size + op.mem.disp
                        if target in target_set:
                            code_refs.append((insn.address, insn.mnemonic, insn.op_str, target))
                            break
    
    print(f"\nCode references to global pointers: {len(code_refs)}")
    for addr, mnemonic, op_str, target in code_refs[:30]:
        print(f"  0x{addr:X}: {mnemonic} {op_str} -> 0x{target:X}")
