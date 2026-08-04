#!/usr/bin/env python3
"""EXP-079 TASK 2f: Find INIT_ARRAY entries pointing to 0x800A9F210."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def main():
    img = ElfImage(EBOOT_PATH)
    
    # Read dynamic info
    dyn_seg = None
    for s in img.segments:
        if s['p_type'] == 2:
            dyn_seg = s
            break
    dyn_raw = img.raw[dyn_seg['p_offset']:dyn_seg['p_offset'] + dyn_seg['p_filesz']]
    info = {}
    for i in range(0, len(dyn_raw), 16):
        if i + 16 > len(dyn_raw): break
        d_tag, d_val = struct.unpack_from('<qQ', dyn_raw, i)
        if d_tag == 0: break
        info[d_tag] = d_val
    
    print("All DT entries:")
    for k in sorted(info.keys()):
        print(f"  DT 0x{k:X} = 0x{info[k]:X}")
    
    # Standard + Orbis init_array tags
    candidates = [
        (25, 'DT_INIT_ARRAY'),
        (27, 'DT_INIT_ARRAYSZ'),
        (26, 'DT_FINI_ARRAY'),
        (28, 'DT_FINI_ARRAYSZ'),
        (0x61000025, 'DT_SCE_INIT_ARRAY'),
        (0x61000027, 'DT_SCE_INIT_ARRAYSZ'),
        (0x61000026, 'DT_SCE_FINI_ARRAY'),
        (0x61000028, 'DT_SCE_FINI_ARRAYSZ'),
        (12, 'DT_INIT'),
        (13, 'DT_FINI'),
    ]
    for tag, name in candidates:
        if tag in info:
            print(f"\n{name} (0x{tag:X}) = 0x{info[tag]:X}")
    
    # Try standard
    init_array_vaddr = info.get(25)
    init_arraysz = info.get(27)
    
    # If standard empty, try Orbis
    if not init_array_vaddr:
        init_array_vaddr = info.get(0x61000025)
        init_arraysz = info.get(0x61000027)
    
    if init_array_vaddr and init_arraysz:
        print(f"\n  Init array: vaddr=0x{init_array_vaddr:X} size=0x{init_arraysz:X} ({init_arraysz//8} entries)")
        ia_off = img.vaddr_to_offset(init_array_vaddr)
        if ia_off:
            for i in range(init_arraysz // 8):
                val = struct.unpack_from('<Q', img.raw, ia_off + i * 8)[0]
                runtime_addr = val + PS5_BASE if val < 0x10000000 else val
                print(f"    [{i}] = 0x{val:X} (runtime 0x{runtime_addr:X})")
    else:
        print("No init_array found")
    
    # The slot at 0x1D1C370 — check if it's in a reloc table that would be initialized at load time
    # The RELA entry we found was at 0x1D1C370 with addend=0xA9F210, type=R_X86_64_RELATIVE
    # R_X86_64_RELATIVE: *(r_offset) = base + r_addend
    # So at load time, the runtime writes 0x800000000 + 0xA9F210 = 0x800A9F210 to address 0x1D1C370 (runtime: 0x801D1C370)
    # This means 0x801D1C370 stores a pointer to 0x800A9F210 (the init function)
    
    # Find what calls/uses 0x801D1C370
    slot_runtime = 0x801D1C370
    print(f"\n=== Looking for users of slot 0x{slot_runtime:X} (which stores ptr to 0x800A9F210) ===")
    
    # Search for direct references (LEA r, [rip+disp] or MOV r, [rip+disp])
    lea_prefixes_64 = [b'\x48\x8d\x05', b'\x48\x8d\x0d', b'\x48\x8d\x15', b'\x48\x8d\x1d',
                       b'\x48\x8d\x2d', b'\x48\x8d\x35', b'\x48\x8d\x3d',
                       b'\x4c\x8d\x05', b'\x4c\x8d\x0d', b'\x4c\x8d\x15', b'\x4c\x8d\x1d',
                       b'\x4c\x8d\x25', b'\x4c\x8d\x2d', b'\x4c\x8d\x35', b'\x4c\x8d\x3d']
    mov_prefixes_64 = [b'\x48\x8b\x05', b'\x48\x8b\x0d', b'\x48\x8b\x15', b'\x48\x8b\x1d',
                       b'\x48\x8b\x2d', b'\x48\x8b\x35', b'\x48\x8b\x3d',
                       b'\x4c\x8b\x05', b'\x4c\x8b\x0d', b'\x4c\x8b\x15', b'\x4c\x8b\x1d',
                       b'\x4c\x8b\x25', b'\x4c\x8b\x2d', b'\x4c\x8b\x35', b'\x4c\x8b\x3d']
    
    slot_vaddr = slot_runtime - PS5_BASE
    found_lea = []
    found_mov = []
    for seg in img.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1): continue
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        for i in range(len(seg_data) - 7):
            # Check LEA
            for pfx in lea_prefixes_64:
                if seg_data[i:i+3] == pfx:
                    disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                    target = PS5_BASE + seg['p_vaddr'] + i + 7 + disp32
                    if target == slot_runtime:
                        found_lea.append((PS5_BASE + seg['p_vaddr'] + i, pfx.hex(), 'lea'))
                    break
            # Check MOV r, [rip+disp]
            for pfx in mov_prefixes_64:
                if seg_data[i:i+3] == pfx:
                    disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                    target = PS5_BASE + seg['p_vaddr'] + i + 7 + disp32
                    if target == slot_runtime:
                        found_mov.append((PS5_BASE + seg['p_vaddr'] + i, pfx.hex(), 'mov'))
                    break
    
    print(f"  LEA refs to slot: {len(found_lea)}")
    for a, p, k in found_lea[:20]:
        print(f"    0x{a:X}: {k} ({p})")
    print(f"  MOV-load refs to slot: {len(found_mov)}")
    for a, p, k in found_mov[:20]:
        print(f"    0x{a:X}: {k} ({p})")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
