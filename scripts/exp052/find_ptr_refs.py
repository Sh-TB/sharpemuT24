#!/usr/bin/env python3
"""
EXP-052 Task A1j: Find function pointer references to wrapper 0x800805AE0.

The wrapper at 0x800805AE0 has 0 direct callers but IS the metadata
registration function. It must be called via a function pointer.

Strategy:
  1. Search ALL executable+data segments for the 8-byte LE value of 0x800805AE0.
  2. Also search for related addresses: writer 0x8007F90A0, callback 0x80134FA00.
  3. For each match, identify the surrounding structure (likely a vtable or func ptr table).
"""
import struct
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import parse_elf_segments, EBOOT, PRX, EBOOT_BASE, PRX_BASE

TARGETS = {
    0x800805AE0: "wrapper (calls hash_insert)",
    0x8007F90A0: "hash_table_writer (allocator)",
    0x800806940: "hash_insert (called by wrapper)",
    0x8004bd620: "metadata_lookup",
    0x800ce3aa0: "hash_key_gen",
    0x800C66670: "metadata_list_create",
    0x800C66B40: "metadata_lookup_alt",
    0x80134FA00: "callback_func",
    0x80135DDD0: "crash_func",
    0x8013EB6B0: "init_func",
    0x804F04BA0: "real_init",
    0x804ED85D0: "il2cpp_init",
    0x804F677A0: "il2cpp_add_internal_call",
}

def find_ptr_refs(path, target_addr, max_results=50):
    """Find all 8-byte LE references to target_addr in any segment."""
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    segments = parse_elf_segments(path, load_base=base)
    target_bytes = struct.pack("<Q", target_addr)
    results = []
    for seg in segments:
        data = seg["content"]
        seg_base = seg["runtime_vaddr"]
        n = len(data)
        # Use bytes.find iteratively
        pos = 0
        while True:
            idx = data.find(target_bytes, pos)
            if idx < 0:
                break
            results.append(seg_base + idx)
            pos = idx + 1
            if len(results) >= max_results:
                return results
    return results

def main():
    print("=" * 78)
    print("EXP-052 Task A1j: Function pointer references")
    print("=" * 78)
    
    for path, label in [(EBOOT, "eboot"), (PRX, "PRX")]:
        print(f"\n========== {label} ==========")
        for tgt, name in TARGETS.items():
            refs = find_ptr_refs(path, tgt, max_results=50)
            if refs:
                print(f"\n  {name} (0x{tgt:X}): {len(refs)} pointer references")
                for r in refs[:30]:
                    print(f"    @ 0x{r:X}")
                if len(refs) > 30:
                    print(f"    ... ({len(refs)} total)")
            else:
                print(f"\n  {name} (0x{tgt:X}): NO pointer references")

if __name__ == "__main__":
    main()
