#!/usr/bin/env python3
"""EXP-094: Disassemble il2cpp_class_get_method_from_name (0x804F21D70).

Question: What memory structure does this function ACTUALLY search?

Hypotheses to verify by disassembly:
  H1: It reads the hash table at 0x801EF7610 (the structure EXP-040..092 focused on)
  H2: It reads [0x808923D88] (the structure used by call#7's loop body)
  H3: It reads the sorted array at 0x808958230 (the array sorted by array_proc)
  H4: It reads some other structure

Context:
  - real_init @ 0x804F055D6 calls this function (per EXP-090)
  - Args: rdi=type_ptr, rsi=namespace_str, rdx=method_name_str
  - Result stored at global 0x808B53C48 (NULL when lookup fails)
  - _ThreadPoolWaitCallback lookup returns NULL → ThreadPool deadlock (EXP-088/089/090)

This script disassembles 0x804F21D70 and reports:
  - All RIP-relative memory accesses (which globals does it read?)
  - All call targets
  - Loop structure (backward jumps)
  - Whether it reads 0x801EF7610, [0x808923D88], 0x808958230, or something else
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
TARGET_ADDR = 0x804F21D70

# Known structure addresses from prior EXPs — we'll flag any RIP-relative access
# to these addresses in the disassembly.
KNOWN_STRUCTS = {
    0x801EF7610: "global hash table ptr (EXP-040..092 focus)",
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
    print(f"\nDisassembling il2cpp_class_get_method_from_name @ 0x{TARGET_ADDR:X}")

    file_vaddr = TARGET_ADDR - PRX_BASE
    size = 2000
    code = prx.read_bytes(file_vaddr, size)
    if code is None:
        print(f"ERROR: cannot read {size} bytes at file vaddr 0x{file_vaddr:X}")
        return 1

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    # Tracking
    call_targets = []        # (caller_vaddr, target_vaddr)
    backward_jmps = []       # (caller_vaddr, target_vaddr, mnemonic) — loop candidates
    forward_jmps = []        # (caller_vaddr, target_vaddr, mnemonic)
    rip_relative_targets = []  # (insn_addr, target_addr, mnemonic) — memory accesses via RIP
    known_struct_hits = []   # (insn_addr, target_addr, struct_description)

    # Track the function's first ret to know its body size
    first_ret_addr = None
    insn_count = 0

    print(f"\n{'='*78}")
    print(f"  il2cpp_class_get_method_from_name @ 0x{TARGET_ADDR:X}")
    print(f"{'='*78}")

    for insn in md.disasm(code, TARGET_ADDR):
        insn_count += 1
        ops_str = fmt_ops(insn)
        line = f"  0x{insn.address:08X}  {insn.mnemonic:8s} {ops_str}"

        # Annotate RIP-relative memory accesses (base register = 41 in capstone = rip)
        rip_target = None
        for op in insn.operands:
            if op.type == CS_OP_MEM and op.mem.base == 41:  # rip
                rip_target = (insn.address + insn.size) + op.mem.disp
                line += f"   ; -> 0x{rip_target:X}"
                rip_relative_targets.append((insn.address, rip_target, insn.mnemonic))

                # Check if this is a known structure
                for struct_addr, desc in KNOWN_STRUCTS.items():
                    if rip_target == struct_addr:
                        known_struct_hits.append((insn.address, rip_target, desc))
                        line += f"   *** KNOWN STRUCT: {desc} ***"
                        break

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
                        line += f"   ; call indirect [rip+...] -> [0x{target:X}]"
                    else:
                        line += f"   ; call indirect {mem_str(op)}"
                elif op.type == CS_OP_REG:
                    line += f"   ; call indirect reg {insn.reg_name(op.reg)}"

        # Track jumps
        if insn.group(CS_GRP_JUMP):
            for op in insn.operands:
                if op.type == CS_OP_IMM:
                    target = op.imm & 0xFFFFFFFFFFFFFFFF
                    if target < insn.address:
                        backward_jmps.append((insn.address, target, insn.mnemonic))
                        line += f"   ; BACKWARD JUMP (loop)"
                    else:
                        forward_jmps.append((insn.address, target, insn.mnemonic))

        if len(insn.bytes.hex()) <= 16:
            line += f"   ; bytes={insn.bytes.hex()}"

        print(line)

        if insn.mnemonic == "ret" and first_ret_addr is None:
            first_ret_addr = insn.address
            print(f"  --- first ret at 0x{insn.address:X} (function body size: {insn.address - TARGET_ADDR + 1} bytes) ---")
            # Don't break — keep disassembling to see if there are multiple return paths
            # (functions often have several ret instructions)

        if insn_count > 800:
            print(f"  --- safety limit at {insn_count} instructions ---")
            break

    # ===== Summary =====
    print(f"\n{'='*78}")
    print(f"  SUMMARY")
    print(f"{'='*78}")
    print(f"  Total instructions disassembled: {insn_count}")
    if first_ret_addr:
        print(f"  First ret at: 0x{first_ret_addr:X} (body size: {first_ret_addr - TARGET_ADDR + 1} bytes)")
    print(f"  Call sites: {len(call_targets)}")
    for site, tgt in call_targets:
        in_prx = PRX_BASE <= tgt < PRX_BASE + 0x10000000
        print(f"    0x{site:08X} -> 0x{tgt:X}  {'(in PRX)' if in_prx else '(out of PRX)'}")
    print(f"  Backward jumps (loop candidates): {len(backward_jmps)}")
    for s, t, m in backward_jmps:
        print(f"    0x{s:08X} --{m}--> 0x{t:08X}  (loop body: 0x{t:X}..0x{s:X}, {s-t} bytes)")
    print(f"  Forward jumps: {len(forward_jmps)}")
    print(f"  RIP-relative accesses: {len(rip_relative_targets)}")

    print(f"\n  --- KNOWN STRUCT HITS ---")
    if not known_struct_hits:
        print(f"  *** NONE *** — function does NOT access any of the known structures!")
        print(f"  This means the lookup uses a DIFFERENT structure than any of:")
        for addr, desc in KNOWN_STRUCTS.items():
            print(f"    0x{addr:X} ({desc})")
    else:
        for site, tgt, desc in known_struct_hits:
            print(f"    0x{site:08X} accesses 0x{tgt:X} — {desc}")

    # Also list all unique RIP-relative targets, in case none match known structs
    print(f"\n  --- ALL UNIQUE RIP-RELATIVE TARGETS (first 30) ---")
    seen = set()
    for site, tgt, mnem in rip_relative_targets:
        if tgt not in seen:
            seen.add(tgt)
            in_prx = PRX_BASE <= tgt < PRX_BASE + 0x10000000
            print(f"    0x{site:08X} ({mnem}) -> 0x{tgt:X}  {'(in PRX data)' if in_prx else '(out of PRX)'}")
            if len(seen) >= 30:
                break

    return 0


if __name__ == "__main__":
    sys.exit(main())
