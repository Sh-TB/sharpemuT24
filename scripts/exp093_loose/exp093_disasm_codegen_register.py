#!/usr/bin/env python3
"""EXP-093: Disassemble the il2cpp_codegen_register implementation chain.

real_init @ 0x804F04C5C: call [0x808958220]
                              |
                              v
              0x804D9C620  (wrapper — loads 3 hardcoded pointers, tail-jumps)
                  |
                  v
              0x804FA60C0  (actual implementation)

The wrapper sets:
    rdi = rip + 0x394c9e2  (computed below)
    rsi = rip + 0x3abff71  (computed below)
    rdx = rip + 0x3511a8b  (computed below)

These three addresses are the candidates for:
    - Il2CppCodeRegistration*  (expected: 0x8086E9000 per EXP-054)
    - Il2CppMetadataRegistration* (expected: 0x80885C580 per EXP-055)
    - methodPointers / invocationList
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


def resolve_rip_relative(insn, next_rip):
    """For LEA / MOV with RIP-relative addressing, compute the absolute target."""
    for op in insn.operands:
        if op.type == CS_OP_MEM and op.mem.base == 41:  # 41 = rip in capstone
            return next_rip + op.mem.disp
    return None


def disasm_function(prx: ElfImage, label: str, vaddr: int, size: int, max_calls=15):
    print(f"\n{'='*78}")
    print(f"  {label} @ 0x{vaddr:X}  (PRX offset 0x{vaddr-PRX_BASE:X})")
    print(f"{'='*78}")

    file_vaddr = vaddr - PRX_BASE
    code = prx.read_bytes(file_vaddr, size)
    if code is None:
        print(f"  ERROR: cannot read {size} bytes at file vaddr 0x{file_vaddr:X}")
        return

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    call_targets = []
    insn_count = 0
    for insn in md.disasm(code, vaddr):
        insn_count += 1
        ops_str = fmt_ops(insn)
        line = f"  0x{insn.address:08X}  {insn.mnemonic:8s} {ops_str}"
        # Annotate RIP-relative LEA with absolute target
        if insn.mnemonic == "lea":
            target = resolve_rip_relative(insn, insn.address + insn.size)
            if target is not None:
                line += f"   ; -> 0x{target:X}"
        if insn.mnemonic == "call":
            for op in insn.operands:
                if op.type == CS_OP_MEM and op.mem.base == 41:
                    target = (insn.address + insn.size) + op.mem.disp
                    line += f"   ; -> [0x{target:X}]"
                elif op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    call_targets.append((insn.address, target))
        if len(insn.bytes.hex()) <= 16:
            line += f"   ; bytes={insn.bytes.hex()}"
        print(line)
        if insn.mnemonic == "ret":
            print(f"  --- ret reached after {insn_count} instructions ---")
            break
        if insn_count > size / 2:  # Safety limit
            print(f"  --- safety limit reached at {insn_count} instructions ---")
            break

    print(f"\n  Call sites: {len(call_targets)}")
    for site, tgt in call_targets:
        in_prx = PRX_BASE <= tgt < PRX_BASE + 0x10000000
        print(f"    0x{site:08X} -> 0x{tgt:X}  {'(in PRX)' if in_prx else '(out of PRX)'}")


def main():
    if not os.path.exists(PRX_PATH):
        print(f"ERROR: PRX not found at {PRX_PATH}", file=sys.stderr)
        return 1

    prx = ElfImage(PRX_PATH)
    print(f"Loaded PRX: {PRX_PATH}")

    # ===== Step 1: Compute the 3 hardcoded arguments from the wrapper 0x804D9C620 =====
    print("\n" + "="*78)
    print("  Step 1: Wrapper 0x804D9C620 — compute hardcoded arg addresses")
    print("="*78)

    # 0x804D9C620  lea      rsi, [rip+0x3abff71]
    # 0x804D9C627  lea      rdi, [rip+0x394c9e2]
    # 0x804D9C62E  lea      rdx, [rip+0x3511a8b]
    # 0x804D9C635  jmp      0x804fa60c0
    rsi_target = 0x804D9C627 + 0x3abff71
    rdi_target = 0x804D9C62E + 0x394c9e2
    rdx_target = 0x804D9C635 + 0x3511a8b
    print(f"  rsi (1st hardcoded arg) = 0x{rsi_target:X}")
    print(f"  rdi (2nd hardcoded arg) = 0x{rdi_target:X}")
    print(f"  rdx (3rd hardcoded arg) = 0x{rdx_target:X}")

    # Compare against known Il2Cpp registrations from EXP-054/055
    print(f"\n  Known from prior EXPs:")
    print(f"    Il2CppCodeRegistration     @ 0x8086E9000  (EXP-054)")
    print(f"    Il2CppMetadataRegistration @ 0x80885C580  (EXP-055)")
    print(f"  Match check:")
    print(f"    rsi == Il2CppMetadataRegistration? {rsi_target == 0x80885C580}")
    print(f"    rdi == Il2CppCodeRegistration?     {rdi_target == 0x8086E9000}")

    # ===== Step 2: Read first 0x40 bytes at each address to see what they point to =====
    print("\n" + "="*78)
    print("  Step 2: Dump bytes at each hardcoded address")
    print("="*78)
    for name, addr in [("rsi", rsi_target), ("rdi", rdi_target), ("rdx", rdx_target)]:
        file_vaddr = addr - PRX_BASE
        b = prx.read_bytes(file_vaddr, 0x40)
        if b is None:
            print(f"  {name} @ 0x{addr:X}: NOT IN PRX (file_vaddr=0x{file_vaddr:X})")
        else:
            print(f"  {name} @ 0x{addr:X} (file_vaddr=0x{file_vaddr:X}):")
            print(f"    first 0x40 bytes: {b.hex()}")

    # ===== Step 3: Disassemble the real implementation 0x804FA60C0 =====
    disasm_function(prx, "il2cpp_codegen_register_impl_0x804FA60C0", 0x804FA60C0, 2000)

    return 0


if __name__ == "__main__":
    sys.exit(main())
