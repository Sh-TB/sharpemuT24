#!/usr/bin/env python3
"""
EXP-052 Task A1k: Search RELA relocations for targets pointing to our functions.

PS5 ELFs use RELA relocations. Function pointer tables are initialized via
R_X86_64_RELATIVE relocations: r_offset = location to write, r_addend = target.

Strategy:
  1. Parse DT_RELA, DT_RELASZ, DT_RELAENT from dynamic table.
  2. Iterate all RELA entries.
  3. For each R_X86_64_RELATIVE entry, compute target = base + r_addend.
  4. Check if target matches our function addresses.
  5. Report matching entries (r_offset = where the pointer is stored).
"""
import struct
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import parse_elf_segments, EBOOT, PRX, EBOOT_BASE, PRX_BASE

# Dynamic section tags
DT_RELA = 7
DT_RELASZ = 8
DT_RELAENT = 9
DT_SCE_RELA = 0x61000018  # PS5-specific

TARGETS = {
    0x800805AE0: "wrapper (calls hash_insert)",
    0x8007F90A0: "hash_table_writer",
    0x800806940: "hash_insert",
    0x8004bd620: "metadata_lookup",
    0x800ce3aa0: "hash_key_gen",
    0x800C66670: "metadata_list_create",
    0x800C66B40: "metadata_lookup_alt",
    0x80134FA00: "callback_func",
    0x80135DDD0: "crash_func",
    0x8013EB6B0: "init_func",
    0x804F04BA0: "real_init",
    0x804ED85D0: "il2cpp_init",
    0x804F677A0: "il2cpp_add_internal_call",
}

def parse_dynamic(path):
    """Parse the dynamic section to find RELA info."""
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    with open(path, "rb") as f:
        data = f.read()
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    
    dynamic_seg = None
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
            struct.unpack_from("<IIQQQQQQ", data, off)
        if p_type == 2:  # PT_DYNAMIC
            dynamic_seg = (p_offset, p_filesz, p_vaddr + base)
            break
    if not dynamic_seg:
        return None
    dyn_off, dyn_size, dyn_vaddr = dynamic_seg
    entries = []
    for i in range(0, dyn_size, 16):
        d_tag, d_val = struct.unpack_from("<QQ", data, dyn_off + i)
        if d_tag == 0:
            break
        entries.append((d_tag, d_val))
    return entries, dyn_off, dyn_size, dyn_vaddr, data

def find_rela_refs(path, targets):
    """Find RELA relocations whose addend (target) matches our functions."""
    result = parse_dynamic(path)
    if not result:
        return []
    entries, dyn_off, dyn_size, dyn_vaddr, data = result
    
    rela_off = None
    rela_size = None
    rela_ent = 24  # default
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    
    for tag, val in entries:
        if tag == DT_RELA or tag == DT_SCE_RELA:
            # DT_RELA stores the virtual address of the table
            # We need to convert back to file offset
            target_vaddr = val
            # Try: val is the file vaddr (without base), or with base?
            # Let's try both
            if val >= base:
                target_vaddr_in_file = val - base
            else:
                target_vaddr_in_file = val
            # Find the segment containing this vaddr
            segs = parse_elf_segments(path, load_base=0)
            for seg in segs:
                if seg["type"] == 1 and seg["file_vaddr"] <= target_vaddr_in_file < seg["file_vaddr"] + seg["filesz"]:
                    rela_off = seg["file_offset"] + (target_vaddr_in_file - seg["file_vaddr"])
                    break
        elif tag == DT_RELASZ:
            rela_size = val
        elif tag == DT_RELAENT:
            rela_ent = val
    
    if rela_off is None or rela_size is None:
        print(f"  No RELA section found. dynamic entries:")
        for tag, val in entries[:30]:
            print(f"    tag=0x{tag:X} val=0x{val:X}")
        return []
    
    print(f"  RELA at file offset 0x{rela_off:X}, size 0x{rela_size:X}, entry size {rela_ent}")
    
    refs = []
    for i in range(0, rela_size, rela_ent):
        r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, rela_off + i)
        r_type = r_info & 0xFFFFFFFF
        r_sym = r_info >> 32
        # R_X86_64_RELATIVE = 8
        if r_type == 8:
            target = base + r_addend
            if target in targets:
                # The pointer is written at runtime address (base + r_offset)
                ptr_location = base + r_offset
                refs.append((ptr_location, target, targets[target]))
    return refs

def main():
    print("=" * 78)
    print("EXP-052 Task A1k: RELA relocation references")
    print("=" * 78)
    
    for path, label in [(EBOOT, "eboot"), (PRX, "PRX")]:
        print(f"\n========== {label} ==========")
        refs = find_rela_refs(path, TARGETS)
        if refs:
            print(f"  Found {len(refs)} references:")
            for ptr_loc, tgt, name in refs:
                print(f"    *[0x{ptr_loc:X}] = 0x{tgt:X}  ({name})")
        else:
            print("  No references found in RELA table.")

if __name__ == "__main__":
    main()
