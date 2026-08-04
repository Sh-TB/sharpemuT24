#!/usr/bin/env python3
"""
EXP-053 Task B: Verify static table population.

Reads eboot.bin's RELA table and lists what should be at 0x1CC0080.
Then we can compare with the runtime dump to see if SharpEmu applied
all relocations correctly.

The static table is Il2CppMetadataRegistration. Each entry is 0x218 bytes
(we computed this from the reloc offsets: 0x1CC0080, 0x1CC0298, 0x1CC04B0...).
Each entry contains:
  +0x00: type_info_ptr (function pointer to type metadata)
  +0x08: method_info_ptr (function pointer to method metadata)
  +0x10..+0x210: zeros (or other fields, not reloc-initialized)
  +0x210: type_name_ptr (string pointer)  [from EXP-052: 0x1CC4590+]
  +0x218: method_name_ptr (string pointer)
"""
import struct

EBOOT = "/tmp/games/yatzi/eboot.bin"
BASE = 0x800000000
TABLE_START = 0x1CC0080
TABLE_END = 0x1CE0080

with open(EBOOT, "rb") as f:
    data = f.read()

rela_off = 0x1E075F0
rela_size = 0x124170

# Collect all RELATIVE relocs in the static table range
relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    if r_type == 8 and TABLE_START <= r_offset < TABLE_END:
        relocs.append((r_offset, r_addend))

print(f"Total RELATIVE relocs in static table: {len(relocs)}")
print()

# Group by entry (0x218-byte stride)
# First entry: r_offset 0x1CC0080, 0x1CC0088
# Second entry: r_offset 0x1CC0298, 0x1CC02A0 (delta = 0x218)
# Third entry: r_offset 0x1CC04B0, 0x1CC04B8 (delta = 0x218)
# So entry size = 0x218, with 2 pointers at +0x00 and +0x08

entry_size = 0x218
print(f"Entry size: 0x{entry_size:X} bytes")
print(f"Total entries: {(TABLE_END - TABLE_START) // entry_size}")
print()

# Show first 5 entries
print("First 5 entries (what SHOULD be in memory at runtime):")
for entry_idx in range(5):
    entry_offset = TABLE_START + entry_idx * entry_size
    # Find relocs for this entry
    entry_relocs = [(r_off - entry_offset, r_addend) for r_off, r_addend in relocs 
                    if entry_offset <= r_off < entry_offset + entry_size]
    print(f"  Entry {entry_idx} @ runtime 0x{entry_offset + BASE:X}:")
    for off_in_entry, addend in entry_relocs:
        runtime_val = addend + BASE
        # Check if addend points to code or string
        kind = "code" if addend < 0x1938C2C else ("rodata" if 0x1938C2C <= addend < 0x1D20000 else "data")
        print(f"    +0x{off_in_entry:04X}: 0x{runtime_val:X} ({kind})")

# Also check the SECOND table at 0x1CC4590 (where string pointers start)
print()
print("String pointers table (starting at 0x1CC4590):")
string_relocs = [(r_off, r_addend) for r_off, r_addend in relocs 
                 if 0x1CC4590 <= r_off < 0x1CC4600]
for r_off, r_addend in string_relocs:
    runtime_addr = r_off + BASE
    runtime_val = r_addend + BASE
    print(f"  *[0x{runtime_addr:X}] = 0x{runtime_val:X}")

# Read the actual string at the first few string pointers
print()
print("First 5 string pointers and their contents:")
# Group string-area relocs
string_area_relocs = sorted([(r_off, r_addend) for r_off, r_addend in relocs 
                              if 0x1CC4590 <= r_off < 0x1CC4600])
for r_off, r_addend in string_area_relocs[:10]:
    runtime_addr = r_off + BASE
    runtime_val = r_addend + BASE
    # Read the string from eboot at file offset = addend
    if addend < len(data):
        end = data.find(b'\x00', r_addend)
        if end < 0 or end - r_addend > 200:
            end = r_addend + 64
        s = data[r_addend:end].decode('ascii', errors='replace')
        print(f"  *[0x{runtime_addr:X}] = 0x{runtime_val:X} -> \"{s}\"")

# Count how many unique string pointers there are
print()
all_string_ptrs = set()
for r_off, r_addend in relocs:
    if 0x1CC4590 <= r_off:
        all_string_ptrs.add(r_addend + BASE)
print(f"Unique string pointer values: {len(all_string_ptrs)}")
