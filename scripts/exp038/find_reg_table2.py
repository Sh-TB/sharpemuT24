#!/usr/bin/env python3
"""EXP-038 Task 3b: Search ALL segments for registration function pointers.

The registration functions might be in a read-only data segment or
in a metadata table that's not in the standard RW data segments.
"""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()

# Registration functions to search for (from find_reg_table.py)
search_funcs = [
    0x80045C210, 0x80045C520, 0x800460DD0, 0x800461D50, 0x8004622D0,
    0x800465F10, 0x800467B30, 0x800468690, 0x80046DAF0, 0x800474B40,
]

print("=== Searching ALL file bytes for registration function pointers ===")
for func_addr in search_funcs:
    needle = struct.pack('<Q', func_addr)
    idx = 0
    found = []
    while idx < len(data):
        pos = data.find(needle, idx)
        if pos < 0:
            break
        found.append(pos)
        idx = pos + 1
    if found:
        print(f"  0x{func_addr:X}: found at {len(found)} locations:")
        for p in found[:5]:
            print(f"    file offset 0x{p:X}")
    else:
        print(f"  0x{func_addr:X}: NOT FOUND")

# Also search for 32-bit relative references (e.g., in relocation tables)
# The functions might be referenced by R_X86_64_RELATIVE relocations
print("\n=== Searching RELA relocations for registration function addresses ===")

e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

dyn_foff = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type == 2:  # PT_DYNAMIC
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
print(f"RELA: vaddr=0x{rela_addr:X} foff=0x{rela_foff:X} size=0x{rela_size:X}")

# Search for RELATIVE relocations whose addend matches a registration function
search_set = set(search_funcs)
reloc_matches = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
    rel_type = r_info & 0xFFFFFFFF
    if rel_type == 8:  # R_X86_64_RELATIVE
        runtime_val = IMAGE_BASE + r_addend
        if runtime_val in search_set:
            reloc_matches.append((r_offset, r_addend, runtime_val))

print(f"\nFound {len(reloc_matches)} RELATIVE relocations pointing to registration functions:")
for r_off, addend, runtime in reloc_matches[:20]:
    print(f"  r_offset=0x{r_off:X} -> 0x{runtime:X} (addend=0x{addend:X})")

# Group r_offsets to find if they form a table
if reloc_matches:
    offsets = sorted(set(r[0] for r in reloc_matches))
    print(f"\nUnique r_offsets: {len(offsets)}")
    print("First 20:")
    for o in offsets[:20]:
        print(f"  0x{o:X}")
    
    # Check if consecutive
    if len(offsets) >= 2:
        diffs = [offsets[i+1] - offsets[i] for i in range(len(offsets)-1)]
        print(f"\nDifferences between consecutive offsets (first 10): {diffs[:10]}")
        # If all diffs are 8, it's a function pointer table
        if len(set(diffs)) == 1 and diffs[0] == 8:
            print(f"*** ALL diffs are 8 — this IS a function pointer table! ***")
            print(f"Table range: 0x{offsets[0]:X}..0x{offsets[-1]+8:X}")
            print(f"Total entries: {len(offsets)}")
