#!/usr/bin/env python3
"""
EXP-112 step 3 — investigate the GATE function at call #151 (0x804F3E700)
and the conditional call #152 (0x804F3DF90 with rsi=1) that it guards.

Hypothesis: if 0x804F3E700 returns non-zero, call #152 is skipped. If #152
is the callback registration trigger, a wrong return from #151 would
explain why the callback dispatch subsystem never gets set up.

Also check whether 0x804F3E700 internally calls any HLE/PLT function
whose return value might be wrong.
"""
from io import BytesIO
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

PRX_PATH = "/tmp/games/yatzi/Il2cppUserAssemblies.prx"
PRX_RUNTIME_BASE = 0x804CD5000


def load_prx_text():
    with open(PRX_PATH, "rb") as f:
        data = f.read()
    elf = ELFFile(BytesIO(data))
    for i in range(elf["e_phnum"]):
        hdr = elf._get_segment_header(i)
        seg = Segment(hdr, elf.stream)
        if seg["p_type"] == "PT_LOAD" and (seg["p_flags"] & 1):
            return seg["p_vaddr"], seg.data()
    raise RuntimeError("no exec segment")


def find_next_func_start(text_data, text_base, off):
    n = len(text_data)
    align = 16
    nxt = (off + align - 1) & ~(align - 1)
    while nxt < n:
        if nxt >= 16 and 0xCC in text_data[max(0, nxt-8):nxt]:
            if nxt + 4 <= n:
                sig = text_data[nxt:nxt+4]
                if (sig == b"\xF3\x0F\x1E\xFA" or
                    sig[0] == 0x55 or
                    (sig[0] == 0x41 and sig[1] in (0x54,0x55,0x56,0x57)) or
                    (sig[0] == 0x48 and sig[1] == 0x83 and sig[2] == 0xEC) or
                    (sig[0] == 0x48 and sig[1] == 0x81 and sig[2] == 0xEC)):
                    return nxt
        nxt += align
    return n


def disasm_function(text_data, text_base, elf_va, label, max_size=0x800):
    off = elf_va - text_base
    if off < 0 or off >= len(text_data):
        print(f"  [!] {label} elf_va=0x{elf_va:x} out of range")
        return
    next_off = find_next_func_start(text_data, text_base, off + 1)
    size = next_off - off
    if size <= 0 or size > max_size:
        size = min(max_size, len(text_data) - off)
    chunk = text_data[off:off+size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n=== {label}  elf_va=0x{elf_va:x}  runtime=0x{elf_va+PRX_RUNTIME_BASE:x}  size={size} (0x{size:x}) ===")
    insns = list(md.disasm(chunk, elf_va))
    print(f"  disassembled {len(insns)} instructions")
    return insns


def list_calls(insns, label):
    """List all call instructions in the function."""
    print(f"\n--- calls in {label} ---")
    call_count = 0
    for ins in insns:
        if ins.mnemonic == "call":
            call_count += 1
            ops = ins.operands
            if len(ops) == 1:
                op = ops[0]
                if op.type == CS_OP_IMM:
                    tgt_elf = op.imm
                    tgt_runtime = tgt_elf + PRX_RUNTIME_BASE
                    # check if it's a "low address" (small function or PLT)
                    is_low = tgt_elf < 0x10000
                    kind = "low_addr" if is_low else "direct"
                    print(f"  0x{ins.address+PRX_RUNTIME_BASE:x}: call 0x{tgt_elf:x} (runtime 0x{tgt_runtime:x})  [{kind}]")
                elif op.type == CS_OP_MEM:
                    mem = op.mem
                    base = ins.reg_name(mem.base) if mem.base else None
                    disp = mem.disp
                    if base == "rip":
                        target_elf = ins.address + ins.size + disp
                        print(f"  0x{ins.address+PRX_RUNTIME_BASE:x}: call [rip+0x{disp:x}]  -> GOT/data at 0x{target_elf+PRX_RUNTIME_BASE:x}")
                    elif base:
                        print(f"  0x{ins.address+PRX_RUNTIME_BASE:x}: call [{base}+0x{disp:x}]")
                    else:
                        print(f"  0x{ins.address+PRX_RUNTIME_BASE:x}: call [mem disp=0x{disp:x}]")
                elif op.type == CS_OP_REG:
                    reg = ins.reg_name(op.reg)
                    print(f"  0x{ins.address+PRX_RUNTIME_BASE:x}: call {reg}")
    print(f"  total calls in {label}: {call_count}")
    return call_count


def main():
    text_base, text_data = load_prx_text()
    print(f"[+] text_base=0x{text_base:x}  size=0x{len(text_data):x}")

    # === GATE function: call #151 target ===
    gate_elf = 0x269700  # 0x804F3E700
    gate_runtime = gate_elf + PRX_RUNTIME_BASE
    insns = disasm_function(text_data, text_base, gate_elf, f"GATE function (call #151) 0x{gate_runtime:x}")
    if insns:
        list_calls(insns, f"GATE 0x{gate_runtime:x}")
        # Also print first 60 instructions for context
        print(f"\n  first 60 instructions of GATE function:")
        for ins in insns[:60]:
            print(f"    0x{ins.address+PRX_RUNTIME_BASE:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}")

    # === Conditional call #152 target ===
    print("\n" + "=" * 78)
    target_elf = 0x268f90  # 0x804F3DF90
    target_runtime = target_elf + PRX_RUNTIME_BASE
    insns = disasm_function(text_data, text_base, target_elf, f"CONDITIONAL call #152 target 0x{target_runtime:x}")
    if insns:
        list_calls(insns, f"COND_TARGET 0x{target_runtime:x}")
        print(f"\n  first 60 instructions of CONDITIONAL target:")
        for ins in insns[:60]:
            print(f"    0x{ins.address+PRX_RUNTIME_BASE:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}")

    # === Call #4 target 0x804F68D90 — see what it does (already partially shown) ===
    # Already shown in step 2 — skip.

    # === Look at calls #147, #148, #149 (tail setup before #150) ===
    print("\n" + "=" * 78)
    print("Calls #147, #148, #149 targets (tail setup):")
    for elf_va, name in [(0x29bd30, "call #147: 0x804F70D30"),
                          (0x29bd80, "call #148: 0x804F70D80"),
                          (0x2d3120, "call #149: 0x804FA8120")]:
        insns = disasm_function(text_data, text_base, elf_va, name, max_size=0x300)
        if insns:
            list_calls(insns, name)
            print(f"\n  first 30 instructions:")
            for ins in insns[:30]:
                print(f"    0x{ins.address+PRX_RUNTIME_BASE:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}")


if __name__ == "__main__":
    main()
