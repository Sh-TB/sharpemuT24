#!/usr/bin/env python3
"""EXP-079: Resolve PLT symbols using standard ELF DT_JMPREL/DT_SYMTAB/DT_STRTAB."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def parse_dynamic(img):
    dyn_seg = None
    for s in img.segments:
        if s['p_type'] == 2:
            dyn_seg = s
            break
    if dyn_seg is None:
        return None
    dyn_raw = img.raw[dyn_seg['p_offset']:dyn_seg['p_offset'] + dyn_seg['p_filesz']]
    info = {}
    needed = []
    for i in range(0, len(dyn_raw), 16):
        if i + 16 > len(dyn_raw):
            break
        d_tag, d_val = struct.unpack_from('<qQ', dyn_raw, i)
        if d_tag == 0: break
        if d_tag == 1:  # DT_NEEDED
            needed.append(d_val)
        else:
            info[d_tag] = d_val
    return info, needed

def find_string(img, strtab_vaddr, str_offset):
    strtab_off = img.vaddr_to_offset(strtab_vaddr)
    if strtab_off is None: return None
    file_off = strtab_off + str_offset
    if file_off >= len(img.raw): return None
    end = img.raw.find(b'\x00', file_off)
    if end < 0: return None
    return img.raw[file_off:end].decode('utf-8', errors='replace')

def main():
    img = ElfImage(EBOOT_PATH)
    info, needed = parse_dynamic(img)
    print("=== Dynamic info ===")
    for k in sorted(info.keys()):
        print(f"  DT 0x{k:X} = 0x{info[k]:X}")
    
    strtab_vaddr = info.get(5)  # DT_STRTAB
    symtab_vaddr = info.get(6)  # DT_SYMTAB
    jmprel_vaddr = info.get(23) # DT_JMPREL
    jmprel_size = info.get(2)   # DT_PLTRELSZ
    sym_ent = info.get(11, 24)  # DT_SYMENT
    rela_vaddr = info.get(7)    # DT_RELA
    relasz = info.get(8)        # DT_RELASZ
    
    print(f"\n  STRTAB  vaddr = 0x{strtab_vaddr:X}" if strtab_vaddr else "  STRTAB not found")
    print(f"  SYMTAB  vaddr = 0x{symtab_vaddr:X}" if symtab_vaddr else "  SYMTAB not found")
    print(f"  JMPREL  vaddr = 0x{jmprel_vaddr:X}, size = 0x{jmprel_size:X}" if jmprel_vaddr else "  JMPREL not found")
    print(f"  RELA    vaddr = 0x{rela_vaddr:X}, size = 0x{relasz:X}" if rela_vaddr else "  RELA not found")
    print(f"  SYMENT  = {sym_ent}")
    
    if not (strtab_vaddr and symtab_vaddr and jmprel_vaddr and jmprel_size):
        print("\nCannot resolve PLT - missing DT entries")
        # Try alternative: maybe DT 0x61000017 is the JMPREL
        if 0x61000017 in info:
            print(f"  DT 0x61000017 = 0x{info[0x61000017]:X} (likely DT_SCE_JMPREL)")
        if 0x61000019 in info:
            print(f"  DT 0x61000019 = 0x{info[0x61000019]:X}")
        return 1
    
    # Get file offsets
    strtab_off = img.vaddr_to_offset(strtab_vaddr)
    symtab_off = img.vaddr_to_offset(symtab_vaddr)
    jmprel_off = img.vaddr_to_offset(jmprel_vaddr)
    print(f"\n  STRTAB file off = 0x{strtab_off:X}" if strtab_off else "  STRTAB not mappable")
    print(f"  SYMTAB file off = 0x{symtab_off:X}" if symtab_off else "  SYMTAB not mappable")
    print(f"  JMPREL file off = 0x{jmprel_off:X}" if jmprel_off else "  JMPREL not mappable")
    
    if not (strtab_off and symtab_off and jmprel_off):
        return 1
    
    # Parse .rela.plt entries (24 bytes: r_offset, r_info, r_addend)
    sym_to_name = {}
    n_entries = jmprel_size // 24
    print(f"\n  JMPREL entries: {n_entries}")
    for i in range(n_entries):
        off = jmprel_off + i * 24
        if off + 24 > len(img.raw):
            break
        r_offset, r_info, r_addend = struct.unpack_from('<QQq', img.raw, off)
        sym_idx = r_info >> 32
        rel_type = r_info & 0xFFFFFFFF
        # Read symbol
        sym_off = symtab_off + sym_idx * sym_ent
        if sym_off + 24 > len(img.raw):
            sym_to_name[r_offset] = f'<sym{sym_idx}?'
            continue
        st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack_from('<IBBHQQ', img.raw, sym_off)
        sym_name = find_string(img, strtab_vaddr, st_name) or f'<sym{sym_idx}>'
        sym_to_name[r_offset] = sym_name
    
    print(f"\n  Total resolved: {len(sym_to_name)}")
    
    # Now check our specific GOT slots
    targets = [0x801D1AD80, 0x801D1AE50, 0x801D1AE58, 0x801D1AE60, 0x801D1AE68, 0x801D1AE70]
    print("\n=== Specific GOT slots ===")
    for got_addr in targets:
        sym = sym_to_name.get(got_addr, '<UNRESOLVED>')
        print(f"  GOT 0x{got_addr:X} → '{sym}'")
    
    # Filter for interesting symbols
    print("\n=== Semaphore-related PLT entries ===")
    for got, name in sorted(sym_to_name.items()):
        if any(k in name.lower() for k in ['sema', 'signal', 'wait', 'baselib', 'lock', 'mutex', 'sync', 'wake', 'notif']):
            print(f"  GOT 0x{got:X} → '{name}'")
    
    # Save full mapping
    with open('/tmp/exp079_plt_map.txt', 'w') as f:
        for got, name in sorted(sym_to_name.items()):
            f.write(f"0x{got:X}\t{name}\n")
    print(f"\n  Full map written to /tmp/exp079_plt_map.txt")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
