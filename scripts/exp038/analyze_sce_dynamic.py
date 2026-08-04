#!/usr/bin/env python3
"""EXP-038 Task 1: Analyze PT_SCE_DYNAMIC segment.

The PT_SCE_DYNAMIC segment for eboot.bin is at:
  offset=0x01D203F0, vaddr=0x000001D1C3F0, size=0x60

This 96-byte structure is the Sony sce_dynamic_info which contains
the REAL init_array pointers (separate from DT_INIT_ARRAY).
"""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
data = EBOOT.read_bytes()

# PT_SCE_DYNAMIC for eboot.bin: offset=0x1D203F0, size=0x60
sce_dyn_off = 0x1D203F0
sce_dyn_size = 0x60

print(f"=== PT_SCE_DYNAMIC at file offset 0x{sce_dyn_off:X} (size 0x{sce_dyn_size:X}) ===")
chunk = data[sce_dyn_off:sce_dyn_off + sce_dyn_size]

# Dump as hex
for i in range(0, len(chunk), 16):
    hex_part = " ".join(f"{b:02X}" for b in chunk[i:i+16])
    print(f"  +0x{i:02X}: {hex_part}")

print()

# The sce_dynamic_info structure (from PS5 SDK reverse engineering):
# struct sce_dynamic_info {
#     uint64_t size;              // +0x00
#     uint64_t ents_offset;       // +0x08 (offset to DT entries)
#     uint64_t ents_size;         // +0x10
#     uint64_t stubs_offset;      // +0x18
#     uint64_t stubs_size;        // +0x20
#     uint64_t needed_offset;     // +0x28
#     uint64_t needed_size;       // +0x30
#     uint64_t flags1;            // +0x38
#     uint64_t flags2;            // +0x40
#     uint64_t reserved[3];       // +0x48..+0x58
# }

# Actually, the real structure is different. Let me just parse all 8-byte fields
print("=== Parsed as 8-byte fields ===")
for i in range(0, sce_dyn_size, 8):
    val = struct.unpack_from('<Q', chunk, i)[0]
    print(f"  +0x{i:02X}: 0x{val:016X}")

# The ents_offset likely points to a secondary dynamic table
# that contains the REAL DT_INIT_ARRAY
ents_offset = struct.unpack_from('<Q', chunk, 8)[0]
ents_size = struct.unpack_from('<Q', chunk, 16)[0]
print(f"\n=== Secondary dynamic table at ents_offset=0x{ents_offset:X}, size=0x{ents_size:X} ===")

# ents_offset is relative to the PT_SCE_DYNAMIC vaddr? Or absolute?
# Let me check: PT_SCE_DYNAMIC vaddr = 0x1D1C3F0
# If ents_offset is relative to image base, it's a vaddr
# If relative to PT_SCE_DYNAMIC, it's offset from 0x1D1C3F0

# Try as vaddr first
def vaddr_to_foff(vaddr):
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
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

# The ents_offset might be a vaddr or an offset from PT_SCE_DYNAMIC
for label, addr in [("as vaddr", ents_offset),
                       ("as offset from PT_SCE_DYNAMIC vaddr", 0x1D1C3F0 + ents_offset),
                       ("as offset from PT_SCE_DYNAMIC file offset", 0x1D203F0 + ents_offset)]:
    foff = vaddr_to_foff(addr) if addr < 0x800000000 else None
    if foff is None and addr < len(data):
        foff = addr
    if foff and foff + ents_size <= len(data):
        print(f"\n  Trying {label} (addr=0x{addr:X}, foff=0x{foff:X}):")
        # Parse as DT entries
        i = 0
        count = 0
        while i < ents_size and count < 50:
            d_tag, d_val = struct.unpack_from('<qQ', data, foff + i)
            if d_tag == 0:
                break
            # DT names
            DT_NAMES = {
                12: "DT_INIT", 25: "DT_INIT_ARRAY", 27: "DT_INIT_ARRAYSZ",
                0x61000010: "DT_SCE_INIT_ARRAY", 0x61000011: "DT_SCE_INIT_ARRAY_SIZE",
                0x61000012: "DT_SCE_FINI_ARRAY", 0x61000013: "DT_SCE_FINI_ARRAY_SIZE",
                5: "DT_STRTAB", 6: "DT_SYMTAB", 7: "DT_RELA", 8: "DT_RELASZ",
            }
            name = DT_NAMES.get(d_tag, f"DT_{d_tag:X}")
            print(f"    {name} = 0x{d_val:X}")
            i += 16
            count += 1
