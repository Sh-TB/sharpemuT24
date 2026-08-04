#!/usr/bin/env python3
"""EXP-038 Task 3c: Map the full metadata table and find its iterator.

Found RELATIVE relocations at 0x1CCD2D0+ pointing to registration functions.
This is likely the IL2CPP metadata registration table.

Strategy:
1. Find ALL RELATIVE relocations in the 0x1CC0000..0x1CD0000 range
2. Map the table structure
3. Find code that reads from the table start address
4. Determine what iterates this table
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

# Find ALL RELATIVE relocations in 0x1CC0000..0x1CE0000
print("=== ALL RELATIVE relocations in 0x1CC0000..0x1CE0000 ===")
table_relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
    rel_type = r_info & 0xFFFFFFFF
    if rel_type == 8:  # R_X86_64_RELATIVE
        if 0x1CC0000 <= r_offset <= 0x1CE0000:
            table_relocs.append((r_offset, r_addend))

table_relocs.sort()
print(f"Found {len(table_relocs)} RELATIVE relocations in range")
print(f"Range: 0x{table_relocs[0][0]:X}..0x{table_relocs[-1][0]:X}")
print(f"Span: 0x{table_relocs[-1][0] - table_relocs[0][0]:X} bytes")

# Dump first 30 entries
print("\nFirst 30 entries:")
for r_off, addend in table_relocs[:30]:
    runtime = IMAGE_BASE + addend
    print(f"  0x{r_off:X}: -> 0x{runtime:X} (addend=0x{addend:X})")

# The table likely starts at 0x1CCD2D0 or nearby
# Let me check what's before 0x1CCD2D0
print("\n=== Relocations just before 0x1CCD2D0 ===")
before = [(o, a) for o, a in table_relocs if o < 0x1CCD2D0]
for r_off, addend in before[-10:]:
    runtime = IMAGE_BASE + addend
    print(f"  0x{r_off:X}: -> 0x{runtime:X} (addend=0x{addend:X})")

# Now find code that reads from the table start address
# The table seems to start around 0x1CCD2D0
# Let me search for LEA or MOV instructions that reference addresses in this range
print("\n=== Searching for code references to table addresses ===")

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Search for references to 0x1CCD2D0 and nearby addresses
# The table might be referenced by a pointer stored in a global variable
# Let me search for LEA instructions that compute addresses in 0x1CC0000..0x1CE0000

table_start = table_relocs[0][0]  # First relocation offset
table_end = table_relocs[-1][0] + 8

# Search for any RIP-relative reference to addresses in the table range
text_start = 0x4000
text_size = 0x1938C2C
chunk_size = 0x200000

refs_to_table = []
for chunk_start in range(text_start, text_start + text_size, chunk_size):
    chunk_end = min(chunk_start + chunk_size, text_start + text_size)
    chunk = data[chunk_start:chunk_end]
    chunk_vaddr = chunk_start - 0x4000 + IMAGE_BASE
    
    for insn in md.disasm(chunk, chunk_vaddr):
        for op in insn.operands:
            if op.type == 3:  # X86_OP_MEM
                if op.mem.base == 41:  # RIP
                    target = insn.address + insn.size + op.mem.disp
                    if table_start <= target <= table_end:
                        refs_to_table.append((insn.address, insn.mnemonic, insn.op_str, target))
                        break

print(f"Found {len(refs_to_table)} code references to table range")
for addr, mnemonic, op_str, target in refs_to_table[:20]:
    print(f"  0x{addr:X}: {mnemonic} {op_str} -> 0x{target:X}")

# Also search for references to the EXACT table start
print(f"\n=== References to table start 0x{table_start:X} ===")
exact_refs = [(a, m, o, t) for a, m, o, t in refs_to_table if t == table_start]
for addr, mnemonic, op_str, target in exact_refs[:10]:
    print(f"  0x{addr:X}: {mnemonic} {op_str}")

# Also search for a global variable that POINTS to the table
# The table address might be stored in a global, and code reads the global
print(f"\n=== Searching for global variables pointing to table ===")
# Search RELA for relocations whose ADDEND points into the table range
ptr_relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
    rel_type = r_info & 0xFFFFFFFF
    if rel_type == 8:  # R_X86_64_RELATIVE
        if table_start <= r_addend <= table_end:
            ptr_relocs.append((r_offset, r_addend))

# Filter out the table entries themselves (which are IN the table range)
# We want relocations OUTSIDE the table that point INTO it
ptr_relocs_outside = [(r_off, addend) for r_off, addend in ptr_relocs 
                        if not (table_start <= r_off <= table_end)]
print(f"Relocations OUTSIDE table pointing INTO table: {len(ptr_relocs_outside)}")
for r_off, addend in ptr_relocs_outside[:20]:
    runtime = IMAGE_BASE + addend
    print(f"  [0x{r_off:X}] = 0x{runtime:X} (points into table)")
