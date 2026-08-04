#!/usr/bin/env python3
"""EXP-054: Read the rodata pointer array at 0x80893E950 (12978 entries)."""
import struct

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

with open(PRX, "rb") as f:
    data = f.read()

# Parse RELA
e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
e_phnum = struct.unpack_from("<H", data, 0x38)[0]

dyn_off = None
dyn_size = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
        struct.unpack_from("<IIQQQQQQ", data, off)
    if p_type == 2:
        dyn_off = p_offset
        dyn_size = p_filesz
        break

rela_off = None
rela_size = None
for i in range(0, dyn_size, 16):
    d_tag, d_val = struct.unpack_from("<QQ", data, dyn_off + i)
    if d_tag == 0: break
    if d_tag == 7:
        for j in range(e_phnum):
            off2 = e_phoff + j * e_phentsize
            p_type2, p_flags2, p_offset2, p_vaddr2, p_paddr2, p_filesz2, p_memsz2, p_align2 = \
                struct.unpack_from("<IIQQQQQQ", data, off2)
            if p_type2 == 1 and p_vaddr2 <= d_val < p_vaddr2 + p_filesz2:
                rela_off = p_offset2 + (d_val - p_vaddr2)
                break
    elif d_tag == 8:
        rela_size = d_val

# Collect all RELATIVE relocs in the target range
# Array at runtime 0x80893E950 - 0x808958220
# File vaddr = runtime - PRX_BASE = 0x80893E950 - 0x804CD5000 = 0x3C8E950
target_start = 0x80893E950 - PRX_BASE  # 0x3C8E950
target_end = 0x808958220 - PRX_BASE    # 0x3CA3220

relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    if r_type == 8 and target_start <= r_offset < target_end:
        relocs.append((r_offset, r_addend))

print(f"Relocs in target range: {len(relocs)}")
print()

# Read first 30 strings
print("First 30 strings (typeNames candidates):")
for i in range(min(30, len(relocs))):
    r_offset, r_addend = relocs[i]
    runtime_offset = r_offset + PRX_BASE
    runtime_value = r_addend + PRX_BASE
    # Read string at file offset = addend
    if 0 <= r_addend < len(data):
        end = data.find(b'\x00', r_addend)
        if end < 0 or end - r_addend > 300:
            end = r_addend + 200
        s = data[r_addend:end].decode('utf-8', errors='replace')
        print(f"  [{i}] *[0x{runtime_offset:X}] = 0x{runtime_value:X} -> \"{s[:100]}\"")
    else:
        print(f"  [{i}] *[0x{runtime_offset:X}] = 0x{runtime_value:X} -> <out of range>")

# Also check: are these strings type names? Look for patterns like "System." or "UnityEngine."
print()
print("Checking if strings look like type names...")
type_name_count = 0
sample_type_names = []
for i in range(min(1000, len(relocs))):
    r_offset, r_addend = relocs[i]
    if 0 <= r_addend < len(data):
        end = data.find(b'\x00', r_addend)
        if end < 0 or end - r_addend > 300:
            end = r_addend + 200
        s = data[r_addend:end].decode('utf-8', errors='replace')
        # Type names typically contain '.' or start with uppercase
        if '.' in s or (s and s[0].isupper() and len(s) > 3):
            type_name_count += 1
            if len(sample_type_names) < 20:
                sample_type_names.append(s)

print(f"  Strings looking like type names (first 1000): {type_name_count}")
print(f"  Sample type names:")
for s in sample_type_names:
    print(f"    \"{s[:100]}\"")

# Also look at the array right before this one (might be the types[] array)
# The mixed array at 0x808724730-0x808762978 (31818 entries, 19580 code + 12238 data)
# might be the types[] array (Il2CppType structs)
print()
print("Checking the mixed array at 0x808724730 (types[] candidates)...")
mixed_start = 0x808724730 - PRX_BASE
mixed_end = 0x808762978 - PRX_BASE
mixed_relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    if r_type == 8 and mixed_start <= r_offset < mixed_end:
        mixed_relocs.append((r_offset, r_addend))

print(f"  Relocs in mixed array: {len(mixed_relocs)}")
print(f"  First 10:")
for i in range(min(10, len(mixed_relocs))):
    r_offset, r_addend = mixed_relocs[i]
    runtime_offset = r_offset + PRX_BASE
    runtime_value = r_addend + PRX_BASE
    # Check if addend is in code or data segment
    if r_addend < 0x2B9722A:
        cls = "code"
    elif 0x3A14000 <= r_addend < 0x3E6CBC8:
        cls = "data"
    else:
        cls = "other"
    print(f"    [{i}] *[0x{runtime_offset:X}] = 0x{runtime_value:X} ({cls})")
