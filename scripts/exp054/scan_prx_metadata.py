#!/usr/bin/env python3
"""
EXP-054 Tier 1 Task 2A: Full PRX scan for Il2CppCodeRegistration/MetadataRegistration.

The PRX (Il2cppUserAssemblies.prx) is 74MB with 383,614 RELA relocations.
We search for patterns that match Unity's IL2CPP registration structures:

  Il2CppCodeRegistration {
      uint32_t methodPointersCount;
      const Il2CppMethodPointer* methodPointers;  // array of func ptrs
      uint32_t reversePInvokeWrapperCount;
      ...
  }

  Il2CppMetadataRegistration {
      int32_t genericClassesCount;
      const Il2CppGenericClass* const* genericClasses;
      int32_t typesCount;
      const Il2CppType* const* types;        // array of type ptrs
      int32_t methodSpecsCount;
      ...
      const char* const* typeNames;          // array of string ptrs
  }

Strategy:
  1. Parse all 383,614 RELA relocations
  2. Group by r_offset proximity (entries in arrays are contiguous)
  3. Find arrays of:
     a. Pure code pointers (all addends in .text range)
     b. Pure rodata pointers (all addends in .rodata range)
     c. Mixed code+rodata pairs (registration table signature)
  4. For string arrays, read the strings and check if they look like type names
     (e.g., "System.Object", "UnityEngine.Transform", etc.)
"""
import struct
import sys

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000  # runtime base

with open(PRX, "rb") as f:
    data = f.read()

# Parse PRX program headers
e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
e_phnum = struct.unpack_from("<H", data, 0x38)[0]

segments = []
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
        struct.unpack_from("<IIQQQQQQ", data, off)
    if p_type == 1:  # PT_LOAD
        segments.append({
            "file_vaddr": p_vaddr,
            "filesz": p_filesz,
            "memsz": p_memsz,
            "file_offset": p_offset,
            "flags": p_flags,
            "content": data[p_offset:p_offset + p_filesz],
        })

# Find code segment range (file vaddr)
code_seg = next(s for s in segments if s["flags"] & 1)  # PF_X
code_min = code_seg["file_vaddr"]
code_max = code_seg["file_vaddr"] + code_seg["filesz"]
print(f"PRX code segment: file_vaddr 0x{code_min:X} - 0x{code_max:X} (runtime 0x{code_min + PRX_BASE:X} - 0x{code_max + PRX_BASE:X})")

# Find rodata segment (PF_R, not PF_X, not PF_W)
rodata_segs = [s for s in segments if (s["flags"] & 4) and not (s["flags"] & 2) and not (s["flags"] & 1)]
print(f"PRX rodata segments: {len(rodata_segs)}")
for s in rodata_segs:
    print(f"  file_vaddr 0x{s['file_vaddr']:X} - 0x{s['file_vaddr'] + s['filesz']:X}")

# Find data segments (PF_W)
data_segs = [s for s in segments if (s["flags"] & 2)]
print(f"PRX data segments: {len(data_segs)}")
for s in data_segs:
    print(f"  file_vaddr 0x{s['file_vaddr']:X} - 0x{s['file_vaddr'] + s['filesz']:X}")

# Parse RELA
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

print(f"\nPRX RELA: offset=0x{rela_off:X} size=0x{rela_size:X} entries={rela_size // 24}")

# Collect all RELATIVE relocations
relocs = []
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    if r_type == 8:  # R_X86_64_RELATIVE
        relocs.append((r_offset, r_addend))

print(f"Total RELATIVE relocs: {len(relocs)}")

# Classify each addend: code, rodata, data, or other
def classify(addend):
    if code_min <= addend < code_max:
        return "code"
    for s in rodata_segs:
        if s["file_vaddr"] <= addend < s["file_vaddr"] + s["filesz"]:
            return "rodata"
    for s in data_segs:
        if s["file_vaddr"] <= addend < s["file_vaddr"] + s["filesz"]:
            return "data"
    return "other"

# Group relocs by r_offset proximity (contiguous arrays)
relocs.sort()
print(f"\nSearching for contiguous pointer arrays...")

# Find runs of relocs where r_offset increases by 8 each time
arrays = []
current_array = [relocs[0]]
for i in range(1, len(relocs)):
    prev_off = relocs[i-1][0]
    curr_off = relocs[i][0]
    if curr_off == prev_off + 8:
        current_array.append(relocs[i])
    else:
        if len(current_array) >= 8:  # only keep arrays with 8+ entries
            arrays.append(current_array)
        current_array = [relocs[i]]
if len(current_array) >= 8:
    arrays.append(current_array)

print(f"Found {len(arrays)} contiguous arrays (8+ entries)")

# Classify arrays by their addend types
print(f"\nTop 30 largest arrays:")
arrays.sort(key=lambda a: -len(a))
for arr in arrays[:30]:
    start_off = arr[0][0]
    end_off = arr[-1][0]
    types = [classify(addend) for _, addend in arr]
    code_count = types.count("code")
    rodata_count = types.count("rodata")
    data_count = types.count("data")
    other_count = types.count("other")
    runtime_start = start_off + PRX_BASE
    runtime_end = end_off + PRX_BASE
    print(f"  array @ 0x{runtime_start:X}-0x{runtime_end:X} ({len(arr)} entries): "
          f"code={code_count} rodata={rodata_count} data={data_count} other={other_count}")
    # Show first 3 addends
    for j in range(min(3, len(arr))):
        off, addend = arr[j]
        cls = classify(addend)
        print(f"    [{j}] +0x{off - start_off:X}: 0x{addend + PRX_BASE:X} ({cls})")

# For arrays that are ALL code pointers, check if they look like method pointers
print(f"\nArrays with ALL code pointers (methodPointers candidates):")
code_only_arrays = [a for a in arrays if all(classify(addend) == "code" for _, addend in a)]
print(f"  Count: {len(code_only_arrays)}")
for arr in code_only_arrays[:10]:
    start_off = arr[0][0]
    runtime_start = start_off + PRX_BASE
    print(f"  array @ 0x{runtime_start:X} ({len(arr)} code ptrs)")
    for j in range(min(3, len(arr))):
        off, addend = arr[j]
        print(f"    [{j}] 0x{addend + PRX_BASE:X}")

# For arrays that are ALL rodata pointers, read the strings
print(f"\nArrays with ALL rodata pointers (typeNames candidates):")
rodata_only_arrays = [a for a in arrays if all(classify(addend) == "rodata" for _, addend in a)]
print(f"  Count: {len(rodata_only_arrays)}")
for arr in rodata_only_arrays[:5]:
    start_off = arr[0][0]
    runtime_start = start_off + PRX_BASE
    print(f"  array @ 0x{runtime_start:X} ({len(arr)} rodata ptrs)")
    # Read first 5 strings
    for j in range(min(5, len(arr))):
        off, addend = arr[j]
        # Read string at file offset = addend (since addend is file vaddr for rodata)
        if addend < len(data):
            end = data.find(b'\x00', addend)
            if end < 0 or end - addend > 200:
                end = addend + 100
            s = data[addend:end].decode('ascii', errors='replace')
            print(f"    [{j}] 0x{addend + PRX_BASE:X} -> \"{s[:80]}\"")

# For mixed arrays (code + rodata pairs), check if they're registration tables
print(f"\nMixed arrays (code+rodata pairs, registration table candidates):")
mixed_arrays = []
for arr in arrays:
    types = [classify(addend) for _, addend in arr]
    code_count = types.count("code")
    rodata_count = types.count("rodata")
    if code_count > 0 and rodata_count > 0:
        mixed_arrays.append((arr, code_count, rodata_count))
print(f"  Count: {len(mixed_arrays)}")
for arr, cc, rc in mixed_arrays[:5]:
    start_off = arr[0][0]
    runtime_start = start_off + PRX_BASE
    print(f"  array @ 0x{runtime_start:X} ({len(arr)} entries: {cc} code, {rc} rodata)")
    for j in range(min(6, len(arr))):
        off, addend = arr[j]
        cls = classify(addend)
        if cls == "rodata" and addend < len(data):
            end = data.find(b'\x00', addend)
            if end < 0 or end - addend > 200:
                end = addend + 100
            s = data[addend:end].decode('ascii', errors='replace')
            print(f"    [{j}] 0x{addend + PRX_BASE:X} ({cls}) -> \"{s[:80]}\"")
        else:
            print(f"    [{j}] 0x{addend + PRX_BASE:X} ({cls})")
