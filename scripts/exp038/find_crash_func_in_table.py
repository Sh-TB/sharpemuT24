#!/usr/bin/env python3
"""EXP-038 Task 3f: Check if crash function 0x80135DDD0 is in the metadata table.

The crash function has zero callers. It must be called via a function pointer.
The metadata table at 0x1CC0080 has 13905 function pointers.
Check if 0x80135DDD0 is among them.
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

# Target: the crash function and the WRITE function
targets = {
    0x80135DDD0: "crash_function (reads global)",
    0x8013EB6B0: "init_function (calls il2cpp_init + hash lookup)",
    0x8013FCE40: "main_function (called from entry)",
    0x8013525A0: "nearby_function_1",
    0x801352783: "read_site_1",
}

# Also add ALL functions that READ the global at 0x801E51240
# (from EXP-037 analysis)
global_read_sites = [
    0x80135DE6D, 0x801352783, 0x801549E2E, 0x80154D962,
    0x800AABD42, 0x800AACDB3, 0x800AC67A8, 0x800AD0DC1,
    0x800F9C1E0, 0x80132130E,
]

# Find function starts for these read sites
for site in global_read_sites:
    target_foff = site - IMAGE_BASE + 0x4000
    pos = data.rfind(b'\x55\x48\x89\xe5', target_foff - 0x1000, target_foff)
    if pos >= 0:
        func_vaddr = pos - 0x4000 + IMAGE_BASE
        targets[func_vaddr] = f"reader_of_global (read at 0x{site:X})"

print("=== Searching ALL RELATIVE relocations for target functions ===")
print(f"Targets: {len(targets)}")
for addr, desc in sorted(targets.items()):
    print(f"  0x{addr:X}: {desc}")

# Search all RELATIVE relocations
found = {}
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
    rel_type = r_info & 0xFFFFFFFF
    if rel_type == 8:  # R_X86_64_RELATIVE
        runtime_val = IMAGE_BASE + r_addend
        if runtime_val in targets:
            if runtime_val not in found:
                found[runtime_val] = []
            found[runtime_val].append(r_offset)

print(f"\n=== Results ===")
for addr, desc in sorted(targets.items()):
    if addr in found:
        locs = found[addr]
        print(f"\n  0x{addr:X} ({desc}):")
        print(f"    Found in {len(locs)} RELATIVE relocations:")
        for loc in locs[:10]:
            # Check if the location is in the metadata table range
            in_table = 0x1CC0080 <= loc <= 0x1CE0000
            table_marker = " [IN METADATA TABLE]" if in_table else ""
            print(f"    [0x{loc:X}] = 0x{addr:X}{table_marker}")
    else:
        print(f"\n  0x{addr:X} ({desc}): NOT FOUND in any relocation")

# Summary
print(f"\n=== Summary ===")
table_funcs = []
for addr, desc in sorted(targets.items()):
    if addr in found:
        for loc in found[addr]:
            if 0x1CC0080 <= loc <= 0x1CE0000:
                table_funcs.append((addr, desc, loc))
                break

print(f"Functions found in metadata table: {len(table_funcs)}")
for addr, desc, loc in table_funcs:
    print(f"  0x{addr:X} ({desc}) at table offset 0x{loc:X}")
