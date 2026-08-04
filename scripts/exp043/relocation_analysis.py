#!/usr/bin/env python3
"""EXP-043 Task 3: Sony relocation analysis for 0x801E51240.

Check if ANY relocation (standard or Sony-specific) targets 0x801E51240.
Also check nearby addresses (0x801E51238, 0x801E51248, etc.) to see if
a struct initialization covers this address.

Also check: is 0x801E51240 in a region that gets bulk-initialized?
For example, if a RELATIVE relocation at a nearby address sets a pointer
that happens to cover 0x801E51240 as part of a struct.
"""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000
TARGET_VADDR = 0x1E51240

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

# Find ALL relocation tables (standard + Sony)
rela_addr = rela_size = 0
jmprel_addr = jmprel_size = 0
i = 0
while i < dyn_size:
    d_tag, d_val = struct.unpack_from('<qQ', data, dyn_foff + i)
    if d_tag == 0: break
    if d_tag == 7: rela_addr = d_val  # DT_RELA
    elif d_tag == 8: rela_size = d_val  # DT_RELASZ
    elif d_tag == 23: jmprel_addr = d_val  # DT_JMPREL
    elif d_tag == 2: jmprel_size = d_val  # DT_PLTRELSZ
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

# Search ALL relocations for r_offset = 0x1E51240 or nearby
print("=== Searching ALL relocations for 0x801E51240 and nearby ===")
print(f"Target vaddr: 0x{TARGET_VADDR:X}")
print()

for table_name, table_addr, table_size in [("DT_RELA", rela_addr, rela_size),
                                              ("DT_JMPREL", jmprel_addr, jmprel_size)]:
    if table_addr == 0 or table_size == 0:
        continue
    foff = vaddr_to_foff(table_addr)
    if not foff:
        continue
    
    print(f"--- {table_name} (0x{table_addr:X}, size 0x{table_size:X}) ---")
    nearby_count = 0
    exact_count = 0
    for i in range(0, table_size, 24):
        r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, foff + i)
        # Check exact match
        if r_offset == TARGET_VADDR:
            rel_type = r_info & 0xFFFFFFFF
            sym_idx = r_info >> 32
            type_names = {0:'NONE',1:'R_64',2:'PC32',6:'GLOB_DAT',7:'JUMP_SLOT',8:'RELATIVE',9:'GOTPCREL',10:'GOT32'}
            runtime_val = IMAGE_BASE + r_addend if rel_type == 8 else r_addend
            print(f"  EXACT MATCH: r_offset=0x{r_offset:X} type={type_names.get(rel_type, rel_type)} sym={sym_idx} addend=0x{r_addend:X} runtime=0x{runtime_val:X}")
            exact_count += 1
        # Check nearby (within 256 bytes)
        elif abs(r_offset - TARGET_VADDR) <= 256:
            nearby_count += 1
            if nearby_count <= 10:
                rel_type = r_info & 0xFFFFFFFF
                type_names = {0:'NONE',1:'R_64',2:'PC32',6:'GLOB_DAT',7:'JUMP_SLOT',8:'RELATIVE'}
                runtime_val = IMAGE_BASE + r_addend if rel_type == 8 else r_addend
                offset_diff = r_offset - TARGET_VADDR
                print(f"  NEARBY [{offset_diff:+4d}]: r_offset=0x{r_offset:X} type={type_names.get(rel_type, rel_type)} addend=0x{r_addend:X} runtime=0x{runtime_val:X}")
    
    print(f"  Exact matches: {exact_count}, Nearby: {nearby_count}")
    print()

# Also check: is 0x801E51240 in a region covered by a RELATIVE relocation
# that initializes a struct? A struct base might be at a nearby address
# with a relocation, and 0x801E51240 might be a field within that struct.
print("=== Checking struct initialization ===")
print(f"Target 0x801E51240 is at vaddr 0x{TARGET_VADDR:X}")
print(f"Checking if any RELATIVE relocation's runtime value points to a struct")
print(f"that contains 0x801E51240 as a field...")

# The global at 0x801E51240 might be a field in a larger struct.
# If a struct starts at address A, and 0x801E51240 = A + offset,
# then a relocation at A might set the struct base, and the field
# at offset would be set separately.
# Let me check if there's a RELATIVE relocation at any address A
# where A <= 0x1E51240 < A + 0x200 (512-byte struct).
foff = vaddr_to_foff(rela_addr)
struct_candidates = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, foff + i)
    if r_offset <= TARGET_VADDR < r_offset + 0x200:
        rel_type = r_info & 0xFFFFFFFF
        if rel_type == 8:  # RELATIVE
            offset_in_struct = TARGET_VADDR - r_offset
            struct_candidates.append((r_offset, r_addend, offset_in_struct))

print(f"Struct candidates: {len(struct_candidates)}")
for r_off, addend, offset in struct_candidates[:10]:
    print(f"  Struct at 0x{r_off:X}, 0x801E51240 is at +0x{offset:X}, addend=0x{addend:X}")
