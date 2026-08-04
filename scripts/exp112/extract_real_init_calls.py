#!/usr/bin/env python3
"""
EXP-112 step 1 — statically extract all 164 call instructions from
real_init (0x804F04BA0, 4560 bytes), classify each by:
  - call type: direct / indirect-mem / indirect-reg / PLT-stub
  - target runtime VA
  - target name (if it's a known reachable function)
  - position (call index #1..#164)
"""
import json
import os
from io import BytesIO
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

PRX_PATH = "/tmp/games/yatzi/Il2cppUserAssemblies.prx"
PRX_RUNTIME_BASE = 0x804CD5000

REAL_INIT_RUNTIME_VA = 0x804F04BA0
REAL_INIT_ELF_VA = REAL_INIT_RUNTIME_VA - PRX_RUNTIME_BASE

KNOWN_REACHABLE = {
    0x804F04BA0: "real_init",
    0x804F527C0: "registration_parent",
    0x804FA20E0: "registration_func",
    0x804F889D0: "registration_helper",
    0x804FC2930: "once_init_primitive_start",
    0x804FC33B0: "once_init_primitive (mid)",
    0x804FA1FE0: "registered_callback_NEVER_INVOKED",
    0x804F6EC20: "work_submission_NEVER_REACHED",
    0x804F9FA80: "registered_callback_calls_work_submission",
    0x804F6E510: "threadpool_dispatch (WaitSema blocks)",
    0x804FC31F0: "called_by_registered_callback_target_1",
    0x804FC2C80: "called_by_registered_callback_target_2",
    0x804FC1C60: "registered_callback_helper_1",
    0x804FC1CE0: "registered_callback_helper_2",
    0x804F88AD0: "callback_invoker_NEVER_REACHED",
}

PLT_RANGE_END = 0x10000


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


def extract_real_init_calls(text_data, text_base):
    off = REAL_INIT_ELF_VA - text_base
    next_off = find_next_func_start(text_data, text_base, off + 1)
    size = next_off - off
    if size > 0x4000:
        size = 0x4000
    chunk = text_data[off:off+size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    insns = list(md.disasm(chunk, REAL_INIT_ELF_VA))

    calls = []
    for i, ins in enumerate(insns):
        if ins.mnemonic != "call":
            continue
        ops = ins.operands
        if len(ops) != 1:
            continue
        op = ops[0]
        site_runtime = ins.address + PRX_RUNTIME_BASE
        if op.type == CS_OP_IMM:
            target_elf = op.imm
            target_runtime = target_elf + PRX_RUNTIME_BASE
            call_type = "direct"
            is_plt = target_elf < PLT_RANGE_END
            if is_plt:
                call_type = "plt_stub"
            calls.append({
                "index": len(calls) + 1,
                "site_runtime_va": site_runtime,
                "site_elf_va": ins.address,
                "target_runtime_va": target_runtime,
                "target_elf_va": target_elf,
                "call_type": call_type,
                "target_known_name": KNOWN_REACHABLE.get(target_runtime, ""),
                "insn": f"{ins.mnemonic} {ins.op_str}",
                "bytes": ins.bytes.hex(),
            })
        elif op.type == CS_OP_MEM:
            mem = op.mem
            disp = mem.disp
            base = ins.reg_name(mem.base) if mem.base else None
            index = ins.reg_name(mem.index) if mem.index else None
            calls.append({
                "index": len(calls) + 1,
                "site_runtime_va": site_runtime,
                "site_elf_va": ins.address,
                "target_runtime_va": None,
                "target_elf_va": None,
                "call_type": "indirect_mem",
                "mem_base": base,
                "mem_index": index,
                "mem_disp": disp,
                "insn": f"{ins.mnemonic} {ins.op_str}",
                "bytes": ins.bytes.hex(),
            })
        elif op.type == CS_OP_REG:
            reg = ins.reg_name(op.reg)
            calls.append({
                "index": len(calls) + 1,
                "site_runtime_va": site_runtime,
                "site_elf_va": ins.address,
                "target_runtime_va": None,
                "target_elf_va": None,
                "call_type": "indirect_reg",
                "reg": reg,
                "insn": f"{ins.mnemonic} {ins.op_str}",
                "bytes": ins.bytes.hex(),
            })

    return calls, size, len(insns)


def main():
    text_base, text_data = load_prx_text()
    print(f"[+] text_base=0x{text_base:x}  size=0x{len(text_data):x}")

    calls, size, total_insns = extract_real_init_calls(text_data, text_base)
    print(f"[+] real_init: 0x{REAL_INIT_RUNTIME_VA:x}..0x{REAL_INIT_RUNTIME_VA+size:x}  size={size} (0x{size:x})")
    print(f"[+] total instructions: {total_insns}")
    print(f"[+] total call instructions: {len(calls)}")

    direct = [c for c in calls if c["call_type"] == "direct"]
    plt = [c for c in calls if c["call_type"] == "plt_stub"]
    indirect_mem = [c for c in calls if c["call_type"] == "indirect_mem"]
    indirect_reg = [c for c in calls if c["call_type"] == "indirect_reg"]

    print()
    print("=" * 78)
    print(f"CALL CLASSIFICATION:")
    print(f"  Direct (to PRX-internal function):  {len(direct)}")
    print(f"  PLT stub (likely HLE/libc import):  {len(plt)}")
    print(f"  Indirect via memory:                 {len(indirect_mem)}")
    print(f"  Indirect via register:               {len(indirect_reg)}")
    print("=" * 78)

    from collections import Counter
    plt_targets = Counter()
    for c in calls:
        if c["call_type"] == "plt_stub":
            plt_targets[c["target_elf_va"]] += 1
    print(f"\nPLT stub targets (called from real_init):")
    for target_elf, count in plt_targets.most_common():
        target_runtime = target_elf + PRX_RUNTIME_BASE
        print(f"  elf_va=0x{target_elf:6x}  runtime=0x{target_runtime:x}  called {count}x")

    direct_targets = Counter()
    for c in direct:
        direct_targets[c["target_elf_va"]] += 1
    print(f"\nDirect call targets (called from real_init) — top 20 by call count:")
    for target_elf, count in direct_targets.most_common(20):
        target_runtime = target_elf + PRX_RUNTIME_BASE
        name = KNOWN_REACHABLE.get(target_runtime, "")
        print(f"  elf_va=0x{target_elf:6x}  runtime=0x{target_runtime:x}  called {count}x  {name}")

    print(f"\nAll {len(calls)} calls in source order (first 40):")
    print(f"{'#':>3}  {'site_runtime':>11}  {'type':<14}  {'target':>11}  insn")
    for c in calls[:40]:
        if c["call_type"] in ("direct", "plt_stub"):
            tgt = f"0x{c['target_runtime_va']:x}"
        elif c["call_type"] == "indirect_mem":
            tgt = f"mem[{c['mem_base']}+0x{c['mem_disp']:x}]" if c['mem_base'] else f"mem[+0x{c['mem_disp']:x}]"
        else:
            tgt = f"reg:{c['reg']}"
        name = c.get('target_known_name') or ''
        marker = f"  [{name}]" if name else ""
        print(f"{c['index']:>3}  0x{c['site_runtime_va']:x}  {c['call_type']:<14}  {tgt:>11}  {c['insn']}{marker}")

    if len(calls) > 40:
        print(f"\n... ({len(calls)-40} more calls)\n")
        print(f"Last 30 calls in source order:")
        print(f"{'#':>3}  {'site_runtime':>11}  {'type':<14}  {'target':>11}  insn")
        for c in calls[-30:]:
            if c["call_type"] in ("direct", "plt_stub"):
                tgt = f"0x{c['target_runtime_va']:x}"
            elif c["call_type"] == "indirect_mem":
                tgt = f"mem[{c['mem_base']}+0x{c['mem_disp']:x}]" if c['mem_base'] else f"mem[+0x{c['mem_disp']:x}]"
            else:
                tgt = f"reg:{c['reg']}"
            name = c.get('target_known_name') or ''
            marker = f"  [{name}]" if name else ""
            print(f"{c['index']:>3}  0x{c['site_runtime_va']:x}  {c['call_type']:<14}  {tgt:>11}  {c['insn']}{marker}")

    os.makedirs("/home/z/my-project/scripts/exp112", exist_ok=True)
    with open("/home/z/my-project/scripts/exp112/real_init_calls.json", "w") as f:
        json.dump({
            "real_init_runtime_va": hex(REAL_INIT_RUNTIME_VA),
            "real_init_size": size,
            "total_calls": len(calls),
            "by_type": {
                "direct": len(direct),
                "plt_stub": len(plt),
                "indirect_mem": len(indirect_mem),
                "indirect_reg": len(indirect_reg),
            },
            "calls": calls,
        }, f, indent=2)

    print(f"\n[+] Full call list saved to /home/z/my-project/scripts/exp112/real_init_calls.json")


if __name__ == "__main__":
    main()
