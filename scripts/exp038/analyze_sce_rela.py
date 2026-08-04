#!/usr/bin/env python3
"""EXP-038 Task 1: Analyze DT_SCE_RELA — the PS5-specific relocation table.

From the ELF dynamic section:
  DT_SCE_RELA (0x6100003f) = 0x3900
  DT_SCE_RELASZ_2 (0x61000040) = ?

This is a SEPARATE relocation table that SharpEmu may not process.
It might contain the init_array bounds relocations.
"""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()

e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

# Find PT_DYNAMIC
dyn_foff = None
dyn_size = 0
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type == 2:
        dyn_foff = struct.unpack_from('<Q', data, off + 8)[0]
        dyn_size = struct.unpack_from('<Q', data, off + 32)[0]
        break

# Parse ALL dynamic entries, looking for SCE-specific relocation entries
print("=== SCE-specific relocation entries ===")
sce_rela = sce_relasz = sce_relaent = 0
sce_jmprel = sce_pltrelsz = 0
i = 0
while i < dyn_size:
    d_tag, d_val = struct.unpack_from('<qQ', data, dyn_foff + i)
    if d_tag == 0: break
    
    # SCE relocation-related tags
    if d_tag in (0x6100003f, 0x61000040, 0x61000041, 0x61000043, 0x61000044):
        names = {
            0x6100003f: "DT_SCE_RELA",
            0x61000040: "DT_SCE_RELASZ",
            0x61000041: "DT_SCE_RELAENT",
            0x61000043: "DT_SCE_JMPREL",
            0x61000044: "DT_SCE_PLTRELSZ",
        }
        print(f"  {names[d_tag]} = 0x{d_val:X}")
        if d_tag == 0x6100003f: sce_rela = d_val
        elif d_tag == 0x61000040: sce_relasz = d_val
        elif d_tag == 0x61000041: sce_relaent = d_val
        elif d_tag == 0x61000043: sce_jmprel = d_val
        elif d_tag == 0x61000044: sce_pltrelsz = d_val
    i += 16

print(f"\nDT_SCE_RELA = 0x{sce_rela:X}")
print(f"DT_SCE_RELASZ = 0x{sce_relasz:X}")
print(f"DT_SCE_RELAENT = 0x{sce_relaent:X}")
print(f"DT_SCE_JMPREL = 0x{sce_jmprel:X}")
print(f"DT_SCE_PLTRELSZ = 0x{sce_pltrelsz:X}")

# The DT_SCE_RELA value 0x3900 is very small. It might be a vaddr.
# Let me check which segment contains it.
def vaddr_to_foff(vaddr):
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type != 1: continue
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        p_memsz = struct.unpack_from('<Q', data, off + 40)[0]
        if p_vaddr <= vaddr < p_vaddr + p_memsz:
            return (p_offset + (vaddr - p_vaddr), p_filesz, p_vaddr, p_offset)
    return None

# Check if 0x3900 is a valid vaddr
result = vaddr_to_foff(0x3900)
if result:
    foff, filesz, seg_vaddr, seg_off = result
    print(f"\n0x3900 is in a LOAD segment:")
    print(f"  File offset: 0x{foff:X}")
    print(f"  Reading 64 bytes at this offset:")
    chunk = data[foff:foff+64]
    for j in range(0, 64, 8):
        val = struct.unpack_from('<Q', chunk, j)[0]
        print(f"    +0x{j:02X}: 0x{val:016X}")
else:
    print(f"\n0x3900 is NOT in any LOAD segment")
    # It might be a count or packed value
    print(f"  As a count: {sce_rela}")
    print(f"  As packed: high16=0x{(sce_rela>>48):X} mid16=0x{(sce_rela>>32)&0xFFFF:X} low32=0x{(sce_rela&0xFFFFFFFF):X}")

# Also check the standard RELA
rela_addr = rela_size = 0
i = 0
while i < dyn_size:
    d_tag, d_val = struct.unpack_from('<qQ', data, dyn_foff + i)
    if d_tag == 0: break
    if d_tag == 7: rela_addr = d_val
    elif d_tag == 8: rela_size = d_val
    i += 16

print(f"\nStandard DT_RELA = 0x{rela_addr:X}, size = 0x{rela_size:X}")
print(f"Standard DT_RELA contains {rela_size // 24} entries")

# Check: does the standard RELA contain relocations for the init_array bounds?
# init_array end pointer at 0x1D1A588
# init_array start (from LEA) at 0x800000070
rela_foff = vaddr_to_foff(rela_addr)
if rela_foff:
    rela_foff = rela_foff[0]
    print(f"\nSearching standard RELA for init_array bounds relocations...")
    for i in range(0, rela_size, 24):
        r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
        if r_offset in (0x1D1A580, 0x1D1A588, 0x1D1A590, 0x1D1A598):
            rel_type = r_info & 0xFFFFFFFF
            sym_idx = r_info >> 32
            type_names = {8: 'RELATIVE', 6: 'GLOB_DAT', 7: 'JUMP_SLOT', 1: '64'}
            print(f"  r_offset=0x{r_offset:X} type={type_names.get(rel_type, rel_type)} sym={sym_idx} addend=0x{r_addend:X}")

# Check: what's at 0x1D1A580 (8 bytes before the end pointer)?
# This might be the init_array START pointer
result = vaddr_to_foff(0x1D1A580)
if result:
    foff = result[0]
    val = struct.unpack_from('<Q', data, foff)[0]
    print(f"\n[0x1D1A580] file value = 0x{val:X}")
    # This gets relocated to IMAGE_BASE + val if there's a RELATIVE reloc

# Also check the PLTGOT area
# DT_PLTGOT = 0x1D1A590
# The PLTGOT[0] = address of .dynamic
# PLTGOT[1] = link_map
# PLTGOT[2] = resolver
# PLTGOT[3+] = function pointers (one per PLT entry)
print(f"\n=== PLTGOT area (0x1D1A590) ===")
result = vaddr_to_foff(0x1D1A590)
if result:
    foff = result[0]
    for j in range(0, 64, 8):
        val = struct.unpack_from('<Q', data, foff + j)[0]
        print(f"  [0x{0x1D1A590+j:X}] = 0x{val:X}")
