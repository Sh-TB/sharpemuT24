#!/usr/bin/env python3
"""EXP-094 part 3: Find what writes to 0x808923D88.

The metadata lookup function (il2cpp_class_get_method_from_name) reads [0x808923D88]
as its working structure. We need to find what WRITES to 0x808923D88 — that's the
function that populates the actual metadata lookup structure.

Approach:
  1. Scan the PRX executable segment for any instruction that writes to 0x808923D88
     (either directly via mov [0x808923D88], reg, or via RIP-relative addressing).
  2. For each writer, report the surrounding function context.

Also check the EBOOT for writers — the structure might be initialized by EBOOT
(before the PRX runs), similar to how 0x801EF7610 is created by EBOOT's
hash_table_writer at 0x8007F90A0.
"""

import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from exp079_load_elf import ElfImage, PRX_PATH, EBOOT_PATH  # noqa: E402

from capstone import (  # noqa: E402
    Cs, CS_ARCH_X86, CS_MODE_64,
    CS_OP_REG, CS_OP_MEM, CS_OP_IMM,
)


PRX_BASE = 0x804CD5000
EBOOT_BASE = 0x800000000
TARGET_ADDR = 0x808923D88  # the structure we want writers for


def find_writers(elf, image_base, image_name, target_addr, max_writers=20):
    """Scan all executable PT_LOAD segments for instructions that write to target_addr."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    writers = []  # list of (insn_addr, mnemonic, full_disasm, writes_target)

    # Iterate over executable segments
    for seg in elf.segments:
        if seg['p_type'] != 1:  # PT_LOAD
            continue
        if not (seg['p_flags'] & 1):  # not executable
            continue

        seg_start = seg['p_vaddr']
        seg_end = seg_start + seg['p_filesz']
        seg_size = seg['p_filesz']

        # Read segment bytes from file
        seg_bytes = elf.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        if not seg_bytes:
            continue

        # Disassemble and look for writes to target_addr
        for insn in md.disasm(seg_bytes, image_base + seg_start):
            # Check if this instruction accesses target_addr via RIP-relative
            for op in insn.operands:
                if op.type == CS_OP_MEM and op.mem.base == 41:  # rip
                    rip_target = (insn.address + insn.size) + op.mem.disp
                    if rip_target == target_addr:
                        # Check if it's a write (destination operand is the memory operand)
                        # In capstone, the destination is operands[0] for most instructions
                        is_write = (op == insn.operands[0]) if insn.operands else False
                        # Special cases: lea is not a write, call is not a write
                        if insn.mnemonic in ("lea", "call", "jmp", "cmp", "test", "movsse", "movaps"):
                            is_write = insn.mnemonic == "mov" and is_write
                        writers.append((
                            insn.address,
                            insn.mnemonic,
                            f"{insn.mnemonic} {', '.join(_fmt_op(insn, op) for op in insn.operands)}",
                            is_write,
                        ))
                        if len(writers) >= max_writers:
                            return writers
                        break
    return writers


def _fmt_op(insn, op):
    if op.type == CS_OP_REG:
        return insn.reg_name(op.reg)
    elif op.type == CS_OP_MEM:
        s = []
        if op.mem.base != 0: s.append(f"base={op.mem.base}")
        if op.mem.index != 0: s.append(f"index={op.mem.index}")
        if op.mem.disp != 0: s.append(f"disp=0x{op.mem.disp & 0xFFFFFFFFFFFFFFFF:x}")
        if op.mem.scale != 1: s.append(f"scale={op.mem.scale}")
        return "[" + ",".join(s) + "]"
    elif op.type == CS_OP_IMM:
        return f"0x{op.imm & 0xFFFFFFFFFFFFFFFF:x}"
    return f"?type{op.type}"


def main():
    print(f"Searching for writes to 0x{TARGET_ADDR:X} in PRX and EBOOT...")
    print(f"(This may take 1-2 minutes — scanning entire executable segments.)\n")

    # ===== PRX =====
    print(f"===== PRX: {PRX_PATH} =====")
    prx = ElfImage(PRX_PATH)
    prx_writers = find_writers(prx, PRX_BASE, "PRX", TARGET_ADDR, max_writers=30)
    print(f"Found {len(prx_writers)} accesses to 0x{TARGET_ADDR:X} in PRX:")
    for addr, mnem, disasm, is_write in prx_writers:
        kind = "WRITE" if is_write else "READ"
        print(f"  0x{addr:08X}  [{kind}]  {disasm}")

    # ===== EBOOT =====
    print(f"\n===== EBOOT: {EBOOT_PATH} =====")
    eboot = ElfImage(EBOOT_PATH)
    eboot_writers = find_writers(eboot, EBOOT_BASE, "EBOOT", TARGET_ADDR, max_writers=30)
    print(f"Found {len(eboot_writers)} accesses to 0x{TARGET_ADDR:X} in EBOOT:")
    for addr, mnem, disasm, is_write in eboot_writers:
        kind = "WRITE" if is_write else "READ"
        print(f"  0x{addr:08X}  [{kind}]  {disasm}")

    # Summary
    prx_write_count = sum(1 for _, _, _, w in prx_writers if w)
    eboot_write_count = sum(1 for _, _, _, w in eboot_writers if w)
    print(f"\n===== SUMMARY =====")
    print(f"PRX writers:   {prx_write_count}")
    print(f"EBOOT writers: {eboot_write_count}")
    print(f"PRX readers:   {len(prx_writers) - prx_write_count}")
    print(f"EBOOT readers: {len(eboot_writers) - eboot_write_count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
