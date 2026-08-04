#!/usr/bin/env python3
"""
EXP-052 Task A1d: Find direct callers of insert/probe/writer functions.

A direct CALL is `E8 disp32` (5 bytes). Target = insn_addr + 5 + disp32.
We scan executable segments for E8 bytes and check if the computed target
matches our function addresses.

Also scan for direct JMP (E9 disp32, 5 bytes) — sometimes called via tail call.
"""
import struct
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX, parse_elf_segments, EBOOT_BASE, PRX_BASE

# Functions of interest
FUNCS = {
    0x8007F90A0: "hash_table_writer",  # allocates hash table
    0x8007F9690: "entries_init",       # called by writer, fills entries (sentinel?)
    0x800806940: "hash_insert",        # candidate insert function
    0x800806800: "hash_probe_loop",    # probe loop (probably mid-function)
    0x800806600: "hash_resize",        # called from insert
    0x801704D40: "string_hash",        # called from insert
    0x800C66670: "metadata_list_create",  # creates empty metadata list
    0x800C66B40: "metadata_lookup",    # looks up metadata
    0x800C195C0: "metadata_accessor",  # stubbed in EXP-050
    0x80134FA00: "callback_func",      # stubbed in EXP-048
    0x80135DDD0: "crash_func",         # crash function
    0x8013EB6B0: "init_func",          # main init function (calls il2cpp_init)
    0x804F04BA0: "real_init",          # real_init (called by il2cpp_init)
    0x804ED85D0: "il2cpp_init",        # il2cpp_init
    0x804F677A0: "il2cpp_add_internal_call",
}

def scan_direct_calls(path, targets):
    """Scan for E8 disp32 and E9 disp32 instructions targeting our functions."""
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    segments = parse_elf_segments(path, load_base=base)
    callers = {tgt: [] for tgt in targets}
    
    for seg in segments:
        if seg["type"] != 1 or not (seg["flags"] & 1):
            continue
        data = seg["content"]
        seg_base = seg["runtime_vaddr"]
        n = len(data)
        # Search for E8 (call rel32) and E9 (jmp rel32)
        i = 0
        while i < n - 5:
            b = data[i]
            if b == 0xE8 or b == 0xE9:
                # Decode disp32 (signed LE)
                disp = struct.unpack_from("<i", data, i + 1)[0]
                insn_addr = seg_base + i
                target = insn_addr + 5 + disp
                if target in callers:
                    kind = "call" if b == 0xE8 else "jmp"
                    callers[target].append((insn_addr, kind))
            i += 1
    return callers

def main():
    print("=" * 78)
    print("EXP-052 Task A1d: Direct callers of hash table functions")
    print("=" * 78)
    
    for path, label in [(EBOOT, "eboot"), (PRX, "PRX")]:
        print(f"\n========== {label} ==========")
        callers = scan_direct_calls(path, FUNCS.keys())
        for tgt, name in FUNCS.items():
            cs = callers[tgt]
            if cs:
                print(f"\n  {name} (0x{tgt:X}): {len(cs)} callers")
                for addr, kind in cs[:30]:
                    print(f"    0x{addr:X} ({kind})")
                if len(cs) > 30:
                    print(f"    ... ({len(cs)} total)")
            else:
                print(f"\n  {name} (0x{tgt:X}): NO direct callers")

if __name__ == "__main__":
    main()
