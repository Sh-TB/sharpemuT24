#!/usr/bin/env python3
"""
EXP-052 Task A1: Static search for hash-table writers.

PS5 ELFs have stripped/invalid section headers but valid program headers.
We parse the program headers manually using struct to avoid lief issues.

Strategy:
  1. Parse ELF program headers (PT_LOAD segments).
  2. Disassemble each executable segment.
  3. Find RIP-relative writes to target addresses.
  4. Disassemble key functions: writer 0x8007F90A0, probe 0x800806800.
"""
import struct
import sys
from pathlib import Path
import capstone

EBOOT = "/tmp/games/yatzi/eboot.bin"
PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"

# Targets of interest
TARGETS = {
    0x801EF7610: "hash_table_ptr",
    0x801EA4E80: "metadata_list_head",
    0x801E50E40: "metadata_struct_base",
    0x801E51220: "field_+0x3E0",
    0x801E51240: "field_+0x400",
    0x801E9DF28: "registration_list_head",
    0x801EA49D8: "callback_func_ptr",
}

def parse_elf_segments(path, load_base=None):
    """Parse ELF program headers. If load_base is given, treat that as the
    runtime load base (e.g. 0x800000000 for eboot). Otherwise use file vaddr."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF":
        raise ValueError(f"{path} is not ELF")
    is_64 = data[4] == 2
    is_le = data[5] == 1
    if not (is_64 and is_le):
        raise ValueError("Only 64-bit LE ELF supported")
    # ELF64 header
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
            struct.unpack_from("<IIQQQQQQ", data, off)
        content = data[p_offset:p_offset + p_filesz]
        # Compute runtime vaddr. The first PT_LOAD with file vaddr 0 starts at load_base.
        # We track BOTH file_vaddr (original) and runtime_vaddr (file + load_base).
        segments.append({
            "type": p_type, "flags": p_flags,
            "file_vaddr": p_vaddr,
            "runtime_vaddr": p_vaddr + (load_base or 0),
            "filesz": p_filesz, "memsz": p_memsz, "align": p_align,
            "file_offset": p_offset, "content": content,
        })
    return segments

# Eboot loads at 0x800000000, PRX loads at 0x808800000 (per prior findings).
EBOOT_BASE = 0x800000000
PRX_BASE = 0x808800000  # From prior EXP-039 analysis

def get_seg_bytes(segments, runtime_vaddr, size):
    for seg in segments:
        if seg["type"] == 1:  # PT_LOAD
            if seg["runtime_vaddr"] <= runtime_vaddr < seg["runtime_vaddr"] + seg["filesz"]:
                off = runtime_vaddr - seg["runtime_vaddr"]
                return seg["content"][off:off + size]
    return None

def disasm_at(path, addr, size=0x800, label=""):
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    segments = parse_elf_segments(path, load_base=base)
    data = get_seg_bytes(segments, addr, size)
    if data is None:
        print(f"  ERROR: cannot read code at 0x{addr:X} in {path}")
        return []
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    insns = list(md.disasm(data, addr))
    if label:
        print(f"\n=== {label} @ 0x{addr:X} ({len(insns)} insns) ===")
    return insns

def find_rip_rel_writes_to(path, target_addr, max_results=200):
    """Find all instructions that write RIP-relative to target_addr."""
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    segments = parse_elf_segments(path, load_base=base)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    results = []
    for seg in segments:
        if seg["type"] != 1:
            continue
        if not (seg["flags"] & 1):  # PF_X
            continue
        data = seg["content"]
        seg_base = seg["runtime_vaddr"]
        for insn in md.disasm(data, seg_base):
            if insn.mnemonic not in ("mov", "movabs", "and", "or", "xor", "add", "sub"):
                continue
            for op in insn.operands:
                if op.type != capstone.x86.X86_OP_MEM:
                    continue
                mem = op.mem
                if mem.base != capstone.x86.X86_REG_RIP:
                    continue
                eff = insn.address + insn.size + mem.disp
                if eff == target_addr:
                    if op == insn.operands[0]:
                        results.append((insn.address, str(insn)))
                        if len(results) >= max_results:
                            return results
    return results

# (Note: PRX_BASE depends on where SharpEmu loads Il2cppUserAssemblies.prx.
# We use 0x808800000 as a working hypothesis based on prior EXP-039 logs.)

def find_rip_rel_refs_to(path, target_addr, max_results=200):
    """Find all RIP-relative reads OR writes to target_addr."""
    base = EBOOT_BASE if path == EBOOT else PRX_BASE
    segments = parse_elf_segments(path, load_base=base)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    results = []
    for seg in segments:
        if seg["type"] != 1:
            continue
        if not (seg["flags"] & 1):
            continue
        data = seg["content"]
        seg_base = seg["runtime_vaddr"]
        for insn in md.disasm(data, seg_base):
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
    return results

def main():
    print("=" * 78)
    print("EXP-052 Task A1: Hash table writer search")
    print("=" * 78)

    # Step 1: disassemble hash table writer 0x8007F90A0
    print("\n--- Step 1: Hash table writer 0x8007F90A0 (eboot) ---")
    insns = disasm_at(EBOOT, 0x8007F90A0, size=0x600, label="hash_table_writer")
    for ins in insns[:80]:
        print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

    # Step 2: disassemble probe loop 0x800806800
    print("\n--- Step 2: Probe loop 0x800806800 (eboot) ---")
    insns = disasm_at(EBOOT, 0x800806800, size=0x600, label="hash_probe_loop")
    for ins in insns[:120]:
        print(f"  0x{ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")

    # Step 3: For each target, find all RIP-relative writes/reads
    for tgt, name in TARGETS.items():
        print(f"\n--- References to 0x{tgt:X} ({name}) in eboot ---")
        results = find_rip_rel_refs_to(EBOOT, tgt, max_results=300)
        for addr, role, txt in results[:40]:
            print(f"  0x{addr:X} [{role}] {txt}")
        if len(results) > 40:
            print(f"  ... ({len(results)} total)")
        print(f"\n--- References to 0x{tgt:X} ({name}) in PRX ---")
        results = find_rip_rel_refs_to(PRX, tgt, max_results=300)
        for addr, role, txt in results[:40]:
            print(f"  0x{addr:X} [{role}] {txt}")
        if len(results) > 40:
            print(f"  ... ({len(results)} total)")

if __name__ == "__main__":
    main()
