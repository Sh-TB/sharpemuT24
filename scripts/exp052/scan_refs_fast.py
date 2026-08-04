#!/usr/bin/env python3
"""
EXP-052 Task A1c (fast): Find RIP-relative refs by scanning for disp32.

For a RIP-relative instruction at address A with instruction size S, the
displacement disp32 satisfies: target = A + S + disp32, so
disp32 = target - A - S.

We don't know S in advance, but for x86-64 RIP-relative instructions:
- Most are 6-8 bytes (REX + opcode + modrm + disp32, sometimes + immediate)
- The disp32 is the LAST 4 bytes of the instruction (when no immediate)
  OR the second-to-last 4 bytes (when followed by an immediate)

Strategy: For each 4-byte aligned position in the executable, check if
treating those 4 bytes as disp32 produces a valid RIP-relative ref to target.
i.e., for offset i, compute A = seg_base + i - 3 (assuming 3 prefix bytes),
and check if disp32 + A + 7 == target. If yes, decode and verify.
"""
import struct
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX, parse_elf_segments, EBOOT_BASE, PRX_BASE
import capstone

TARGETS = {
    0x801EF7610: "entries_array_base",
    0x801E51618: "hash_table_struct",
    0x801EA4E80: "metadata_list_head",
    0x801E50E40: "metadata_struct_base",
    0x801E51220: "field_+0x3E0",
    0x801E51240: "field_+0x400",
    0x801E9DF28: "registration_list_head",
    0x801EA49D8: "callback_func_ptr",
    0x801EC0C78: "callback_result_obj",
}

def scan_fast(path, target_addr, max_results=500):
    """Fast scan: for each 4-byte LE position, try decode and check."""
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    segments = parse_elf_segments(path, load_base=base)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    
    results = []
    for seg in segments:
        if seg["type"] != 1 or not (seg["flags"] & 1):
            continue
        data = seg["content"]
        seg_base = seg["runtime_vaddr"]
        n = len(data)
        # For each position i where a disp32 could start, check if the
        # preceding 3 bytes form a valid RIP-relative instruction prefix.
        # We iterate i from 3 to n-4. For each i, decode the instruction
        # ending at i+4 (size varies). Easier: just decode at every offset
        # i-3 to i-0 (4 possible start positions for a 7-byte insn), and
        # see if the resulting insn writes/reads RIP-relative to target.
        # 
        # Optimization: only try i-3, i-2, i-1, i-0 (4 possible prefix lengths).
        # That's 4 * n tries — still O(n) but with constant factor 4.
        # 
        # Even better: at each offset i, try decoding ONE instruction starting
        # at offset i. If it's RIP-relative to target, record. Capstone is fast.
        for i in range(0, n - 15):
            # Try decode one instruction at offset i
            # Use a fast path: skip if the byte at i doesn't look like a valid
            # x86 prefix/opcode start
            b = data[i]
            # Skip obvious data bytes (0xFF, 0x00, 0xCC) — but only as a heuristic
            # Actually, just try every position with capstone
            try:
                insns = list(md.disasm(data[i:i+15], seg_base + i, count=1))
            except:
                continue
            if not insns:
                continue
            insn = insns[0]
            # Check if any operand is RIP-relative to target
            for op in insn.operands:
                if op.type != capstone.x86.X86_OP_MEM:
                    continue
                mem = op.mem
                if mem.base != capstone.x86.X86_REG_RIP:
                    continue
                eff = insn.address + insn.size + mem.disp
                if eff == target_addr:
                    is_write = (op == insn.operands[0])
                    role = "W" if is_write else "R"
                    results.append((insn.address, role, str(insn)))
                    if len(results) >= max_results:
                        return results
                    break
    return results

def main():
    print("=" * 78)
    print("EXP-052 Task A1c (fast): Byte-level scan for RIP-relative refs")
    print("=" * 78)
    
    for tgt, name in TARGETS.items():
        print(f"\n=== References to 0x{tgt:X} ({name}) in eboot ===")
        results = scan_fast(EBOOT, tgt, max_results=300)
        print(f"  Found {len(results)} references")
        for addr, role, txt in results[:60]:
            print(f"  0x{addr:X} [{role}] {txt}")
        if len(results) > 60:
            print(f"  ... ({len(results)} total)")

if __name__ == "__main__":
    main()
