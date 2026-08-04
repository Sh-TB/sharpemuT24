#!/usr/bin/env python3
"""EXP-097 Step 1: Search PRX and EBOOT data segments for the 4 dead-code function
addresses as stored qwords.

The 4 dead-code functions from EXP-096:
  0x804F456E0  (contains work-submission call site #1)
  0x804F9FA80  (contains work-submission call site #2)
  0x804FA1440  (contains work-submission call site #3)
  0x804FA1FE0  (contains the single caller of site #2's function)

If any of these addresses appear as a stored 8-byte value in a data segment
(RW or RO), that's a vtable slot, delegate target, or function pointer global.

We search BOTH:
  - The file image (static relocations — already set at link time)
  - Account for PRX base 0x804CD5000 and EBOOT base 0x800000000

Also search for the work-submission function itself (0x804F6EC20) in case
it's directly stored as a function pointer.
"""

import os
import sys
import struct

sys.path.insert(0, "/home/z/my-project/scripts")
from exp079_load_elf import ElfImage, PRX_PATH, EBOOT_PATH

PRX_BASE = 0x804CD5000
EBOOT_BASE = 0x800000000

# The 4 dead-code functions + the work-submission function itself
TARGETS = [
    0x804F456E0,  # contains call site #1
    0x804F9FA80,  # contains call site #2
    0x804FA1440,  # contains call site #3
    0x804FA1FE0,  # contains caller of site #2's function
    0x804F6EC20,  # the work-submission function itself
]


def scan_data_segment_for_targets(elf, image_base, image_name, targets):
    """Scan all PT_LOAD segments (both code and data) for stored qwords matching targets."""
    hits = []  # (segment_vaddr, offset_in_seg, file_offset, found_value, target_addr)
    
    for seg in elf.segments:
        if seg['p_type'] != 1:  # PT_LOAD
            continue
        seg_vaddr = seg['p_vaddr']
        seg_bytes = elf.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        flags = ''
        if seg['p_flags'] & 4: flags += 'R'
        if seg['p_flags'] & 2: flags += 'W'
        if seg['p_flags'] & 1: flags += 'X'
        
        # Scan every 8-byte-aligned position (and also unaligned, just in case)
        for i in range(0, len(seg_bytes) - 8, 1):  # step=1 to catch unaligned refs
            val = struct.unpack_from('<Q', seg_bytes, i)[0]
            if val in targets:
                runtime_addr = image_base + seg_vaddr + i
                hits.append((runtime_addr, flags, seg_vaddr, i, seg['p_offset'] + i, val))
    
    return hits


def main():
    print(f"Searching for 5 target addresses as stored qwords in PRX and EBOOT data segments...")
    print(f"Targets: {', '.join(f'0x{t:X}' for t in TARGETS)}")
    print()
    
    # ===== PRX =====
    print(f"===== PRX: {PRX_PATH} =====")
    prx = ElfImage(PRX_PATH)
    print(f"PRX segments:")
    for seg in prx.segments:
        if seg['p_type'] == 1:
            flags = ''
            if seg['p_flags'] & 4: flags += 'R'
            if seg['p_flags'] & 2: flags += 'W'
            if seg['p_flags'] & 1: flags += 'X'
            print(f"  LOAD vaddr=0x{seg['p_vaddr']:X}..0x{seg['p_vaddr']+seg['p_memsz']:X} flags={flags} filesz=0x{seg['p_filesz']:X}")
    
    prx_hits = scan_data_segment_for_targets(prx, PRX_BASE, "PRX", set(TARGETS))
    print(f"\nPRX hits: {len(prx_hits)}")
    for runtime_addr, flags, seg_vaddr, offset_in_seg, file_off, val in prx_hits:
        target_idx = TARGETS.index(val)
        label = ["site#1 func", "site#2 func", "site#3 func", "caller of site#2", "work-submit func"][target_idx]
        print(f"  [seg {flags}] runtime_addr=0x{runtime_addr:X} (seg_vaddr=0x{seg_vaddr:X} + 0x{offset_in_seg:X})  "
              f"file_off=0x{file_off:X}  value=0x{val:X} ({label})")
    
    # ===== EBOOT =====
    print(f"\n===== EBOOT: {EBOOT_PATH} =====")
    eboot = ElfImage(EBOOT_PATH)
    print(f"EBOOT segments:")
    for seg in eboot.segments:
        if seg['p_type'] == 1:
            flags = ''
            if seg['p_flags'] & 4: flags += 'R'
            if seg['p_flags'] & 2: flags += 'W'
            if seg['p_flags'] & 1: flags += 'X'
            print(f"  LOAD vaddr=0x{seg['p_vaddr']:X}..0x{seg['p_vaddr']+seg['p_memsz']:X} flags={flags} filesz=0x{seg['p_filesz']:X}")
    
    eboot_hits = scan_data_segment_for_targets(eboot, EBOOT_BASE, "EBOOT", set(TARGETS))
    print(f"\nEBOOT hits: {len(eboot_hits)}")
    for runtime_addr, flags, seg_vaddr, offset_in_seg, file_off, val in eboot_hits:
        target_idx = TARGETS.index(val)
        label = ["site#1 func", "site#2 func", "site#3 func", "caller of site#2", "work-submit func"][target_idx]
        print(f"  [seg {flags}] runtime_addr=0x{runtime_addr:X} (seg_vaddr=0x{seg_vaddr:X} + 0x{offset_in_seg:X})  "
              f"file_off=0x{file_off:X}  value=0x{val:X} ({label})")
    
    # Summary
    print(f"\n===== SUMMARY =====")
    print(f"PRX hits:   {len(prx_hits)}")
    print(f"EBOOT hits: {len(eboot_hits)}")
    
    if prx_hits:
        print(f"\nPRX hit details — these are vtable/delegate/function-pointer slots:")
        for runtime_addr, flags, seg_vaddr, offset_in_seg, file_off, val in prx_hits:
            target_idx = TARGETS.index(val)
            label = ["site#1 func", "site#2 func", "site#3 func", "caller of site#2", "work-submit func"][target_idx]
            # Classify: is this in an executable segment (vtable in .rodata near code) or RW data?
            seg_type = "RW data (runtime-writable)" if 'W' in flags else "RO data (static reloc)"
            print(f"  0x{runtime_addr:X} [{flags}] -> 0x{val:X} ({label}) [{seg_type}]")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
