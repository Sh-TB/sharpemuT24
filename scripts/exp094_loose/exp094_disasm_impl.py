#!/usr/bin/env python3
"""EXP-094 part 2: Disassemble the actual implementation that 0x804F21D70 jumps to.

0x804F21D70 is a 1-instruction trampoline: jmp 0x804EEE8D0

This script disassembles 0x804EEE8D0 to find:
  - What structure IT reads (likely 0x808923D88, same as the wrapper at 0x804F21DC0)
  - The actual lookup algorithm
"""

import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from exp079_load_elf import ElfImage, PRX_PATH  # noqa: E402

from capstone import (  # noqa: E402
    Cs, CS_ARCH_X86, CS_MODE_64,
    CS_OP_REG, CS_OP_MEM, CS_OP_IMM,
    CS_GRP_CALL, CS_GRP_JUMP,
)


PRX_BASE = 0x804CD5000
TARGET_ADDR = 0x804EEE8D0

KNOWN_STRUCTS = {
    0x801EF7610: "global hash table ptr (EXP-040..092 focus — RED HERRING?)",
    0x801EE7610: "different global (EXP039 tracer — NOT the same!)",
    0x808923D88: "call#7 loop body working structure (EXP-093)",
    0x808958230: "sorted type array (EXP-093 array_proc)",
    0x808B542E8: "saved Il2CppCodeRegistration* (EXP-093)",
    0x808B542F0: "saved Il2CppMetadataRegistration* (EXP-093)",
    0x808B542F8: "saved method pointers array (EXP-093)",
    0x808B53C48: "_ThreadPoolWaitCallback result global (EXP-090)",
    0x8086E9000: "Il2CppCodeRegistration (EXP-054)",
    0x80885C580: "Il2CppMetadataRegistration (EXP-055)",
    0x801E51240: "metadata global pointer (NULL when not set — EXP-083)",
    0x801EA4E80: "metadata list head pointer",
}


def mem_str(op):
    s = []
    if op.mem.base != 0: s.append(f"base={op.mem.base}")
    if op.mem.index != 0: s.append(f"index={op.mem.index}")
    if op.mem.disp != 0: s.append(f"disp=0x{op.mem.disp & 0xFFFFFFFFFFFFFFFF:x}")
    if op.mem.scale != 1: s.append(f"scale={op.mem.scale}")
    return "[" + ",".join(s) + "]"


def imm_str(op):
    return f"0x{op.imm & 0xFFFFFFFFFFFFFFFF:x}"


def fmt_ops(insn):
    out = []
    for op in insn.operands:
        if op.type == CS_OP_REG:
            out.append(insn.reg_name(op.reg))
        elif op.type == CS_OP_MEM:
            out.append(mem_str(op))
        elif op.type == CS_OP_IMM:
            out.append(imm_str(op))
        else:
            out.append(f"?type{op.type}")
    return ", ".join(out)


def main():
    prx = ElfImage(PRX_PATH)
    print(f"Disassembling actual impl @ 0x{TARGET_ADDR:X} (target of 0x804F21D70 jmp)")

    file_vaddr = TARGET_ADDR - PRX_BASE
    size = 1500
    code = prx.read_bytes(file_vaddr, size)
    if code is None:
        print(f"ERROR: cannot read at file vaddr 0x{file_vaddr:X}")
        return 1

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    call_targets = []
    backward_jmps = []
    rip_relative_targets = []
    known_struct_hits = []
    first_ret_addr = None
    insn_count = 0

    print(f"\n{'='*78}")
    print(f"  actual impl @ 0x{TARGET_ADDR:X}")
    print(f"{'='*78}")

    for insn in md.disasm(code, TARGET_ADDR):
        insn_count += 1
        ops_str = fmt_ops(insn)
        line = f"  0x{insn.address:08X}  {insn.mnemonic:8s} {ops_str}"

        for op in insn.operands:
            if op.type == CS_OP_MEM and op.mem.base == 41:  # rip
                rip_target = (insn.address + insn.size) + op.mem.disp
                line += f"   ; -> 0x{rip_target:X}"
                rip_relative_targets.append((insn.address, rip_target, insn.mnemonic))
                for struct_addr, desc in KNOWN_STRUCTS.items():
                    if rip_target == struct_addr:
                        known_struct_hits.append((insn.address, rip_target, desc))
                        line += f"   *** KNOWN STRUCT: {desc} ***"
                        break

        if insn.group(CS_GRP_CALL):
            for op in insn.operands:
                if op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    call_targets.append((insn.address, target))
                    in_prx = PRX_BASE <= target < PRX_BASE + 0x10000000
                    line += f"   ; call 0x{target:X} {'(in PRX)' if in_prx else '(out)'}"

        if insn.group(CS_GRP_JUMP):
            for op in insn.operands:
                if op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    if target < insn.address:
                        backward_jmps.append((insn.address, target, insn.mnemonic))

        if len(insn.bytes.hex()) <= 16:
            line += f"   ; bytes={insn.bytes.hex()}"

        print(line)

        if insn.mnemonic == "ret" and first_ret_addr is None:
            first_ret_addr = insn.address
            print(f"  --- first ret at 0x{insn.address:X} (body size so far: {insn.address - TARGET_ADDR + 1} bytes) ---")

        if insn_count > 500:
            print(f"  --- safety limit at {insn_count} instructions ---")
            break

    # Summary
    print(f"\n{'='*78}")
    print(f"  SUMMARY")
    print(f"{'='*78}")
    print(f"  Total instructions: {insn_count}")
    if first_ret_addr:
        print(f"  First ret at: 0x{first_ret_addr:X} (body size: {first_ret_addr - TARGET_ADDR + 1} bytes)")
    print(f"  Call sites: {len(call_targets)}")
    for site, tgt in call_targets[:20]:
        in_prx = PRX_BASE <= tgt < PRX_BASE + 0x10000000
        print(f"    0x{site:08X} -> 0x{tgt:X}  {'(in PRX)' if in_prx else '(out of PRX)'}")
    print(f"  Backward jumps (loop candidates): {len(backward_jmps)}")
    for s, t, m in backward_jmps[:15]:
        print(f"    0x{s:08X} --{m}--> 0x{t:08X}  (loop body: 0x{t:X}..0x{s:X}, {s-t} bytes)")
    print(f"  RIP-relative accesses: {len(rip_relative_targets)}")

    print(f"\n  --- KNOWN STRUCT HITS ---")
    if not known_struct_hits:
        print(f"  *** NONE *** — function does NOT access any of the known structures")
    else:
        for site, tgt, desc in known_struct_hits:
            print(f"    0x{site:08X} accesses 0x{tgt:X} — {desc}")

    print(f"\n  --- ALL UNIQUE RIP-RELATIVE TARGETS (first 20) ---")
    seen = set()
    for site, tgt, mnem in rip_relative_targets:
        if tgt not in seen:
            seen.add(tgt)
            in_prx = PRX_BASE <= tgt < PRX_BASE + 0x10000000
            print(f"    0x{site:08X} ({mnem}) -> 0x{tgt:X}  {'(in PRX data)' if in_prx else '(out of PRX)'}")
            if len(seen) >= 20:
                break

    return 0


if __name__ == "__main__":
    sys.exit(main())
