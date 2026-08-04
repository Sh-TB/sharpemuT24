#!/usr/bin/env python3
"""
EXP-111 verification: spot-disassemble the known reachable functions
and check whether our scan correctly identified (or missed) any
`call [reg+0x08]` sites inside them.

For each of:
  real_init        (0x804F04BA0 -> elf 0x22fba0, containing func 0x22fba0)
  0x804F527C0      (-> elf 0x1d7c0,   containing func 0x1d7c0)
  0x804FA20E0      (-> elf 0x2d0e0,   containing func 0x2d0e0)
  0x804F889D0      (-> elf 0x139d0,   containing func 0x139d0)
  0x804FC33B0      (-> elf 0x2e3b0,   containing func 0x2ed930 -- per prior step)

... disassemble up to the next heuristic function start (or 4KB max),
print every `call` instruction, every `mov rXX, [reg+0x08]` instruction,
and confirm none of them match our patterns.
"""
from io import BytesIO
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG

PRX_PATH = "/tmp/games/yatzi/Il2cppUserAssemblies.prx"
PRX_RUNTIME_BASE = 0x804CD5000

TARGETS = [
    (0x804F04BA0, "real_init"),
    (0x804F527C0, "registration_parent"),
    (0x804FA20E0, "registration_func"),
    (0x804F889D0, "registration_helper"),
    (0x804FC33B0, "once_init_primitive"),
]


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
    """Find next 16-byte aligned offset after `off` whose preceding bytes
    include 0xCC and which begins with a known prologue. Return offset
    or len(text_data) if none."""
    n = len(text_data)
    align = 16
    # Round up to next 16-byte boundary
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


def disasm_function(text_data, text_base, func_elf_va, label, max_size=0x4000):
    off = func_elf_va - text_base
    if off < 0 or off >= len(text_data):
        print(f"  [!] {label} 0x{func_elf_va:x} out of range")
        return
    next_off = find_next_func_start(text_data, text_base, off + 1)
    size = next_off - off
    if size <= 0 or size > max_size:
        size = min(max_size, len(text_data) - off)
    chunk = text_data[off:off+size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n=== {label}  elf_va=0x{func_elf_va:x}  runtime=0x{func_elf_va+PRX_RUNTIME_BASE:x}  size={size} (0x{size:x}) ===")
    insns = list(md.disasm(chunk, func_elf_va))
    print(f"  disassembled {len(insns)} instructions")
    found_calls = []
    found_loads_disp8 = []
    for ins in insns:
        if ins.mnemonic == "call":
            ops = ins.operands
            if len(ops) == 1:
                op = ops[0]
                if op.type == CS_OP_MEM and op.mem.disp == 0x08 and op.mem.base != 0 and op.mem.index == 0:
                    found_calls.append((ins.address, ins.mnemonic, ins.op_str, ins.reg_name(op.mem.base)))
                elif op.type == CS_OP_REG:
                    found_calls.append((ins.address, ins.mnemonic, ins.op_str, "REG:" + ins.reg_name(op.reg)))
                elif op.type == CS_OP_MEM:
                    found_calls.append((ins.address, ins.mnemonic, ins.op_str, f"MEM disp=0x{op.mem.disp:x}"))
                else:
                    found_calls.append((ins.address, ins.mnemonic, ins.op_str, "OTHER"))
        if ins.mnemonic == "mov" and len(ins.operands) == 2:
            dst, src = ins.operands
            if (dst.type == CS_OP_REG and src.type == CS_OP_MEM and
                src.mem.disp == 0x08 and src.mem.base != 0 and src.mem.index == 0):
                found_loads_disp8.append((ins.address, ins.mnemonic, ins.op_str, ins.reg_name(dst.reg), ins.reg_name(src.mem.base)))

    print(f"  total call instructions: {len(found_calls)}")
    print(f"  total `mov rXX, [reg+0x08]` loads: {len(found_loads_disp8)}")
    print(f"  --- all `call` instructions in this function ---")
    for va, mn, op_str, kind in found_calls[:80]:
        print(f"    0x{va:x}: {mn} {op_str}    [{kind}]")
    if len(found_calls) > 80:
        print(f"    ... ({len(found_calls)-80} more)")
    if found_loads_disp8:
        print(f"  --- `mov rXX, [reg+0x08]` loads (PATTERN B candidate) ---")
        for va, mn, op_str, dst, src in found_loads_disp8[:30]:
            print(f"    0x{va:x}: {mn} {op_str}    [dst={dst} src={src}]")


def main():
    text_base, text_data = load_prx_text()
    print(f"[+] text_base=0x{text_base:x}  size=0x{len(text_data):x}")
    for runtime_va, label in TARGETS:
        elf_va = runtime_va - PRX_RUNTIME_BASE
        disasm_function(text_data, text_base, elf_va, label)


if __name__ == "__main__":
    main()
