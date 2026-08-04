#!/usr/bin/env python3
"""
EXP-056: Comprehensive IL2CPP Registration Chain Investigation.

Covers Groups 1, 3, 4, 5 of the master plan:
  - G1-T6: Full field-by-field dump of CodeReg + MetaReg
  - G1-T9: Verify 0x80885C580 file-vaddr->runtime translation
  - G1-T10: Search for codeGenModules[] array
  - G3-T23: Verify CodeReg is really CodeReg vs Il2CppCodeGenModule
  - G3-T27: Search for s_Il2CppCodeGenModules[] array pattern
  - G4-T34: Verify wrapper 0x800805AE0 is metadata-insert vs P/Invoke-only
  - G5-T38: Runtime dump of CodeReg+MetaReg state
"""
import struct
import sys

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000
EBOOT = "/tmp/games/yatzi/eboot.bin"
EBOOT_BASE = 0x800000000

CODEREG_RUNTIME = 0x8086E9000
METAREG_RUNTIME = 0x80885C580
TYPES_ARRAY_RUNTIME = 0x80893E950
WRAPPER_RUNTIME = 0x800805AE0  # in eboot
HASH_TABLE_PTR_RUNTIME = 0x801EF7610  # in eboot

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

def runtime_to_file_off(runtime_addr):
    file_vaddr = runtime_addr - PRX_BASE
    for seg in segments:
        if seg["file_vaddr"] <= file_vaddr < seg["file_vaddr"] + seg["filesz"]:
            return seg["file_offset"] + (file_vaddr - seg["file_vaddr"])
    return None

def classify(addend):
    if addend < 0x2B9722A:
        return "code"
    elif 0x2B98000 <= addend < 0x3A126A0:
        return "rodata"
    elif 0x3A14000 <= addend < 0x3C4F818:
        return "data1"
    elif 0x3C50000 <= addend < 0x3E6CBC8:
        return "data2"
    return "other"

# Parse RELA
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
for i in range(0, dyn_size, 16):
    d_tag, d_val = struct.unpack_from("<QQ", prx_data, dyn_off + i)
    if d_tag == 0: break
    if d_tag == 7:
        for j in range(e_phnum):
            off2 = e_phoff + j * e_phentsize
            p_type2, p_flags2, p_offset2, p_vaddr2, p_paddr2, p_filesz2, p_memsz2, p_align2 = \
                struct.unpack_from("<IIQQQQQQ", prx_data, off2)
            if p_type2 == 1 and p_vaddr2 <= d_val < p_vaddr2 + p_filesz2:
                rela_off = p_offset2 + (d_val - p_vaddr2)
                break
    elif d_tag == 8:
        rela_size = d_val

# Collect all RELATIVE relocations as a dict: r_offset -> r_addend
all_relocs = {}
for i in range(0, rela_size, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", prx_data, rela_off + i)
    r_type = r_info & 0xFFFFFFFF
    if r_type == 8:
        all_relocs[r_offset] = r_addend

print(f"Total RELATIVE relocs: {len(all_relocs)}")

# ===== G1-T9: Verify address translation =====
print()
print("=" * 78)
print("G1-T9: Verify 0x80885C580 file-vaddr -> runtime translation")
print("=" * 78)
meta_file_vaddr = METAREG_RUNTIME - PRX_BASE
print(f"MetaReg runtime: 0x{METAREG_RUNTIME:X}")
print(f"MetaReg file_vaddr: 0x{meta_file_vaddr:X}")
print(f"PRX_BASE: 0x{PRX_BASE:X}")
print(f"Verification: 0x{meta_file_vaddr:X} + 0x{PRX_BASE:X} = 0x{meta_file_vaddr + PRX_BASE:X}")
# Find which segment contains it
for i, seg in enumerate(segments):
    if seg["file_vaddr"] <= meta_file_vaddr < seg["file_vaddr"] + seg["filesz"]:
        file_off = seg["file_offset"] + (meta_file_vaddr - seg["file_vaddr"])
        print(f"Located in segment {i}: file_vaddr=0x{seg['file_vaddr']:X}, file_off=0x{file_off:X}")
        # Read raw bytes at file offset
        b = prx_data[file_off:file_off + 0x100]
        print(f"Raw bytes at file offset 0x{file_off:X} (first 0x100):")
        for j in range(0, 0x100, 8):
            q = struct.unpack_from("<Q", b, j)[0]
            print(f"  +0x{j:02X}: 0x{q:016X}")
        break

# ===== G1-T6: Full field-by-field dump of CodeReg + MetaReg =====
print()
print("=" * 78)
print("G1-T6: Full field-by-field dump of CodeReg + MetaReg (with relocs applied)")
print("=" * 78)

def dump_struct(name, runtime_addr, size=0x100):
    file_vaddr = runtime_addr - PRX_BASE
    print(f"\n{name} @ 0x{runtime_addr:X} (file_vaddr 0x{file_vaddr:X}):")
    # Read raw file bytes (pre-reloc)
    for seg in segments:
        if seg["file_vaddr"] <= file_vaddr < seg["file_vaddr"] + seg["filesz"]:
            file_off = seg["file_offset"] + (file_vaddr - seg["file_vaddr"])
            raw = prx_data[file_off:file_off + size]
            break
    else:
        print(f"  NOT in any file segment (BSS)")
        return
    
    print(f"  {'Offset':<8} {'Raw (file)':<18} {'Reloc addend':<18} {'Runtime value':<18} {'Class'}")
    for j in range(0, size, 8):
        raw_val = struct.unpack_from("<Q", raw, j)[0]
        reloc_addend = all_relocs.get(file_vaddr + j, None)
        if reloc_addend is not None:
            runtime_val = reloc_addend + PRX_BASE
            cls = classify(reloc_addend)
            print(f"  +0x{j:02X}    0x{raw_val:016X}  0x{reloc_addend + PRX_BASE:016X}  0x{runtime_val:016X}  {cls}")
        else:
            if raw_val != 0:
                print(f"  +0x{j:02X}    0x{raw_val:016X}  (no reloc)         0x{raw_val:016X}  (inline data)")

dump_struct("Il2CppCodeRegistration", CODEREG_RUNTIME, 0xA0)
dump_struct("Il2CppMetadataRegistration", METAREG_RUNTIME, 0xA0)

# ===== G3-T23: Verify CodeReg is really CodeReg =====
print()
print("=" * 78)
print("G3-T23: Is 0x8086E9000 really Il2CppCodeRegistration?")
print("=" * 78)
print("""
Unity's Il2CppCodeRegistration struct (public header):
  uint32_t methodPointersCount;
  const Il2CppMethodPointer* methodPointers;
  uint32_t reversePInvokeWrapperCount;
  const Il2CppMethodPointer* reversePInvokeWrappers;
  uint32_t rgcxStartCount;  // (Unity 2019+)
  ...
  uint32_t codeGenModulesCount;
  const Il2CppCodeGenModule** codeGenModules;

Our struct at 0x8086E9000:
  +0x08: rodata ptr (string "22Il2CppExceptionWrapper")
  +0x10: count=17, +0x18: array ptr
  +0x20: count=103561, +0x28: methodPointers[] (103816 code ptrs)
  +0x30: mixed array ptr (31818 entries)
  +0x38: count=18708, +0x40: secondary method ptrs
  ...

The (count, pointer) pair pattern matches. The 103561 count at +0x20 is close
to the 103816 actual methodPointers entries (small discrepancy may be due to
alignment or a sub-array). This IS likely Il2CppCodeRegistration.

However, the first field (+0x08) being a rodata string pointer is unusual —
Unity's struct starts with a count. This might be a Unity 2022+ variant with
a version string or magic field at the start.
""")

# ===== G1-T10/G3-T27: Search for codeGenModules[] array =====
print("=" * 78)
print("G1-T10/G3-T27: Search for codeGenModules[] array")
print("=" * 78)
# codeGenModules[] is an array of Il2CppCodeGenModule* pointers.
# Each Il2CppCodeGenModule is a struct containing pointers to per-assembly
# CodeRegistration and MetadataRegistration.
# Search for a small array (1-10 entries) of pointers into data1/data2 segment.

# Look for relocs whose addend is in the CodeReg/MetaReg region
# (0x8086E9000-0x8086E9100 or 0x80885C580-0x80885C680)
codereg_range = (CODEREG_RUNTIME - PRX_BASE, CODEREG_RUNTIME - PRX_BASE + 0x100)
metareg_range = (METAREG_RUNTIME - PRX_BASE, METAREG_RUNTIME - PRX_BASE + 0x100)

# Find ALL relocs whose addend is in either range
refs_to_codereg = []
refs_to_metareg = []
for r_off, r_add in all_relocs.items():
    if codereg_range[0] <= r_add < codereg_range[1]:
        refs_to_codereg.append((r_off, r_add))
    if metareg_range[0] <= r_add < metareg_range[1]:
        refs_to_metareg.append((r_off, r_add))

print(f"Relocs pointing INTO CodeReg struct: {len(refs_to_codereg)}")
print(f"Relocs pointing INTO MetaReg struct: {len(refs_to_metareg)}")

# Look for a pair of adjacent relocs: one pointing to CodeReg, one to MetaReg
# (this would be the codeGenModules[] entry)
print()
print("Searching for adjacent CodeReg+MetaReg pointer pairs (codeGenModules[])...")
codereg_refs_set = {r_off: r_add for r_off, r_add in refs_to_codereg}
for r_off, r_add in refs_to_metareg:
    # Check if there's a CodeReg ref at r_off-8, r_off+8, r_off-16, r_off+16
    for delta in [-16, -8, 8, 16]:
        if (r_off + delta) in codereg_refs_set:
            pair_off = r_off + delta
            print(f"  FOUND PAIR at runtime 0x{min(r_off, pair_off) + PRX_BASE:X}:")
            print(f"    [0x{pair_off + PRX_BASE:X}] = 0x{codereg_refs_set[pair_off] + PRX_BASE:X} (CodeReg)")
            print(f"    [0x{r_off + PRX_BASE:X}] = 0x{r_add + PRX_BASE:X} (MetaReg)")

# ===== G4-T34: Verify wrapper 0x800805AE0 is metadata-insert vs P/Invoke-only =====
print()
print("=" * 78)
print("G4-T34: Wrapper 0x800805AE0 — metadata-insert or P/Invoke-only?")
print("=" * 78)
print("""
From EXP-052 analysis:
  Wrapper at 0x800805AE0:
  - Takes rdi = string pointer
  - Checks if string starts with "#dllimport:" (byte-by-byte comparison)
  - If "#dllimport:": does P/Invoke-specific handling
  - Otherwise: generic metadata registration
  - Calls hash_insert at 0x800806940

The "#dllimport:" prefix check is for P/Invoke (native function imports).
But the wrapper has a GENERIC path for strings WITHOUT that prefix.

Question: Is the generic path for IL2CPP metadata, or for something else?

Evidence from EXP-053:
  - Wrapper was NEVER called (0 hits) during boot
  - Hash table at 0x801EF7610 (read by lookup 0x8004BD620) stayed empty

If the wrapper is the metadata inserter, it should be called during il2cpp_init.
If it's P/Invoke-only, the metadata inserter is a DIFFERENT function.

From EXP-052: The lookup 0x8004BD620 reads hash_table from [0x801EF7610].
The writer 0x8007F90A0 allocates the hash table at [0x801EF7610].
The wrapper 0x800805AE0 calls insert 0x800806940 which writes to the SAME
hash table.

So the wrapper IS connected to the hash table. But is the hash table for
metadata or for P/Invoke?

The lookup 0x8004BD620 is called from 286 sites in eboot — too many for just
P/Invoke. It's likely the general IL2CPP symbol resolver (types, methods,
AND P/Invoke).

CONCLUSION: The wrapper handles BOTH P/Invoke and metadata. The "#dllimport:"
prefix is just a special case. Without the prefix, it does generic metadata
insertion.

The wrapper being NEVER called means NEITHER P/Invoke NOR metadata gets
registered. This is consistent with the missing walker hypothesis.
""")

# ===== G5-T38: Check if structs are already populated via relocations =====
print("=" * 78)
print("G5-T38: Are CodeReg+MetaReg already populated via relocations?")
print("=" * 78)
# Check if all pointer fields in both structs have relocations
print("\nCodeReg pointer fields (offsets with RELATIVE relocs):")
codereg_file_vaddr = CODEREG_RUNTIME - PRX_BASE
for off in range(0, 0xA0, 8):
    if (codereg_file_vaddr + off) in all_relocs:
        addend = all_relocs[codereg_file_vaddr + off]
        print(f"  +0x{off:02X}: HAS reloc -> 0x{addend + PRX_BASE:X} ({classify(addend)})")
    else:
        # Check raw value
        for seg in segments:
            if seg["file_vaddr"] <= codereg_file_vaddr + off < seg["file_vaddr"] + seg["filesz"]:
                file_off = seg["file_offset"] + (codereg_file_vaddr + off - seg["file_vaddr"])
                raw = struct.unpack_from("<Q", prx_data, file_off)[0]
                if raw != 0:
                    print(f"  +0x{off:02X}: NO reloc, raw=0x{raw:X} (inline data)")
                break

print("\nMetaReg pointer fields (offsets with RELATIVE relocs):")
metareg_file_vaddr = METAREG_RUNTIME - PRX_BASE
for off in range(0, 0xA0, 8):
    if (metareg_file_vaddr + off) in all_relocs:
        addend = all_relocs[metareg_file_vaddr + off]
        print(f"  +0x{off:02X}: HAS reloc -> 0x{addend + PRX_BASE:X} ({classify(addend)})")
    else:
        for seg in segments:
            if seg["file_vaddr"] <= metareg_file_vaddr + off < seg["file_vaddr"] + seg["filesz"]:
                file_off = seg["file_offset"] + (metareg_file_vaddr + off - seg["file_vaddr"])
                raw = struct.unpack_from("<Q", prx_data, file_off)[0]
                if raw != 0:
                    print(f"  +0x{off:02X}: NO reloc, raw=0x{raw:X} (inline data)")
                break
