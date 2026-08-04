#!/usr/bin/env python3
"""
EXP-093: Disassemble array_proc (0x804F2B4D0) and call#7 (0x804F23320) in the PRX
to find:
  1. The loop body inside array_proc (where each entry is processed)
  2. Any `call` instructions inside that loop — these are candidates for the
     hash-insert function that should populate 0x801EF7610's hash table
  3. Whether il2cpp_codegen_register is reachable from real_init/call#7

PRX base = 0x804CD5000 (from master state).
  real_init  = 0x804F04BA0  -> prx offset 0x22FBA0
  call#7     = 0x804F23320  -> prx offset 0x24E320
  array_proc = 0x804F2B4D0  -> prx offset 0x2564D0
"""

import os
import sys
import struct

# Make the existing exp079_load_elf.py importable
sys.path.insert(0, "/home/z/my-project/scripts")
from exp079_load_elf import ElfImage, PRX_PATH  # noqa: E402

from capstone import (  # noqa: E402
    Cs, CS_ARCH_X86, CS_MODE_64,
    CS_OP_REG, CS_OP_MEM, CS_OP_IMM,
    CS_GRP_CALL, CS_GRP_JUMP,
)


PRX_BASE = 0x804CD5000

TARGETS = [
    # The indirect-call target from real_init @ 0x804F04C5C.
    # Loaded from [0x808958220] at runtime. Top candidate for il2cpp_codegen_register.
    ("indirect_target_0x804D9C620", 0x804D9C620, 1500),
    # array_proc's inner call at 0x804F2B714 — called per-entry during merge step.
    ("array_proc_inner_0x804F5B1B0", 0x804F5B1B0, 600),
    # array_proc's first call at 0x804F2B526 — called once per recursion.
    ("array_proc_helper_0x804F2BB30", 0x804F2BB30, 600),
    # call#7's loop body at 0x804F238F0 — called per iteration of first loop.
    ("call7_loopbody_0x804F238F0", 0x804F238F0, 400),
]


def reg_name(op):
    return op.reg


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


def disasm_function(prx: ElfImage, label: str, vaddr: int, size: int):
    print(f"\n{'='*78}")
    print(f"  {label} @ 0x{vaddr:X}  (PRX offset 0x{vaddr-PRX_BASE:X})")
    print(f"{'='*78}")

    # PRX vaddrs are file-relative (start at 0). Convert runtime vaddr to file-relative.
    file_vaddr = vaddr - PRX_BASE
    code = prx.read_bytes(file_vaddr, size)
    if code is None:
        print(f"  ERROR: cannot read {size} bytes at 0x{vaddr:X}")
        return []

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    insns = []
    call_targets = []  # list of (caller_vaddr, target_vaddr)
    jmp_targets = []   # list of (caller_vaddr, target_vaddr, mnemonic)

    for insn in md.disasm(code, vaddr):
        insns.append(insn)
        ops_str = fmt_ops(insn)
        line = f"  0x{insn.address:08X}  {insn.mnemonic:8s} {ops_str}"
        if len(insn.bytes.hex()) <= 16:
            line += f"   ; bytes={insn.bytes.hex()}"
        print(line)

        # Capture calls
        if insn.group(CS_GRP_CALL):
            # Find immediate target (E8 rel32 or FF /2 indirect)
            for op in insn.operands:
                if op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    call_targets.append((insn.address, target))
                elif op.type == CS_OP_MEM:
                    # Indirect call via memory — usually a GOT slot or function pointer
                    call_targets.append((insn.address, f"indirect:{mem_str(op)}"))
                elif op.type == CS_OP_REG:
                    call_targets.append((insn.address, f"indirect:{insn.reg_name(op.reg)}"))

        # Capture jumps (for loop body detection)
        if insn.group(CS_GRP_JUMP):
            for op in insn.operands:
                if op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    jmp_targets.append((insn.address, target, insn.mnemonic))

    # Summary
    print(f"\n  --- {label} summary ---")
    print(f"  Total instructions disassembled: {len(insns)}")
    print(f"  Call sites: {len(call_targets)}")
    for site, tgt in call_targets:
        if isinstance(tgt, int):
            # Is target inside PRX code segment?
            in_prx = PRX_BASE <= tgt < PRX_BASE + 0x10000000
            print(f"    0x{site:08X} -> 0x{tgt:X}  {'(in PRX)' if in_prx else '(out of PRX)'}")
        else:
            print(f"    0x{site:08X} -> {tgt}")
    print(f"  Jump sites: {len(jmp_targets)}")
    backward_jmps = [(s, t, m) for s, t, m in jmp_targets if t < s]
    if backward_jmps:
        print(f"  BACKWARD jumps (loop candidates): {len(backward_jmps)}")
        for s, t, m in backward_jmps:
            print(f"    0x{s:08X} --{m}--> 0x{t:08X}  (loop body: 0x{t:X}..0x{s:X}, {s-t} bytes)")
    return insns


def main():
    if not os.path.exists(PRX_PATH):
        print(f"ERROR: PRX not found at {PRX_PATH}", file=sys.stderr)
        return 1

    prx = ElfImage(PRX_PATH)
    print(f"Loaded PRX: {PRX_PATH}")
    print(f"  raw size: {len(prx.raw)} bytes")
    print(f"  vaddr range: 0x{prx.min_vaddr:X} .. 0x{prx.max_vaddr:X}")
    print(f"  PRX base (runtime): 0x{PRX_BASE:X}")

    # Sanity: confirm 0x804CD5000 maps to start of PRX
    b = prx.read_bytes(0x804CD5000, 16)
    if b:
        print(f"  bytes @ PRX base: {b.hex()}")
    else:
        print(f"  WARN: cannot read at PRX base 0x{PRX_BASE:X}")

    # Disassemble each target
    for label, vaddr, size in TARGETS:
        disasm_function(prx, label, vaddr, size)

    return 0


if __name__ == "__main__":
    sys.exit(main())
