#!/usr/bin/env python3
"""EXP-093: Disassemble the ACTUAL il2cpp_codegen_register implementation at 0x804F23280.

Call chain (verified):
    real_init @ 0x804F04C5C: call [0x808958220]
      -> 0x804D9C620  (wrapper: loads 3 hardcoded args)
         -> 0x804FA60C0  (trampoline: jmp 0x804F23280)
            -> 0x804F23280  (actual implementation)  <-- THIS FILE

Hardcoded args:
    rdi = 0x8086E9010  (Il2CppCodeRegistration @ 0x8086E9000 + 0x10)
    rsi = 0x80885C598  (Il2CppMetadataRegistration @ 0x80885C580 + 0x18)
    rdx = 0x8082AE0C0  (method pointers / type index)
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
TARGET_ADDR = 0x804F23280


def mem_str(op):
    s = []
    if op.mem.base != 0:
        s.append(f"base={op.mem.base}")
    if op.mem.index != 0:
        s.append(f"index={op.mem.index}")
    if op.mem.disp != 0:
        s.append(f"disp=0x{op.mem.disp & 0xFFFFFFFFFFFFFFFF:x}")
    if op.mem.scale != 1:
        s.append(f"scale={op.mem.scale}")
    return "[" + ",".join(s) + "]"


def imm_str(op):
    v = op.imm & 0xFFFFFFFFFFFFFFFF
    return f"0x{v:x}"


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
    if not os.path.exists(PRX_PATH):
        print(f"ERROR: PRX not found at {PRX_PATH}", file=sys.stderr)
        return 1

    prx = ElfImage(PRX_PATH)
    print(f"Loaded PRX: {PRX_PATH}")
    print(f"\nDisassembling il2cpp_codegen_register impl @ 0x{TARGET_ADDR:X}")

    file_vaddr = TARGET_ADDR - PRX_BASE
    size = 1500
    code = prx.read_bytes(file_vaddr, size)
    if code is None:
        print(f"ERROR: cannot read {size} bytes at file vaddr 0x{file_vaddr:X}")
        return 1

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    call_targets = []
    jmp_targets = []
    backward_jmps = []
    ret_count = 0
    insn_count = 0

    print(f"\n{'='*78}")
    print(f"  il2cpp_codegen_register @ 0x{TARGET_ADDR:X}")
    print(f"{'='*78}")

    for insn in md.disasm(code, TARGET_ADDR):
        insn_count += 1
        ops_str = fmt_ops(insn)
        line = f"  0x{insn.address:08X}  {insn.mnemonic:8s} {ops_str}"

        # Annotate RIP-relative
        if insn.mnemonic in ("lea", "mov"):
            for op in insn.operands:
                if op.type == CS_OP_MEM and op.mem.base == 41:  # 41 = rip
                    target = (insn.address + insn.size) + op.mem.disp
                    line += f"   ; -> 0x{target:X}"

        # Track calls
        if insn.group(CS_GRP_CALL):
            for op in insn.operands:
                if op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    call_targets.append((insn.address, target))
                    in_prx = PRX_BASE <= target < PRX_BASE + 0x10000000
                    line += f"   ; call 0x{target:X} {'(in PRX)' if in_prx else '(out)'}"
                elif op.type == CS_OP_MEM:
                    if op.mem.base == 41:  # rip
                        target = (insn.address + insn.size) + op.mem.disp
                        line += f"   ; call [rip+0x{op.mem.disp & 0xFFFFFFFFFFFFFFFF:x}] -> [0x{target:X}]"
                    else:
                        line += f"   ; call indirect {mem_str(op)}"
                elif op.type == CS_OP_REG:
                    line += f"   ; call indirect reg {insn.reg_name(op.reg)}"

        # Track jumps
        if insn.group(CS_GRP_JUMP):
            for op in insn.operands:
                if op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    jmp_targets.append((insn.address, target, insn.mnemonic))
                    if target < insn.address:
                        backward_jmps.append((insn.address, target, insn.mnemonic))

        if len(insn.bytes.hex()) <= 16:
            line += f"   ; bytes={insn.bytes.hex()}"

        print(line)

        if insn.mnemonic == "ret":
            ret_count += 1
            if ret_count >= 3:
                print(f"  --- {ret_count} rets reached, stopping ---")
                break

        if insn_count > 600:
            print(f"  --- safety limit at {insn_count} instructions ---")
            break

    print(f"\n  --- Summary ---")
    print(f"  Total instructions: {insn_count}")
    print(f"  Rets found: {ret_count}")
    print(f"  Call sites: {len(call_targets)}")
    for site, tgt in call_targets:
        in_prx = PRX_BASE <= tgt < PRX_BASE + 0x10000000
        print(f"    0x{site:08X} -> 0x{tgt:X}  {'(in PRX)' if in_prx else '(out of PRX)'}")
    print(f"  Backward jumps (loop candidates): {len(backward_jmps)}")
    for s, t, m in backward_jmps:
        print(f"    0x{s:08X} --{m}--> 0x{t:08X}  (loop body: 0x{t:X}..0x{s:X}, {s-t} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
