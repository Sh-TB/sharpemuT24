#!/usr/bin/env python3
"""
EXP-055 Tier A Task 1-7: Find all references to Il2CppCodeRegistration (0x8086E9000)
and Il2CppMetadataRegistration (TBD via types[] back-ref).

Strategy:
  1. Search PRX RELA for addend = file_vaddr of 0x8086E9000 (0x3A14000)
  2. Search PRX RELA for addend = file_vaddr of types[] (0x3C8E950)
  3. Search PRX code for E8/E9 (call/jmp) targeting functions that load 0x8086E9000
  4. Check PRX fini_array entries (11 found in EXP-044)
  5. Check PRX export/NID table
  6. Search eboot for calls taking (CodeReg*, MetadataReg*) pattern
"""
import struct
import sys

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000
EBOOT = "/tmp/games/yatzi/eboot.bin"
EBOOT_BASE = 0x800000000

# Key addresses (runtime)
CODEREG_RUNTIME = 0x8086E9000
TYPES_ARRAY_RUNTIME = 0x80893E950
METHOD_PTRS_RUNTIME = 0x808791958

with open(PRX, "rb") as f:
    prx_data = f.read()

# Parse PRX program headers
e_phoff = struct.unpack_from("<Q", prx_data, 0x20)[0]
e_phentsize = struct.unpack_from("<H", prx_data, 0x36)[0]
e_phnum = struct.unpack_from("<H", prx_data, 0x38)[0]

segments = []
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
        struct.unpack_from("<IIQQQQQQ", prx_data, off)
    if p_type == 1:
        segments.append({
            "type": p_type, "flags": p_flags,
            "file_vaddr": p_vaddr, "filesz": p_filesz, "memsz": p_memsz,
            "file_offset": p_offset,
            "content": prx_data[p_offset:p_offset + p_filesz],
        })

# Parse PRX dynamic section to find RELA
dyn_off = None
dyn_size = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
        struct.unpack_from("<IIQQQQQQ", prx_data, off)
    if p_type == 2:
        dyn_off = p_offset
        dyn_size = p_filesz
        break

rela_off = None
rela_size = None
init_array_off = None
init_array_size = None
fini_array_off = None
fini_array_size = None
for i in range(0, dyn_size, 16):
    d_tag, d_val = struct.unpack_from("<QQ", prx_data, dyn_off + i)
    if d_tag == 0: break
    if d_tag == 7:  # DT_RELA
        for j in range(e_phnum):
            off2 = e_phoff + j * e_phentsize
            p_type2, p_flags2, p_offset2, p_vaddr2, p_paddr2, p_filesz2, p_memsz2, p_align2 = \
                struct.unpack_from("<IIQQQQQQ", prx_data, off2)
            if p_type2 == 1 and p_vaddr2 <= d_val < p_vaddr2 + p_filesz2:
                rela_off = p_offset2 + (d_val - p_vaddr2)
                break
    elif d_tag == 8:
        rela_size = d_val
    elif d_tag == 25:  # DT_INIT_ARRAY
        init_array_off = d_val  # vaddr
    elif d_tag == 27:  # DT_INIT_ARRAYSZ
        init_array_size = d_val
    elif d_tag == 26:  # DT_FINI_ARRAY
        fini_array_off = d_val
    elif d_tag == 28:  # DT_FINI_ARRAYSZ
        fini_array_size = d_val

print(f"PRX RELA: offset=0x{rela_off:X} size=0x{rela_size:X}")
print(f"PRX DT_INIT_ARRAY: vaddr=0x{init_array_off:X} size=0x{init_array_size:X}" if init_array_off else "PRX DT_INIT_ARRAY: not found")
print(f"PRX DT_FINI_ARRAY: vaddr=0x{fini_array_off:X} size=0x{fini_array_size:X}" if fini_array_off else "PRX DT_FINI_ARRAY: not found")

# Convert init/fini array vaddr to runtime address
if init_array_off:
    print(f"  init_array runtime: 0x{init_array_off + PRX_BASE:X}")
    # Read init_array entries (each is 8 bytes, a function pointer via RELATIVE reloc)
    # Find the file offset
    for seg in segments:
        if seg["file_vaddr"] <= init_array_off < seg["file_vaddr"] + seg["filesz"]:
            file_off = seg["file_offset"] + (init_array_off - seg["file_vaddr"])
            n_entries = init_array_size // 8
            print(f"  {n_entries} init_array entries:")
            for k in range(n_entries):
                val = struct.unpack_from("<Q", prx_data, file_off + k * 8)[0]
                # This is a file vaddr, add PRX_BASE for runtime
                print(f"    [{k}] file_vaddr=0x{val:X} runtime=0x{val + PRX_BASE:X}")
            break

if fini_array_off:
    print(f"  fini_array runtime: 0x{fini_array_off + PRX_BASE:X}")
    for seg in segments:
        if seg["file_vaddr"] <= fini_array_off < seg["file_vaddr"] + seg["filesz"]:
            file_off = seg["file_offset"] + (fini_array_off - seg["file_vaddr"])
            n_entries = fini_array_size // 8
            print(f"  {n_entries} fini_array entries:")
            for k in range(n_entries):
                val = struct.unpack_from("<Q", prx_data, file_off + k * 8)[0]
                print(f"    [{k}] file_vaddr=0x{val:X} runtime=0x{val + PRX_BASE:X}")
            break

# Collect ALL RELATIVE relocations
print()
print("=" * 78)
print("Task 1: Search for relocs with addend = CodeRegistration (0x8086E9000)")
print("=" * 78)
codereg_file_vaddr = CODEREG_RUNTIME - PRX_BASE  # 0x3A14000
print(f"CodeRegistration file_vaddr = 0x{codereg_file_vaddr:X}")

all_relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", prx_data, rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    if r_type == 8:  # RELATIVE
        all_relocs.append((r_offset, r_addend))

print(f"Total RELATIVE relocs: {len(all_relocs)}")

# Search for addend matching CodeRegistration
codereg_refs = [(r_off, r_add) for r_off, r_add in all_relocs if r_add == codereg_file_vaddr]
print(f"\nRelocs with addend = 0x{codereg_file_vaddr:X} (CodeRegistration): {len(codereg_refs)}")
for r_off, r_add in codereg_refs[:30]:
    runtime_off = r_off + PRX_BASE
    print(f"  *[0x{runtime_off:X}] = 0x{CODEREG_RUNTIME:X}")

# Task 5: Search for relocs with addend = types[] array (0x80893E950)
print()
print("=" * 78)
print("Task 5: Find Il2CppMetadataRegistration via types[] back-reference")
print("=" * 78)
types_file_vaddr = TYPES_ARRAY_RUNTIME - PRX_BASE  # 0x3C8E950
print(f"types[] file_vaddr = 0x{types_file_vaddr:X}")

types_refs = [(r_off, r_add) for r_off, r_add in all_relocs if r_add == types_file_vaddr]
print(f"\nRelocs with addend = 0x{types_file_vaddr:X} (types[]): {len(types_refs)}")
for r_off, r_add in types_refs[:30]:
    runtime_off = r_off + PRX_BASE
    print(f"  *[0x{runtime_off:X}] = 0x{TYPES_ARRAY_RUNTIME:X}")

# Also search for methodPointers (0x808791958)
print()
methodptrs_file_vaddr = METHOD_PTRS_RUNTIME - PRX_BASE
print(f"methodPointers[] file_vaddr = 0x{methodptrs_file_vaddr:X}")
mp_refs = [(r_off, r_add) for r_off, r_add in all_relocs if r_add == methodptrs_file_vaddr]
print(f"Relocs with addend = 0x{methodptrs_file_vaddr:X} (methodPointers[]): {len(mp_refs)}")
for r_off, r_add in mp_refs[:30]:
    runtime_off = r_off + PRX_BASE
    print(f"  *[0x{runtime_off:X}] = 0x{METHOD_PTRS_RUNTIME:X}")

# If types[] refs found, examine the surrounding struct (count+ptr pairs)
if types_refs:
    print()
    print("=" * 78)
    print("Task 6: Examine struct containing types[] pointer")
    print("=" * 78)
    # Take the first ref, search for relocs in a 0x100-byte window around it
    first_ref_off = types_refs[0][0]
    window_start = first_ref_off - 0x80
    window_end = first_ref_off + 0x80
    nearby_relocs = [(r_off, r_add) for r_off, r_add in all_relocs
                     if window_start <= r_off < window_end]
    nearby_relocs.sort()
    print(f"Relocs in window 0x{window_start + PRX_BASE:X}-0x{window_end + PRX_BASE:X}:")
    for r_off, r_add in nearby_relocs:
        runtime_off = r_off + PRX_BASE
        runtime_val = r_add + PRX_BASE
        # Classify
        if r_add < 0x2B9722A:
            cls = "code"
        elif 0x2B98000 <= r_add < 0x3A126A0:
            cls = "rodata"
        elif 0x3A14000 <= r_add < 0x3C4F818:
            cls = "data1"
        elif 0x3C50000 <= r_add < 0x3E6CBC8:
            cls = "data2"
        else:
            cls = "other"
        offset_in_struct = r_off - (first_ref_off - 0x80)
        print(f"  +0x{offset_in_struct:02X} *[0x{runtime_off:X}] = 0x{runtime_val:X} ({cls})")

# Task 7: Search eboot for calls taking (CodeReg*, MetadataReg*) pattern
print()
print("=" * 78)
print("Task 7: Search eboot for calls with CodeReg/MetadataReg args")
print("=" * 78)
# This is hard to do statically — args are in registers.
# Instead, search eboot for any LEA loading the CodeRegistration address.
# CodeRegistration is at 0x8086E9000 (PRX). Eboot would need to load this
# via a GOT entry or import.
# Search eboot RELA for addend = 0x8086E9000 (if eboot imports the symbol)
with open(EBOOT, "rb") as f:
    eboot_data = f.read()
eboot_rela_off = 0x1E075F0
eboot_rela_size = 0x124170
codereg_in_eboot = []
for i in range(0, eboot_rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", eboot_data, eboot_rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    if r_type == 8 and (r_addend == CODEREG_RUNTIME or r_addend == codereg_file_vaddr):
        codereg_in_eboot.append((r_offset, r_addend, r_type))
print(f"Eboot relocs with addend matching CodeRegistration: {len(codereg_in_eboot)}")
for r_off, r_add, r_type in codereg_in_eboot[:10]:
    print(f"  r_offset=0x{r_off:X} (runtime 0x{r_off + EBOOT_BASE:X}) type={r_type} addend=0x{r_add:X}")

# Also check non-RELATIVE relocs (symbol-based) in eboot that might import CodeRegistration
print()
print("Eboot non-RELATIVE relocs (symbol-based imports, first 20 with non-zero sym):")
sym_count = 0
for i in range(0, eboot_rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", eboot_data, eboot_rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    r_sym = r_info >> 32
    if r_sym != 0 and r_type != 8:
        sym_count += 1
        if sym_count <= 20:
            print(f"  r_offset=0x{r_offset:X} type={r_type} sym={r_sym} addend=0x{r_addend:X}")
print(f"Total non-RELATIVE symbol relocs: {sym_count}")
