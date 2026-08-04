#!/usr/bin/env python3
"""Read ELF program headers to find the file offset for 0x800AA01D4."""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
data = EBOOT.read_bytes()

# ELF64 header
# e_ident[16], e_type(2), e_machine(2), e_version(4), e_entry(8),
# e_phoff(8), e_shoff(8), e_flags(4), e_ehsize(2), e_phentsize(2),
# e_phnum(2), e_shentsize(2), e_shnum(2), e_shstrndx(2)
e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
e_phnum = struct.unpack_from("<H", data, 0x38)[0]

print(f"ELF: e_phoff=0x{e_phoff:X} e_phentsize={e_phentsize} e_phnum={e_phnum}")
print()

# ELF64 Phdr:
# p_type(4), p_flags(4), p_offset(8), p_vaddr(8), p_paddr(8),
# p_filesz(8), p_memsz(8), p_align(8)
TARGET_VADDR = 0x800AA01D4
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
        struct.unpack_from("<IIQQQQQQ", data, off)
    type_str = {1: "LOAD", 2: "DYNAMIC", 6: "PHDR", 7: "TLS",
                0x6474e550: "GNU_EH_FRAME", 0x6474e551: "GNU_STACK",
                0x6474e552: "GNU_RELRO", 4: "NOTE"}.get(p_type, f"0x{p_type:X}")
    mapped_end = p_vaddr + p_memsz
    print(f"  PH[{i}]: type={type_str:<14} offset=0x{p_offset:08X} "
          f"vaddr=0x{p_vaddr:012X}..0x{mapped_end:012X} "
          f"filesz=0x{p_filesz:X} memsz=0x{p_memsz:X}")
    # Check if target vaddr falls in this segment (when mapped to 0x800000000 base)
    mapped_vaddr = p_vaddr + 0x800000000 if p_vaddr < 0x800000000 else p_vaddr
    if mapped_vaddr <= TARGET_VADDR < mapped_vaddr + p_memsz:
        file_off = p_offset + (TARGET_VADDR - mapped_vaddr)
        print(f"    *** TARGET 0x{TARGET_VADDR:X} is in this segment ***")
        print(f"    *** File offset = 0x{file_off:X} ***")
