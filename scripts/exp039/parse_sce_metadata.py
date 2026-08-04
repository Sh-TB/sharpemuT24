#!/usr/bin/env python3
"""EXP-039 Task 1+2: Parse PT_SCE_DYNAMIC ORBI + Sony module metadata.

Fully parse the PT_SCE_DYNAMIC segment for eboot.bin and all PRXs.
Also dump DT_SCE_MODULE_INFO, DT_SCE_MODULE_PARAM, DT_SCE_PROC_PARAM.

The goal is to find the real DT_INIT callback address.
"""
import struct
from pathlib import Path

BASE = Path("/tmp/games/yatzi")
files = [
    (BASE / "eboot.bin", "eboot.bin", 0x800000000),
    (BASE / "Media/Modules/Il2cppUserAssemblies.prx", "Il2cppUserAssemblies.prx", 0x804CD5000),
    (BASE / "sce_module/libc.prx", "libc.prx", 0x804000000),
]

for path, label, image_base in files:
    if not path.exists():
        continue
    data = path.read_bytes()
    print(f"\n{'='*70}")
    print(f"=== {label} (base 0x{image_base:X}) ===")
    print(f"{'='*70}")

    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_entry = struct.unpack_from('<Q', data, 24)[0]

    print(f"e_entry = 0x{e_entry:X} (runtime: 0x{image_base + e_entry:X})")

    # Find PT_SCE_DYNAMIC and other PT_SCE_* segments
    segs = {}
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_flags = struct.unpack_from('<I', data, off + 4)[0]
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        p_memsz = struct.unpack_from('<Q', data, off + 40)[0]
        segs[p_type] = (p_offset, p_vaddr, p_filesz, p_memsz, p_flags, i)

    # PT_SCE_DYNAMIC = 0x61000001
    sce_dyn = segs.get(0x61000001)
    if sce_dyn:
        p_off, p_vaddr, p_filesz, p_memsz, p_flags, idx = sce_dyn
        print(f"\n--- PT_SCE_DYNAMIC (PH[{idx}]) ---")
        print(f"  vaddr=0x{p_vaddr:X} filesz=0x{p_filesz:X} memsz=0x{p_memsz:X}")
        chunk = data[p_off:p_off + p_filesz]
        print(f"  Raw ({len(chunk)} bytes):")
        for j in range(0, len(chunk), 16):
            hex_part = " ".join(f"{b:02X}" for b in chunk[j:j+16])
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk[j:j+16])
            print(f"    +0x{j:02X}: {hex_part:<48} |{ascii_part}|")

        # Parse as sce_dynamic_info
        # The structure has a 4-byte magic "ORBI" and version
        # Let me try parsing it as the OrbisDynamicInfo structure
        print(f"\n  Parsed fields:")
        if len(chunk) >= 8:
            # Try different field layouts
            # Layout 1: 8-byte fields
            print(f"    [0x00] size/flags: 0x{struct.unpack_from('<Q', chunk, 0)[0]:X}")
            print(f"    [0x08] magic/version: 0x{struct.unpack_from('<Q', chunk, 8)[0]:X}")
            # The "ORBI" is at offset 8-11, version at 12-15
            magic = chunk[8:12]
            version = struct.unpack_from('<I', chunk, 12)[0]
            print(f"    magic={magic} version={version}")
            # After magic+version, there may be more fields
            for k in range(16, min(len(chunk), 96), 8):
                val = struct.unpack_from('<Q', chunk, k)[0]
                if val != 0:
                    print(f"    [0x{k:02X}] = 0x{val:X}")
    else:
        print(f"\n  No PT_SCE_DYNAMIC segment")

    # Parse dynamic section for SCE-specific entries
    dyn = segs.get(2)  # PT_DYNAMIC
    if dyn:
        p_off, p_vaddr, p_filesz, p_memsz, _, _ = dyn
        print(f"\n--- PT_DYNAMIC (offset 0x{p_off:X}) --- SCE entries:")
        i = 0
        while i < p_memsz:
            d_tag, d_val = struct.unpack_from('<qQ', data, p_off + i)
            if d_tag == 0:
                break
            # SCE tags of interest
            if 0x61000000 <= d_tag <= 0x61000050 or d_tag in (0x6FFFFEF5, 0x6FFFFD00, 0x6FFFFFF0):
                tag_names = {
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
                }
                name = tag_names.get(d_tag, f"DT_SCE_0x{d_tag:X}")
                print(f"    {name} = 0x{d_val:X}")
            i += 16

    # Check DT_SCE_MODULE_INFO — this contains the module name and entry
    # DT_SCE_MODULE_INFO = 0x61000002
    # The value is an offset into the string table
    # Let me also check DT_SCE_PROC_PARAM and DT_SCE_MODULE_PARAM
    # PT_SCE_PROCPARAM = 0x61000003
    # PT_SCE_MODULEPARAM = 0x61000004
    for pt_name, pt_type in [("PT_SCE_PROCPARAM", 0x61000003),
                               ("PT_SCE_MODULEPARAM", 0x61000004)]:
        seg = segs.get(pt_type)
        if seg:
            p_off, p_vaddr, p_filesz, p_memsz, _, idx = seg
            print(f"\n--- {pt_name} (PH[{idx}]) ---")
            print(f"  vaddr=0x{p_vaddr:X} filesz=0x{p_filesz:X}")
            chunk = data[p_off:p_off + min(p_filesz, 128)]
            for j in range(0, len(chunk), 16):
                hex_part = " ".join(f"{b:02X}" for b in chunk[j:j+16])
                print(f"    +0x{j:02X}: {hex_part}")
            # Try to parse as sce_module_param
            if len(chunk) >= 48:
                m_size = struct.unpack_from('<Q', chunk, 0)[0]
                ent_top = struct.unpack_from('<Q', chunk, 8)[0]
                ent_end = struct.unpack_from('<Q', chunk, 16)[0]
                stub_top = struct.unpack_from('<Q', chunk, 24)[0]
                stub_end = struct.unpack_from('<Q', chunk, 32)[0]
                print(f"    size=0x{m_size:X} ent=[0x{ent_top:X}..0x{ent_end:X}] stub=[0x{stub_top:X}..0x{stub_end:X}]")
