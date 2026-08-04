#!/usr/bin/env python3
"""EXP-038 Task 2: Full ELF analysis of eboot.bin, Il2cppUserAssemblies.prx, libc.prx.

Dumps:
- All program headers (including PS5-specific PT_SCE_*)
- All dynamic section entries
- Sony-specific segments (.sce_process_param, .sce_module_info, etc.)
- Init/fini arrays and their actual contents
"""
import struct
from pathlib import Path

# PS5/Sony program header types
PT_SCE_NAMES = {
    0x61000001: "PT_SCE_DYNAMIC",        # Sony dynamic info
    0x61000002: "PT_SCE_DYNLIBDATA",     # Sony dynamic library data
    0x61000003: "PT_SCE_PROCPARAM",      # Sony process parameter
    0x61000004: "PT_SCE_MODULEPARAM",    # Sony module parameter
    0x61000005: "PT_SCE_RELRO",          # Sony relro
    0x61000006: "PT_SCE_COMMENT",        # Sony comment
    0x61000007: "PT_SCE_LIBVERSION",     # Sony library version
    0x61000008: "PT_SCE_SSP",            # Sony stack smash protection
}

# Standard program header types
PT_NAMES = {
    0: "PT_NULL", 1: "PT_LOAD", 2: "PT_DYNAMIC", 3: "PT_INTERP",
    4: "PT_NOTE", 5: "PT_SHLIB", 6: "PT_PHDR", 7: "PT_TLS",
    0x6474e550: "PT_GNU_EH_FRAME", 0x6474e551: "PT_GNU_STACK",
    0x6474e552: "PT_GNU_RELRO", 0x6474e553: "PT_GNU_PROPERTY",
}

# Dynamic entry tags
DT_NAMES = {
    0: "DT_NULL", 1: "DT_NEEDED", 2: "DT_PLTRELSZ", 3: "DT_PLTGOT",
    4: "DT_HASH", 5: "DT_STRTAB", 6: "DT_SYMTAB", 7: "DT_RELA",
    8: "DT_RELASZ", 9: "DT_RELAENT", 10: "DT_STRSZ", 11: "DT_SYMENT",
    12: "DT_INIT", 13: "DT_FINI", 14: "DT_SONAME", 15: "DT_RPATH",
    16: "DT_SYMBOLIC", 17: "DT_REL", 18: "DT_RELSZ", 19: "DT_RELENT",
    20: "DT_PLTREL", 21: "DT_DEBUG", 22: "DT_TEXTREL", 23: "DT_JMPREL",
    24: "DT_BIND_NOW", 25: "DT_INIT_ARRAY", 26: "DT_FINI_ARRAY",
    27: "DT_INIT_ARRAYSZ", 28: "DT_FINI_ARRAYSZ", 29: "DT_RUNPATH",
    30: "DT_FLAGS", 32: "DT_SYMTAB_SHNDX",
    # PS5/Sony specific
    0x61000001: "DT_SCE_FINGERPRINT",
    0x61000002: "DT_SCE_MODULE_INFO",
    0x61000003: "DT_SCE_NEEDED_MODULE",
    0x61000004: "DT_SCE_MODULE_ATTR",
    0x61000005: "DT_SCE_EXPORT_LIB",
    0x61000006: "DT_SCE_IMPORT_LIB",
    0x61000007: "DT_SCE_EXPORT_LIB_ATTR",
    0x61000008: "DT_SCE_IMPORT_LIB_ATTR",
    0x61000009: "DT_SCE_DYNAMIC_PROCESS",
    0x6100000a: "DT_SCE_ORIGINAL_FILENAME",
    0x6100000e: "DT_SCE_THREAD_LOCAL",
    0x6100000f: "DT_SCE_THREAD_LOCAL_SIZE",
    0x61000010: "DT_SCE_INIT_ARRAY",
    0x61000011: "DT_SCE_INIT_ARRAY_SIZE",
    0x61000012: "DT_SCE_FINI_ARRAY",
    0x61000013: "DT_SCE_FINI_ARRAY_SIZE",
    0x61000014: "DT_SCE_HASH",
    0x61000015: "DT_SCE_PLTGOT",
    0x61000016: "DT_SCE_STRTAB",
    0x61000017: "DT_SCE_STRSZ",
    0x61000018: "DT_SCE_SYMTAB",
    0x61000019: "DT_SCE_SYMTABSZ",
    0x6100001a: "DT_SCE_SYMENT",
    0x6100001b: "DT_SCE_RELA",
    0x6100001c: "DT_SCE_RELASZ",
    0x6100001d: "DT_SCE_RELAENT",
    0x6100001e: "DT_SCE_JMPREL",
    0x6100001f: "DT_SCE_PLTRELSZ",
    0x61000020: "DT_SCE_PLTREL",
    0x61000021: "DT_SCE_PLTGOT",
    0x61000022: "DT_SCE_SDT",
    0x61000035: "DT_SCE_STRTAB_2",
    0x61000037: "DT_SCE_STRSZ_2",
    0x61000039: "DT_SCE_SYMTAB_2",
    0x6100003b: "DT_SCE_SYMTABSZ_2",
    0x6100003c: "DT_SCE_SYMENT_2",
    0x6100003f: "DT_SCE_RELA_2",
    0x61000040: "DT_SCE_RELASZ_2",
    0x61000041: "DT_SCE_RELAENT_2",
    0x61000043: "DT_SCE_JMPREL_2",
    0x61000044: "DT_SCE_PLTRELSZ_2",
    0x61000045: "DT_SCE_PLTREL_2",
    0x61000047: "DT_SCE_PLTGOT_2",
    0x61000049: "DT_SCE_JMPREL_3",
    0x6100004e: "DT_SCE_HASH_2",
    0x6ffffd00: "DT_SCE_GNU_HASH",
    0x6ffffef5: "DT_SCE_DEBUG",
    0x6ffffff0: "DT_SCE_FLAGS_1",
    0x6ffffff9: "DT_SCE_RELACOUNT",
}


def analyze_elf(path, label):
    data = path.read_bytes()
    print(f"\n{'='*70}")
    print(f"=== {label}: {path.name} ({len(data)} bytes) ===")
    print(f"{'='*70}")

    if data[:4] != b'\x7fELF':
        print("  NOT an ELF file!")
        return

    ei_class = data[4]  # 1=32bit, 2=64bit
    e_type = struct.unpack_from('<H', data, 16)[0]
    e_machine = struct.unpack_from('<H', data, 18)[0]
    e_entry = struct.unpack_from('<Q', data, 24)[0]
    e_phoff = struct.unpack_from('<Q', data, 32)[0]
    e_shoff = struct.unpack_from('<Q', data, 40)[0]
    e_phentsize = struct.unpack_from('<H', data, 54)[0]
    e_phnum = struct.unpack_from('<H', data, 56)[0]
    e_shentsize = struct.unpack_from('<H', data, 58)[0]
    e_shnum = struct.unpack_from('<H', data, 60)[0]
    e_shstrndx = struct.unpack_from('<H', data, 62)[0]

    type_names = {1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}
    print(f"  ELF class: {'64-bit' if ei_class==2 else '32-bit'}")
    print(f"  e_type: {e_type} ({type_names.get(e_type, '?')})")
    print(f"  e_machine: {e_machine} ({'x86-64' if e_machine==62 else '?'})")
    print(f"  e_entry: 0x{e_entry:X}")
    print(f"  e_phoff: 0x{e_phoff:X}, e_phnum: {e_phnum}, e_phentsize: {e_phentsize}")
    print(f"  e_shoff: 0x{e_shoff:X}, e_shnum: {e_shnum}, e_shentsize: {e_shentsize}")

    # Parse program headers
    print(f"\n  --- Program Headers ---")
    dyn_phdr = None
    procparam_phdr = None
    moduleparam_phdr = None
    load_segments = []

    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_flags = struct.unpack_from('<I', data, off + 4)[0]
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_paddr = struct.unpack_from('<Q', data, off + 24)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        p_memsz = struct.unpack_from('<Q', data, off + 40)[0]
        p_align = struct.unpack_from('<Q', data, off + 48)[0]

        pt_name = PT_NAMES.get(p_type, PT_SCE_NAMES.get(p_type, f"UNKNOWN(0x{p_type:X})"))
        flag_str = ""
        if p_flags & 4: flag_str += "R"
        if p_flags & 2: flag_str += "W"
        if p_flags & 1: flag_str += "X"
        print(f"    PH[{i:2d}]: {pt_name:<28} off=0x{p_offset:08X} vaddr=0x{p_vaddr:012X} "
              f"filesz=0x{p_filesz:X} memsz=0x{p_memsz:X} flags={flag_str}")

        if p_type == 2:  # PT_DYNAMIC
            dyn_phdr = (p_offset, p_filesz, p_vaddr)
        elif p_type == 0x61000003:  # PT_SCE_PROCPARAM
            procparam_phdr = (p_offset, p_filesz, p_vaddr)
        elif p_type == 0x61000004:  # PT_SCE_MODULEPARAM
            moduleparam_phdr = (p_offset, p_filesz, p_vaddr)
        elif p_type == 1:  # PT_LOAD
            load_segments.append((p_offset, p_vaddr, p_filesz, p_memsz, p_flags))

    # Parse dynamic section
    if dyn_phdr:
        dyn_off, dyn_size, dyn_vaddr = dyn_phdr
        print(f"\n  --- Dynamic Section (offset=0x{dyn_off:X}, size=0x{dyn_size:X}) ---")
        dt = {}
        i = 0
        while i < dyn_size:
            d_tag, d_val = struct.unpack_from('<qQ', data, dyn_off + i)
            if d_tag == 0:
                break
            dt[d_tag] = d_val
            name = DT_NAMES.get(d_tag, f"UNKNOWN(0x{d_tag:X})")
            print(f"    {name:<36} = 0x{d_val:X}")
            i += 16

        # Check init_array entries
        print(f"\n  --- Init Array Analysis ---")

        # Standard DT_INIT_ARRAY
        ia_addr = dt.get(25, 0)
        ia_size = dt.get(27, 0)
        print(f"    DT_INIT_ARRAY = 0x{ia_addr:X}, size = 0x{ia_size:X}")

        # SCE DT_SCE_INIT_ARRAY
        sce_ia = dt.get(0x61000010, 0)
        sce_ia_size = dt.get(0x61000011, 0)
        print(f"    DT_SCE_INIT_ARRAY = 0x{sce_ia:X}, size = 0x{sce_ia_size:X}")

        # DT_INIT
        init_addr = dt.get(12, 0)
        print(f"    DT_INIT = 0x{init_addr:X}")

        # Try to read init_array contents if it exists
        for label, addr, size in [("DT_INIT_ARRAY", ia_addr, ia_size),
                                     ("DT_SCE_INIT_ARRAY", sce_ia, sce_ia_size)]:
            if addr == 0 or size == 0:
                print(f"    {label}: EMPTY")
                continue
            # Find which LOAD segment contains this vaddr
            for p_off, p_vaddr, p_filesz, p_memsz, p_flags in load_segments:
                if p_vaddr <= addr < p_vaddr + p_memsz:
                    file_off = p_off + (addr - p_vaddr)
                    num_entries = size // 8
                    print(f"    {label}: {num_entries} entries (file offset 0x{file_off:X}):")
                    for j in range(min(num_entries, 20)):
                        if file_off + j * 8 + 8 <= len(data):
                            val = struct.unpack_from('<Q', data, file_off + j * 8)[0]
                            print(f"      [{j}] 0x{val:X}")
                    break

    # Check PT_SCE_PROCPARAM and PT_SCE_MODULEPARAM
    for label, phdr in [("PT_SCE_PROCPARAM", procparam_phdr),
                          ("PT_SCE_MODULEPARAM", moduleparam_phdr)]:
        if phdr:
            p_off, p_filesz, p_vaddr = phdr
            print(f"\n  --- {label} (offset=0x{p_off:X}, size=0x{p_filesz:X}, vaddr=0x{p_vaddr:X}) ---")
            # Dump first 128 bytes
            chunk = data[p_off:p_off + min(128, p_filesz)]
            for i in range(0, len(chunk), 16):
                hex_part = " ".join(f"{b:02X}" for b in chunk[i:i+16])
                print(f"    +0x{i:02X}: {hex_part}")
            # Try to interpret as sce_module_param structure
            # The sce_module_param has: size, ent_top, ent_end, stub_top, stub_end, ...
            if p_filesz >= 48:
                m_size = struct.unpack_from('<Q', data, p_off)[0]
                ent_top = struct.unpack_from('<Q', data, p_off + 8)[0]
                ent_end = struct.unpack_from('<Q', data, p_off + 16)[0]
                stub_top = struct.unpack_from('<Q', data, p_off + 24)[0]
                stub_end = struct.unpack_from('<Q', data, p_off + 32)[0]
                print(f"    Parsed: size=0x{m_size:X}, ent=[0x{ent_top:X}..0x{ent_end:X}], stub=[0x{stub_top:X}..0x{stub_end:X}]")


def main():
    base = Path("/tmp/games/yatzi")
    files = [
        (base / "eboot.bin", "eboot.bin (main executable)"),
        (base / "Media/Modules/Il2cppUserAssemblies.prx", "Il2cppUserAssemblies.prx"),
        (base / "sce_module/libc.prx", "libc.prx"),
    ]
    for path, label in files:
        if path.exists():
            analyze_elf(path, label)
        else:
            print(f"\n=== {label}: NOT FOUND at {path} ===")


if __name__ == "__main__":
    main()
