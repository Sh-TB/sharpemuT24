#!/usr/bin/env python3
"""
EXP-052 Task A1c: Find all references to 0x801EF7610 using byte-level scan.

Capstone linear disasm desyncs on data; we use a robust byte-level scan for
the RIP-relative disp32 pattern: 48 89 1D xx xx xx xx (mov [rip+disp32], rbx)
or 48 8B 1D xx xx xx xx (mov rbx, [rip+disp32]) etc.

We scan for ANY instruction with modrm byte indicating [rip+disp32] and
check if the effective address matches our target.
"""
import struct
import sys
sys.path.insert(0, '/home/z/my-project/scripts/exp052')
from analyze_hash_table_writes import disasm_at, EBOOT, PRX, parse_elf_segments, EBOOT_BASE, PRX_BASE
import capstone

# All hash table related addresses we want to find references to
TARGETS = {
    0x801EF7610: "entries_array_base",
    0x801E51618: "hash_table_struct",
    0x801EA4E80: "metadata_list_head",
    0x801E50E40: "metadata_struct_base",
    0x801E51220: "field_+0x3E0",
    0x801E51240: "field_+0x400",
    0x801E9DF28: "registration_list_head",
}

def scan_rip_rel_refs(path, target_addr, max_results=500):
    """Byte-level scan for RIP-relative references.
    
    Strategy: For each executable byte offset, attempt to disasm 1 instruction.
    If it has a RIP-relative memory operand, check the effective address.
    This is slow (~1 minute per MB) but catches all refs.
    """
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
        # Walk through every byte offset. If capstone successfully decodes an
        # instruction with a RIP-relative mem operand pointing to target, record it.
        # Capstone's disasm() with skipdata=False will fail on bad bytes; we use a
        # sliding window.
        n = len(data)
        # To be faster, look for the 4-byte little-endian target displacement
        # near any byte sequence that looks like a RIP-relative instruction.
        # RIP-relative addressing: modrm byte has mod=00, rm=101.
        # For 64-bit, REX.W prefix (0x48 or 0x4C) is common.
        # The disp32 is the target_addr - (insn_addr + insn_size).
        # Since insn_size varies, we scan for the disp32 value directly.
        # For a typical 7-byte mov [rip+disp32], disp32 = target - (insn_addr + 7).
        # We scan each potential disp32 occurrence and verify.
        
        # Build a list of every 4-byte LE value equal to candidates
        # Actually, disp32 depends on insn_addr, so we can't just search for a value.
        # Instead, scan every byte position, try to decode one instruction, check ref.
        
        # For speed: only check positions where a RIP-relative pattern could start.
        # RIP-relative modrm: low 6 bits are 0b00_xxx_101 = 0x05, 0x0D, 0x15, ...
        # Look for bytes ending in 0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D
        # Actually modrm with mod=00 and rm=101 is just 0x05 | (reg<<3).
        # So modrm & 0xC7 == 0x05 means RIP-relative.
        
        for i in range(n):
            # Try decoding one instruction at offset i
            insns = list(md.disasm(data[i:i+15], seg_base + i, count=1))
            if not insns:
                continue
            insn = insns[0]
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
                    break  # don't duplicate
    return results

def main():
    print("=" * 78)
    print("EXP-052 Task A1c: Byte-level scan for RIP-relative refs")
    print("=" * 78)
    
    for tgt, name in TARGETS.items():
        print(f"\n=== References to 0x{tgt:X} ({name}) in eboot ===")
        results = scan_rip_rel_refs(EBOOT, tgt, max_results=200)
        print(f"  Found {len(results)} references")
        for addr, role, txt in results[:50]:
            print(f"  0x{addr:X} [{role}] {txt}")
        if len(results) > 50:
            print(f"  ... ({len(results)} total)")
    
    # Also scan PRX for the same targets
    print("\n--- PRX scan ---")
    for tgt, name in TARGETS.items():
        print(f"\n=== References to 0x{tgt:X} ({name}) in PRX ===")
        results = scan_rip_rel_refs(PRX, tgt, max_results=200)
        print(f"  Found {len(results)} references")
        for addr, role, txt in results[:30]:
            print(f"  0x{addr:X} [{role}] {txt}")

if __name__ == "__main__":
    main()
