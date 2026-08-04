#!/usr/bin/env python3
"""EXP-079: Parse Orbis-style PLT and match GOT slots to NIDs."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

# Sony Orbis DT tags (PS5)
DT_SCE_NEEDED = 0x61000007
DT_SCE_EXPORT = 0x61000009
DT_SCE_ORIGINAL_FILENAME = 0x6100000F
DT_SCE_MODULE_INFO = 0x61000011
DT_SCE_PLTREL = 0x61000014  
DT_SCE_RELA = 0x61000015
DT_SCE_RELASZ = 0x61000016
DT_SCE_RELAENT = 0x61000017
DT_SCE_JMPREL = 0x61000018
DT_SCE_PLTRELSZ = 0x61000019
DT_SCE_STRTAB = 0x6100001C
DT_SCE_STRSZ = 0x6100001D
DT_SCE_SYMTAB = 0x6100001E
DT_SCE_SYMENT = 0x6100001F

# Standard tags
DT_NEEDED=1; DT_PLTRELSZ=2; DT_PLTGOT=3; DT_STRTAB=5; DT_SYMTAB=6; DT_RELA=7;
DT_RELASZ=8; DT_RELAENT=9; DT_STRSZ=10; DT_SYMENT=11; DT_JMPREL=23; DT_PLTREL=20
DT_SONAME=14

# Orbis module export entry (16 bytes)
# struct { uint64_t fnid_or_nid; void* symbol_addr_or_got_slot_addr; }

def parse_orbis_dynamic(img):
    """Parse Orbis-style dynamic table."""
    dyn_seg = None
    for s in img.segments:
        if s['p_type'] == 2:  # PT_DYNAMIC
            dyn_seg = s
            break
    if dyn_seg is None:
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

def find_string(img, strtab_vaddr, str_offset):
    strtab_off = img.vaddr_to_offset(strtab_vaddr)
    if strtab_off is None:
        return None
    file_off = strtab_off + str_offset
    if file_off >= len(img.raw):
        return None
    end = img.raw.find(b'\x00', file_off)
    if end < 0:
        return None
    return img.raw[file_off:end].decode('utf-8', errors='replace')

def main():
    img = ElfImage(EBOOT_PATH)
    dyn = parse_orbis_dynamic(img)
    
    # Group by tag value (just count occurrences of each tag)
    tag_counts = {}
    info = {}
    for tag, val in dyn:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        # Save the last non-NEEDED value per tag
        if tag not in (DT_NEEDED, 0x61000001, 0x61000007):  # DT_NEEDED variants
            info[tag] = val
    
    print("=== Dynamic tag counts ===")
    for tag in sorted(tag_counts.keys()):
        print(f"  0x{tag & 0xFFFFFFFFFFFFFFFF:X} ({tag}): {tag_counts[tag]}")
    
    # Find JMPREL (0x61000019 seems to map to PLTRELSZ based on size pattern)
    # Looking at the data: 0x61000019 entries have small values (9 bytes each)
    # This suggests it's the PLTRELSZ per-library or per-module.
    
    # Let's look for the actual .rela.plt section by examining known PLT thunks
    # PLT0 is at 0x801936650 (from our disassembly). Let's disassemble it.
    print("\n=== PLT0 (resolver) at 0x801936650 ===")
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    vaddr = 0x801936650 - PS5_BASE
    data = img.read_bytes(vaddr, 128)
    if data:
        for ins in list(md.disasm(data, 0x801936650))[:20]:
            print(f"  0x{ins.address:X}:  {ins.bytes.hex():20s}  {ins.mnemonic:8s} {ins.op_str}")
    
    # Look at PLT thunk pattern at 0x8019377d0 more carefully
    print("\n=== PLT thunk detail at 0x8019377d0 ===")
    vaddr = 0x8019377D0 - PS5_BASE
    data = img.read_bytes(vaddr, 32)
    if data:
        for ins in list(md.disasm(data, 0x8019377D0))[:5]:
            print(f"  0x{ins.address:X}:  {ins.bytes.hex():20s}  {ins.mnemonic:8s} {ins.op_str}")
    
    # The GOT slot 0x801D1AE60 should hold the resolved function address at runtime.
    # But before resolution, it points back to the push instruction.
    # Check what's stored at the GOT slot in the FILE.
    print("\n=== Initial GOT slot values (before runtime resolution) ===")
    for got_addr in [0x801D1AD80, 0x801D1AE50, 0x801D1AE60, 0x801D1AE68]:
        off = img.vaddr_to_offset(got_addr)
        if off:
            val = struct.unpack_from('<Q', img.raw, off)[0] if off + 8 <= len(img.raw) else 0
            print(f"  GOT 0x{got_addr:X} (file off 0x{off:X}) = 0x{val:X}")
    
    # Now scan all PLT thunks between 0x801937600 and 0x801937900 to find all semaphore-related ones
    print("\n=== Scanning PLT region 0x801937600..0x801937A00 ===")
    plt_start = 0x801937600
    plt_end = 0x801937A00
    vaddr = plt_start - PS5_BASE
    data = img.read_bytes(vaddr, plt_end - plt_start)
    if data:
        for ins in md.disasm(data, plt_start):
            if ins.mnemonic == 'jmp' and 'rip' in ins.op_str:
                # Parse: jmp qword ptr [rip + X] → target = ins.address + ins.size + X
                for op in ins.operands:
                    if op.type == 2 and op.mem.base == 41:  # X86_OP_MEM, X86_REG_RIP
                        target = ins.address + ins.size + op.mem.disp
                        print(f"  PLT 0x{ins.address:X}: jmp [0x{target:X}] (GOT slot)")
                        break
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
