#!/usr/bin/env python3
"""EXP-038 Task 3d: Find the IL2CPP registration struct.

The metadata table at 0x1CC0080..0x1CE0000 has no direct code references.
It must be accessed via a registration struct (Il2CppCodeRegistration)
whose fields point to sub-tables within this range.

Strategy:
1. Identify sub-table start addresses (0x1CC0080, 0x1CC4590, 0x1CCD280, etc.)
2. Search for RELATIVE relocations whose addend matches these addresses
3. Those relocations write pointers into a struct — the registration struct
4. Find code that reads the registration struct
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

# Collect ALL RELATIVE relocations
all_relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
    rel_type = r_info & 0xFFFFFFFF
    if rel_type == 8:  # R_X86_64_RELATIVE
        all_relocs.append((r_offset, r_addend))

print(f"Total RELATIVE relocations: {len(all_relocs)}")

# Sub-table start addresses to search for as addends
# These are the vaddrs (relative to image base) of sub-table starts
subtable_starts = [0x1CC0080, 0x1CC4590, 0x1CCD280, 0x1CCD2D0]

# Search for relocations whose ADDEND equals a sub-table start
print("\n=== Searching for relocations pointing to sub-table starts ===")
struct_relocs = []
for r_off, addend in all_relocs:
    if addend in subtable_starts:
        struct_relocs.append((r_off, addend))
        print(f"  [0x{r_off:X}] = 0x{IMAGE_BASE + addend:X} (addend=0x{addend:X})")

# Also search for relocations pointing NEAR the sub-table starts
# (within 0x100 bytes, to catch slight offsets)
print("\n=== Searching for relocations pointing near sub-table starts ===")
near_relocs = []
for r_off, addend in all_relocs:
    for st in subtable_starts:
        if abs(addend - st) <= 0x100 and addend not in subtable_starts:
            # Only if the relocation is OUTSIDE the table range
            if not (0x1CC0000 <= r_off <= 0x1CE0000):
                near_relocs.append((r_off, addend, st))

# Group by r_offset to find the struct
if near_relocs:
    print(f"Found {len(near_relocs)} nearby relocations outside table")
    # Group by r_offset proximity (within 0x100 bytes = same struct)
    near_relocs.sort()
    structs = []
    current_struct = [near_relocs[0]]
    for i in range(1, len(near_relocs)):
        if near_relocs[i][0] - current_struct[-1][0] <= 0x100:
            current_struct.append(near_relocs[i])
        else:
            structs.append(current_struct)
            current_struct = [near_relocs[i]]
    structs.append(current_struct)
    
    print(f"\nFound {len(structs)} potential struct locations:")
    for s in structs[:5]:
        print(f"  Struct at ~0x{s[0][0]:X} ({len(s)} fields):")
        for r_off, addend, st in s[:10]:
            print(f"    [0x{r_off:X}] = 0x{IMAGE_BASE + addend:X} (near subtable 0x{st:X})")

# Let me also search for the EXACT sub-table starts more broadly
# by searching ALL relocations (not just RELATIVE) for these addends
print("\n=== ALL relocations (any type) pointing to sub-table starts ===")
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
    rel_type = r_info & 0xFFFFFFFF
    sym_idx = r_info >> 32
    if r_addend in subtable_starts and rel_type != 8:
        print(f"  r_offset=0x{r_offset:X} type={rel_type} sym={sym_idx} addend=0x{r_addend:X}")

# The registration struct might be at a well-known address
# Let me check what's at the very start of the data segment (PH[3] at 0x1C80000)
# and look for a struct with fields pointing to our table
print("\n=== Checking data segment start for registration struct ===")
# PH[3]: vaddr=0x1C80000, offset=0x1C84000, filesz=0x9C450
# Let's read the first 256 bytes and look for pointers into the table
data_seg_off = 0x1C84000
print(f"Data segment first 256 bytes (vaddr 0x801C80000):")
for i in range(0, 256, 8):
    val = struct.unpack_from('<Q', data, data_seg_off + i)[0]
    # Check if this value (when relocated) points into the table
    if 0x1CC0080 <= val <= 0x1CE0000:
        print(f"  +0x{i:02X} (0x{0x1C80000+i:X}): 0x{val:X} *** POINTS TO TABLE ***")
    elif IMAGE_BASE + 0x1CC0080 <= val <= IMAGE_BASE + 0x1CE0000:
        print(f"  +0x{i:02X} (0x{0x1C80000+i:X}): 0x{val:X} *** POINTS TO TABLE (absolute) ***")
