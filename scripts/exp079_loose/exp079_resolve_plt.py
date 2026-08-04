#!/usr/bin/env python3
"""EXP-079: Resolve PLT/GOT entries to symbol names."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

# PT_DYNAMIC = 2
# DT_NULL=0, DT_NEEDED=1, DT_PLTRELSZ=2, DT_PLTGOT=3, DT_HASH=4, DT_STRTAB=5, DT_SYMTAB=6, DT_RELA=7,
# DT_RELASZ=8, DT_RELAENT=9, DT_STRSZ=10, DT_SYMENT=11, DT_INIT=12, DT_FINI=13, DT_SONAME=14,
# DT_RPATH=15, DT_SYMBOLIC=16, DT_REL=17, DT_RELSZ=18, DT_RELENT=19, DT_PLTREL=20, DT_DEBUG=21,
# DT_TEXTREL=22, DT_JMPREL=23, DT_BIND_NOW=24, DT_INIT_ARRAY=25, DT_FINI_ARRAY=26, DT_FLAGS=30

def parse_dynamic(img):
    """Find PT_DYNAMIC segment and parse it."""
    dyn_seg = None
    for s in img.segments:
        if s['p_type'] == 2:  # PT_DYNAMIC
            dyn_seg = s
            break
    if dyn_seg is None:
        print("  No PT_DYNAMIC segment")
        return None
    dyn_raw = img.raw[dyn_seg['p_offset']:dyn_seg['p_offset'] + dyn_seg['p_filesz']]
    entries = []
    for i in range(0, len(dyn_raw), 16):
        if i + 16 > len(dyn_raw):
            break
        d_tag, d_val = struct.unpack_from('<qQ', dyn_raw, i)
        entries.append((d_tag, d_val))
        if d_tag == 0:
            break
    return entries

def find_string(img, strtab_offset, str_offset):
    """Read a null-terminated string from strtab."""
    file_off = strtab_offset + str_offset
    if file_off >= len(img.raw):
        return None
    end = img.raw.find(b'\x00', file_off)
    if end < 0:
        return None
    return img.raw[file_off:end].decode('utf-8', errors='replace')

def resolve_plt_symbols(img):
    """Resolve PLT thunks to symbol names using JMPREL relocations."""
    dyn = parse_dynamic(img)
    if dyn is None:
        return {}
    
    dt_names = {
        0:'NULL', 1:'NEEDED', 2:'PLTRELSZ', 3:'PLTGOT', 4:'HASH', 5:'STRTAB',
        6:'SYMTAB', 7:'RELA', 8:'RELASZ', 9:'RELAENT', 10:'STRSZ', 11:'SYMENT',
        12:'INIT', 13:'FINI', 14:'SONAME', 15:'RPATH', 16:'SYMBOLIC', 17:'REL',
        18:'RELSZ', 19:'RELENT', 20:'PLTREL', 21:'DEBUG', 22:'TEXTREL', 23:'JMPREL',
        24:'BIND_NOW', 25:'INIT_ARRAY', 26:'FINI_ARRAY', 27:'INIT_ARRAYSZ', 28:'FINI_ARRAYSZ',
        29:'RUNPATH', 30:'FLAGS', 0x6FFFFEF5:'GNU_HASH', 0x6FFFFFF0:'VERSYM', 0x6FFFFFFC:'VERDEF',
        0x6FFFFFFD:'VERDEFNUM', 0x6FFFFFFE:'VERNEED', 0x6FFFFFFF:'VERNEEDNUM',
    }
    
    info = {}
    for tag, val in dyn:
        name = dt_names.get(tag, f'0x{tag:X}')
        if name in ('NULL','NEEDED'):
            print(f"  DT_{name:12s} = 0x{val:X}")
        else:
            info[name] = val
            print(f"  DT_{name:12s} = 0x{val:X}")
    
    # We need STRTAB, SYMTAB, JMPREL, PLTRELSZ, SYMENT
    if 'STRTAB' not in info or 'SYMTAB' not in info or 'JMPREL' not in info:
        print("  Missing required DT entries")
        return {}
    
    strtab_vaddr = info['STRTAB']
    symtab_vaddr = info['SYMTAB']
    jmprel_vaddr = info['JMPREL']
    jmprel_size = info.get('PLTRELSZ', 0)
    syment = info.get('SYMENT', 24)
    
    print(f"\n  STRTAB vaddr=0x{strtab_vaddr:X}")
    print(f"  SYMTAB vaddr=0x{symtab_vaddr:X}")
    print(f"  JMPREL vaddr=0x{jmprel_vaddr:X} size=0x{jmprel_size:X}")
    
    # Convert vaddrs to file offsets
    strtab_off = img.vaddr_to_offset(strtab_vaddr)
    symtab_off = img.vaddr_to_offset(symtab_vaddr)
    jmprel_off = img.vaddr_to_offset(jmprel_vaddr)
    
    if not (strtab_off and symtab_off and jmprel_off):
        print(f"  Cannot map vaddrs to offsets: str={strtab_off}, sym={symtab_off}, jmp={jmprel_off}")
        return {}
    
    # Parse .rela.plt (RELA entries: 24 bytes each — r_offset, r_info, r_addend)
    # r_info: sym = r_info >> 32, type = r_info & 0xFFFFFFFF
    # For x86-64, R_X86_64_JUMP_SLOT = 7
    sym_to_name = {}
    for i in range(0, jmprel_size, 24):
        if i + 24 > jmprel_size:
            break
        r_offset, r_info, r_addend = struct.unpack_from('<QQq', img.raw, jmprel_off + i)
        sym_idx = r_info >> 32
        rel_type = r_info & 0xFFFFFFFF
        # Read symbol entry: st_name (4), st_info (1), st_other (1), st_shndx (2), st_value (8), st_size (8)
        sym_off = symtab_off + sym_idx * syment
        if sym_off + 24 > len(img.raw):
            continue
        st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack_from('<IBBHQQ', img.raw, sym_off)
        sym_name = find_string(img, strtab_off, st_name) or f'<sym{sym_idx}>'
        sym_to_name[r_offset] = sym_name
        # Only print first few / interesting ones
        if i < 24*5 or 'Sema' in sym_name or 'Signal' in sym_name or 'sema' in sym_name or 'Baselib' in sym_name:
            print(f"  PLT reloc: GOT@0x{r_offset:X} → sym#{sym_idx} '{sym_name}' (type={rel_type})")
    
    return sym_to_name

def main():
    img = ElfImage(EBOOT_PATH)
    print("=== Resolving PLT symbols in EBOOT ===")
    sym_map = resolve_plt_symbols(img)
    print(f"\nTotal PLT relocations: {len(sym_map)}")
    
    # Check our specific GOT slots
    targets = {
        0x801D1AD80: '0x801937610 (called on r12+0x30)',
        0x801D1AE50: '0x8019377b0 (signal with esi=1)',
        0x801D1AE60: '0x8019377d0 (signal with eax=count)',
        0x801D1AE58: '0x8019377c0',
        0x801D1AE68: '0x8019377e0',
    }
    print("\n=== Specific GOT slots ===")
    for got_addr, who in targets.items():
        sym = sym_map.get(got_addr, '<UNRESOLVED>')
        print(f"  GOT 0x{got_addr:X}  → '{sym}'   ({who})")
    
    # Search for any semaphore-related symbols
    print("\n=== Semaphore-related symbols ===")
    for got, name in sorted(sym_map.items()):
        if any(k in name.lower() for k in ['sema', 'signal', 'wait', 'baselib', 'lock', 'mutex']):
            print(f"  GOT 0x{got:X} → '{name}'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
