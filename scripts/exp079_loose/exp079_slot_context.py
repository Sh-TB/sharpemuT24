#!/usr/bin/env python3
"""EXP-079 TASK 2g: Examine what's around slot 0x801D1C370 to find its table."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def main():
    img = ElfImage(EBOOT_PATH)
    
    # Read 64 bytes before and after 0x801D1C370
    slot_vaddr = 0x1D1C370
    start = slot_vaddr - 0x80
    end = slot_vaddr + 0x80
    
    off = img.vaddr_to_offset(start)
    if not off:
        print(f"Cannot map vaddr 0x{start:X}")
        return 1
    
    data = img.raw[off:off + (end - start)]
    print(f"=== Memory around slot 0x{slot_vaddr+PS5_BASE:X} ===")
    for i in range(0, len(data), 8):
        val = struct.unpack_from('<Q', data, i)[0]
        addr = start + i + PS5_BASE
        marker = ""
        if addr == 0x801D1C370:
            marker = " ← INIT_FUNC ptr (0x800A9F210)"
        elif 0x800000000 <= val < 0x8020695A0:
            # Looks like a code pointer
            marker = f" (→ code vaddr 0x{val-PS5_BASE:X})"
        elif 0x801000000 <= val < 0x802000000:
            marker = f" (→ data vaddr 0x{val-PS5_BASE:X})"
        print(f"  0x{addr:X}: 0x{val:016X}{marker}")
    
    # The slot at 0x1D1C370 is in a function pointer table. Let me find the boundaries.
    # Look for a long run of valid code pointers (0x800000000..0x8020695A0)
    print("\n=== Scanning for function pointer table boundaries ===")
    seg_start = 0x1C80000
    seg_end = 0x1C80000 + 0x9C450
    seg_off = img.vaddr_to_offset(seg_start)
    seg_data = img.raw[seg_off:seg_off + (seg_end - seg_start)]
    
    # Find runs of 8-byte values that look like code pointers
    runs = []
    in_run = False
    run_start = None
    run_count = 0
    for i in range(0, len(seg_data), 8):
        if i + 8 > len(seg_data): break
        val = struct.unpack_from('<Q', seg_data, i)[0]
        # Code pointer: 0x800000000..0x8020695A0
        is_code_ptr = (PS5_BASE <= val < PS5_BASE + img.max_vaddr) and (val & 0xF) == 0
        if is_code_ptr:
            if not in_run:
                run_start = seg_start + i
                in_run = True
                run_count = 1
            else:
                run_count += 1
        else:
            if in_run and run_count >= 4:
                runs.append((run_start, run_count))
            in_run = False
            run_count = 0
    
    # Print runs that include our slot
    print(f"Found {len(runs)} runs of >=4 code pointers in RW segment")
    for rs, rc in runs:
        rs_runtime = rs + PS5_BASE
        rs_end = rs + rc * 8 + PS5_BASE
        slot_in_run = rs <= slot_vaddr < rs + rc * 8
        marker = " ← CONTAINS OUR SLOT" if slot_in_run else ""
        print(f"  Run at 0x{rs_runtime:X} .. 0x{rs_end:X} ({rc} entries){marker}")
        if slot_in_run or rc < 30:
            # Print entries
            for i in range(min(rc, 30)):
                v = struct.unpack_from('<Q', seg_data, (rs - seg_start) + i * 8)[0]
                addr = rs + i * 8 + PS5_BASE
                slot_marker = " ← OUR SLOT" if addr == 0x801D1C370 else ""
                print(f"    0x{addr:X}: 0x{v:016X}{slot_marker}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
