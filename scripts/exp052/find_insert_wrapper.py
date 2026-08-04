#!/usr/bin/env python3
"""
EXP-052 Task A1e: Look at hash_insert wrapper at 0x80080602D's function,
then find ITS callers — those are the actual fillers of the hash table.
"""
import struct
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX, parse_elf_segments, EBOOT_BASE, PRX_BASE

# Step 1: Find the function start containing 0x80080602D.
# Function starts typically begin with `push rbp` (0x55) or `push rbx` (0x53)
# preceded by 0xCC (int3) padding. Walk backwards to find a function start.

def find_func_start(path, addr, max_back=0x1000):
    """Walk backwards to find function start (look for 0xCC 0x55 or 0xCC 0x53)."""
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    segments = parse_elf_segments(path, load_base=base)
    for seg in segments:
        if seg["type"] != 1 or not (seg["flags"] & 1):
            continue
        if seg["runtime_vaddr"] <= addr < seg["runtime_vaddr"] + seg["filesz"]:
            data = seg["content"]
            offset = addr - seg["runtime_vaddr"]
            # Walk backwards looking for int3 + push pattern
            for i in range(offset, max(0, offset - max_back), -1):
                if data[i] == 0xCC and i + 1 < len(data):
                    nb = data[i + 1]
                    if nb in (0x55, 0x53, 0x41, 0x40, 0x48):  # push rbp/rbx/r8-r15/rex
                        # Verify this looks like a function start
                        # Check if previous byte was also 0xCC (padding)
                        if i > 0 and data[i - 1] == 0xCC:
                            return seg["runtime_vaddr"] + i + 1
            # Fallback: just return addr - some_offset
            return addr - 0x100
    return None

# Find function containing 0x80080602D
func_start = find_func_start(EBOOT, 0x80080602D)
print(f"Function containing 0x80080602D starts at 0x{func_start:X}")
print()
print("--- Function disassembly ---")
insns = disasm_at(EBOOT, func_start, size=0x400, label="hash_insert_wrapper")
for ins in insns[:80]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

# Now find callers of this wrapper
print()
print("--- Searching for callers of the wrapper function ---")
base = EBOOT_BASE
segments = parse_elf_segments(EBOOT, load_base=base)
callers = []
for seg in segments:
    if seg["type"] != 1 or not (seg["flags"] & 1):
        continue
    data = seg["content"]
    seg_base = seg["runtime_vaddr"]
    n = len(data)
    i = 0
    while i < n - 5:
        b = data[i]
        if b == 0xE8:
            disp = struct.unpack_from("<i", data, i + 1)[0]
            insn_addr = seg_base + i
            target = insn_addr + 5 + disp
            if target == func_start:
                callers.append(insn_addr)
        i += 1
print(f"Found {len(callers)} callers of 0x{func_start:X}")
for c in callers[:50]:
    print(f"  0x{c:X}")

# Also check the wrapper's other calls (it might call hash_insert OR probe)
print()
print("--- Other call targets inside the wrapper ---")
# Already shown in the disasm above; let's also look at what's at 0x800806020 to 0x800806100
print()
print("--- Around the call site (0x800806000 to 0x800806100) ---")
insns = disasm_at(EBOOT, 0x800806000, size=0x200, label="around_call_site")
for ins in insns[:80]:
    print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
