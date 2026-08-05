#!/usr/bin/env python3
"""EXP-155 Task 4: Validate decoder ELF findings — DT_ORBIS_INIT vs DT_INIT."""

import struct

EBOOT_PATH = "/tmp/exp151_games/eboot.bin"
PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"

# PS5 ELF dynamic tags
DT_NULL = 0
DT_NEEDED = 1
DT_INIT = 12
DT_FINI = 13
DT_INIT_ARRAY = 25
DT_INIT_ARRAYSZ = 27

# PS5-specific dynamic tags (from PS5 SDK)
DT_ORBIS_INIT = 0x60000001  # PS5 module_start
DT_ORBIS_FINI = 0x60000002  # PS5 module_stop
DT_ORBIS_PRX_MODULE_NAME = 0x60000003

def parse_elf64_dynamic(path, label):
    data = open(path, 'rb').read()
    
    # Parse ELF header
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    e_shoff = struct.unpack_from('<Q', data, 0x28)[0]
    e_shentsize = struct.unpack_from('<H', data, 0x3A)[0]
    e_shnum = struct.unpack_from('<H', data, 0x3C)[0]
    e_shstrndx = struct.unpack_from('<H', data, 0x3E)[0]
    
    print(f"\n{'='*60}")
    print(f"  {label}: {path.split('/')[-1]}")
    print(f"{'='*60}")
    
    # Find PT_DYNAMIC segment
    dynamic_seg = None
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        if p_type == 2:  # PT_DYNAMIC
            dynamic_seg = {'offset': p_offset, 'vaddr': p_vaddr, 'filesz': p_filesz}
            break
    
    if not dynamic_seg:
        print("  No PT_DYNAMIC segment found")
        return
    
    print(f"  PT_DYNAMIC: offset=0x{dynamic_seg['offset']:X} filesz=0x{dynamic_seg['filesz']:X}")
    
    # Parse dynamic entries
    entries = []
    for i in range(dynamic_seg['filesz'] // 16):
        off = dynamic_seg['offset'] + i * 16
        if off + 16 > len(data):
            break
        d_tag = struct.unpack_from('<q', data, off)[0]  # signed
        d_val = struct.unpack_from('<Q', data, off + 8)[0]
        if d_tag == 0:
            entries.append((d_tag, d_val, 'DT_NULL'))
            break
        entries.append((d_tag, d_val, ''))
    
    # Classify tags
    tag_names = {
        0: 'DT_NULL', 1: 'DT_NEEDED', 2: 'DT_PLTRELSZ', 3: 'DT_PLTGOT',
        4: 'DT_HASH', 5: 'DT_STRTAB', 6: 'DT_SYMTAB', 7: 'DT_RELA',
        8: 'DT_RELASZ', 9: 'DT_RELAENT', 10: 'DT_STRSZ', 11: 'DT_SYMENT',
        12: 'DT_INIT', 13: 'DT_FINI', 14: 'DT_SONAME', 15: 'DT_RPATH',
        20: 'DT_PLTREL', 21: 'DT_DEBUG', 23: 'DT_JMPREL',
        25: 'DT_INIT_ARRAY', 26: 'DT_FINI_ARRAY', 27: 'DT_INIT_ARRAYSZ', 28: 'DT_FINI_ARRAYSZ',
        0x6FFFFFFB: 'DT_FLAGS_1',
    }
    
    # PS5-specific
    ps5_tags = {
        0x60000001: 'DT_ORBIS_INIT (module_start?)',
        0x60000002: 'DT_ORBIS_FINI (module_stop?)',
        0x60000003: 'DT_ORBIS_PRX_MODULE_NAME',
        0x6000000A: 'DT_ORBIS_PRX_MODULE_INFO',
    }
    
    print(f"\n  Dynamic entries ({len(entries)}):")
    has_dt_init = False
    has_dt_orbis_init = False
    dt_init_val = None
    dt_orbis_init_val = None
    
    for d_tag, d_val, _ in entries:
        name = tag_names.get(d_tag, ps5_tags.get(d_tag, f'DT_0x{d_tag:X}'))
        print(f"    d_tag={d_tag:#x} d_val=0x{d_val:X} ({name})")
        
        if d_tag == DT_INIT:
            has_dt_init = True
            dt_init_val = d_val
        if d_tag == DT_ORBIS_INIT:
            has_dt_orbis_init = True
            dt_orbis_init_val = d_val
    
    print(f"\n  Summary:")
    print(f"    DT_INIT present: {has_dt_init}" + (f" (value=0x{dt_init_val:X})" if has_dt_init else ""))
    print(f"    DT_ORBIS_INIT present: {has_dt_orbis_init}" + (f" (value=0x{dt_orbis_init_val:X})" if has_dt_orbis_init else ""))
    
    if has_dt_init and not has_dt_orbis_init:
        print(f"    → Uses DT_INIT (standard ELF), NOT DT_ORBIS_INIT")
    elif has_dt_orbis_init and not has_dt_init:
        print(f"    → Uses DT_ORBIS_INIT (PS5-specific)")
    elif has_dt_init and has_dt_orbis_init:
        print(f"    → Has BOTH DT_INIT and DT_ORBIS_INIT")
    else:
        print(f"    → Has NEITHER — check DT_INIT_ARRAY")

def main():
    print("=" * 80)
    print("EXP-155 Task 4: Validate ELF Initialization Path")
    print("=" * 80)
    
    parse_elf64_dynamic(EBOOT_PATH, "EBOOT")
    parse_elf64_dynamic(PRX_PATH, "PRX (Il2cppUserAssemblies)")
    
    print(f"\n{'='*80}")
    print("ELF INIT VALIDATION SUMMARY")
    print(f"{'='*80}")
    print("""
Decoder hypothesis: DT_ORBIS_INIT may not exist, DT_INIT is used instead.

From runtime log (EXP-118):
  Line 864: [RUNTIME] Starting module Il2cppUserAssemblies.prx: dt_init=0x0000000804CD5010
  → The loader calls dt_init, which is the DT_INIT value

The ELF dynamic table shows whether DT_INIT or DT_ORBIS_INIT is used.
SharpEmu's loader should handle whichever tag is present.

If DT_INIT is used (standard ELF), SharpEmu handles it correctly.
If DT_ORBIS_INIT is used (PS5-specific), SharpEmu must handle it specially.
""")

if __name__ == '__main__':
    main()
