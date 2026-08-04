#!/usr/bin/env python3
"""EXP-038 Task 3: Find the registration function table.

The 995 il2cpp_add_internal_call registration functions have zero callers.
They must be referenced by a function pointer table somewhere in the data
segment. This script searches for such tables.

Strategy:
1. Find a few registration function addresses
2. Search the entire data segment for those addresses as 8-byte values
3. If found, dump the surrounding table to identify all entries
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000
FILE_OFFSET_DELTA = 0x4000

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# First, find more registration function addresses
# We know 0x80045C210 contains a call to il2cpp_add_internal_call at 0x80045C2F3
# Let me find ALL functions that call global[12] (0x801ED6380)

target_global = 0x801ED6380  # il2cpp_add_internal_call

print("=== Finding all functions that call il2cpp_add_internal_call ===")
text_start = 0x4000
text_size = 0x1938C2C

# Find all call sites
call_sites = []
for i in range(text_start, text_start + text_size - 6):
    if data[i] == 0xFF and data[i+1] == 0x15:
        disp32 = struct.unpack_from('<i', data, i+2)[0]
        call_vaddr = i - 0x4000 + 0x800000000
        target_addr = call_vaddr + 6 + disp32
        if target_addr == target_global:
            call_sites.append(call_vaddr)

print(f"Found {len(call_sites)} call sites to il2cpp_add_internal_call")

# Find the function start for each call site
reg_funcs = set()
for site in call_sites:
    target_foff = site - IMAGE_BASE + FILE_OFFSET_DELTA
    # Search backwards for function prologue
    pos = data.rfind(b'\x55\x48\x89\xe5', target_foff - 0x2000, target_foff)
    if pos >= 0:
        func_vaddr = pos - FILE_OFFSET_DELTA + IMAGE_BASE
        reg_funcs.add(func_vaddr)

reg_funcs = sorted(reg_funcs)
print(f"Found {len(reg_funcs)} unique registration functions")
print("First 10:")
for f in reg_funcs[:10]:
    print(f"  0x{f:X}")
print("Last 5:")
for f in reg_funcs[-5:]:
    print(f"  0x{f:X}")

# Now search the DATA segments for these function addresses
# Data segments: PH[3] (0x1C80000, RW), PH[7] (0x1D20000, RW), PH[8] (0x1F39970)
print(f"\n=== Searching data segments for registration function pointers ===")

e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

data_segments = []
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type != 1: continue  # LOAD
    p_flags = struct.unpack_from('<I', data, off + 4)[0]
    p_offset = struct.unpack_from('<Q', data, off + 8)[0]
    p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
    p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
    # Data segments are RW (not X)
    if (p_flags & 2) and not (p_flags & 1):  # W but not X
        data_segments.append((p_offset, p_vaddr, p_filesz, i))
        print(f"  PH[{i}]: data segment off=0x{p_offset:X} vaddr=0x{p_vaddr:X} size=0x{p_filesz:X}")

# Search for the first few registration function addresses as 8-byte values
search_funcs = reg_funcs[:5]
print(f"\nSearching for first {len(search_funcs)} registration functions in data segments:")

found_locations = []
for func_addr in search_funcs:
    needle = struct.pack('<Q', func_addr)
    for seg_off, seg_vaddr, seg_size, phdr_idx in data_segments:
        idx = 0
        while idx < seg_size:
            pos = data.find(needle, seg_off + idx, seg_off + seg_size)
            if pos < 0:
                break
            found_vaddr = pos - seg_off + seg_vaddr + IMAGE_BASE
            found_locations.append((func_addr, pos, found_vaddr, phdr_idx))
            print(f"  0x{func_addr:X} found at file offset 0x{pos:X} (vaddr 0x{found_vaddr:X}) in PH[{phdr_idx}]")
            idx = pos - seg_off + 1

# If we found a location, dump the surrounding table
if found_locations:
    func_addr, file_off, vaddr, phdr_idx = found_locations[0]
    print(f"\n=== Dumping table around 0x{vaddr:X} (first match) ===")
    # Dump 256 bytes before and 256 bytes after
    start = max(0, file_off - 256)
    end = min(len(data), file_off + 256)
    print(f"  Range: 0x{start:X}..0x{end:X}")
    
    # Parse as 8-byte function pointers
    table_start = None
    table_end = None
    for i in range(start, end, 8):
        if i + 8 > len(data):
            break
        val = struct.unpack_from('<Q', data, i)[0]
        vaddr_val = val
        # Check if it looks like a code address (in eboot.bin range)
        if IMAGE_BASE <= vaddr_val < IMAGE_BASE + 0x2000000:
            if table_start is None:
                table_start = i
            table_end = i + 8
    
    if table_start and table_end:
        print(f"  Function pointer table: 0x{table_start:X}..0x{table_end:X} ({(table_end - table_start) // 8} entries)")
        num = (table_end - table_start) // 8
        for j in range(min(num, 30)):
            val = struct.unpack_from('<Q', data, table_start + j * 8)[0]
            print(f"    [{j}] 0x{val:X}")
