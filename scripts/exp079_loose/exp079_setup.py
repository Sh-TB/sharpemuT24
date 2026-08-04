#!/usr/bin/env python3
"""EXP-079: Setup — Load eboot and PRX, prepare analysis tools."""
import sys, os, struct
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PRX_PATH = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"

def load_elf_sections(path):
    """Load ELF sections and segments. Returns (sections, segments, raw_bytes)."""
    with open(path, 'rb') as f:
        raw = f.read()
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        sections = []
        for s in elf.iter_sections():
            sections.append({
                'name': s.name,
                'sh_addr': s['sh_addr'],
                'sh_offset': s['sh_offset'],
                'sh_size': s['sh_size'],
                'sh_type': s['sh_type'],
                'sh_flags': s['sh_flags'],
            })
        segments = []
        for seg in elf.iter_segments():
            segments.append({
                'p_type': seg['p_type'],
                'p_vaddr': seg['p_vaddr'],
                'p_offset': seg['p_offset'],
                'p_filesz': seg['p_filesz'],
                'p_memsz': seg['p_memsz'],
                'p_flags': seg['p_flags'],
            })
        entry = elf.header.e_entry
    return sections, segments, raw, entry

def vaddr_to_offset(vaddr, segments):
    """Convert virtual address to file offset."""
    for seg in segments:
        if seg['p_type'] == 'PT_LOAD':
            if seg['p_vaddr'] <= vaddr < seg['p_vaddr'] + seg['p_filesz']:
                return seg['p_offset'] + (vaddr - seg['p_vaddr'])
    return None

def main():
    print(f"=== EBOOT ===")
    eboot_sections, eboot_segments, eboot_raw, eboot_entry = load_elf_sections(EBOOT_PATH)
    print(f"  size: {len(eboot_raw)} bytes")
    print(f"  entry: 0x{eboot_entry:X}")
    print(f"  segments ({len(eboot_segments)}):")
    for s in eboot_segments:
        print(f"    {s['p_type']:16s} vaddr=0x{s['p_vaddr']:X} off=0x{s['p_offset']:X} filesz=0x{s['p_filesz']:X} memsz=0x{s['p_memsz']:X}")
    print(f"  sections ({len(eboot_sections)}):")
    for s in eboot_sections[:30]:
        if s['sh_size'] > 0:
            print(f"    {s['name']:24s} addr=0x{s['sh_addr']:X} off=0x{s['sh_offset']:X} size=0x{s['sh_size']:X}")
    
    # Map the CLEAR address 0x800A9F750 to file offset
    target = 0x800A9F750
    off = vaddr_to_offset(target, eboot_segments)
    print(f"\n  vaddr 0x{target:X} → file offset {('0x%X' % off) if off else 'NONE'}")
    
    # Map the gate address 0x800AA0207
    target2 = 0x800AA0207
    off2 = vaddr_to_offset(target2, eboot_segments)
    print(f"  vaddr 0x{target2:X} → file offset {('0x%X' % off2) if off2 else 'NONE'}")
    
    print(f"\n=== PRX (Il2cppUserAssemblies) ===")
    prx_sections, prx_segments, prx_raw, prx_entry = load_elf_sections(PRX_PATH)
    print(f"  size: {len(prx_raw)} bytes")
    print(f"  entry: 0x{prx_entry:X}")
    print(f"  segments ({len(prx_segments)}):")
    for s in prx_segments:
        print(f"    {s['p_type']:16s} vaddr=0x{s['p_vaddr']:X} off=0x{s['p_offset']:X} filesz=0x{s['p_filesz']:X} memsz=0x{s['p_memsz']:X}")
    print(f"  sections ({len(prx_sections)}):")
    for s in prx_sections[:30]:
        if s['sh_size'] > 0:
            print(f"    {s['name']:24s} addr=0x{s['sh_addr']:X} off=0x{s['sh_offset']:X} size=0x{s['sh_size']:X}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
