#!/usr/bin/env python3
"""
EXP-121 Task 3: Search eboot.bin and Il2cppUserAssemblies.prx for all
instructions that write to [reg+0xF8] (the task function pointer field).
"""
import re
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EBOOT_PATH = '/tmp/exp118_games/yatzi/eboot.bin'
PRX_PATH = '/tmp/exp118_games/yatzi/Il2cppUserAssemblies.prx'

def load_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    elf = ELFFile(BytesIO(raw))
    for seg in elf.iter_segments():
        if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
            return seg['p_vaddr'], seg.data(), raw, elf
    return None, None, raw, elf

def find_writers_to_offset(text_data, text_base, target_offset=0xF8):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    disp_bytes = struct.pack('<I', target_offset)
    writers = []
    n = len(text_data)
    pos = 0
    while pos < n - 6:
        idx = text_data.find(disp_bytes, pos)
        if idx < 0:
            break
        pos = idx + 1
        for back in range(1, 5):
            start = idx - back
            if start < 0:
                continue
            chunk = text_data[start:start + back + 4 + 4]
            insns = list(md.disasm(chunk, text_base + start))
            if not insns:
                continue
            ins = insns[0]
            if ins.mnemonic not in ('mov', 'movabs', 'lea'):
                continue
            ops = ins.operands
            if len(ops) < 2:
                continue
            dst = ops[0]
            if dst.type != CS_OP_MEM:
                continue
            mem = dst.mem
            if mem.disp != target_offset:
                continue
            if mem.base == 0:
                continue
            base_reg = ins.reg_name(mem.base)
            src_desc = ""
            src = ops[1]
            if src.type == CS_OP_REG:
                src_desc = f"reg:{ins.reg_name(src.reg)}"
            elif src.type == CS_OP_IMM:
                src_desc = f"imm:0x{src.imm:x}"
            elif src.type == CS_OP_MEM:
                src_desc = f"mem"
            writers.append({
                'address': ins.address,
                'mnemonic': ins.mnemonic,
                'op_str': ins.op_str,
                'bytes': ins.bytes.hex(),
                'base_reg': base_reg,
                'src': src_desc,
            })
            break
    return writers

print("=" * 78)
print("EXP-121 Task 3: Search for writes to [reg+0xF8]")
print("=" * 78)

for name, path in [("eboot.bin", EBOOT_PATH), ("Il2cppUserAssemblies.prx", PRX_PATH)]:
    print(f"\n=== {name} ===")
    text_base, text_data, raw, elf = load_text(path)
    if text_data is None:
        print("  No exec segment found")
        continue
    print(f"  Exec Segment: vaddr=0x{text_base:x} size=0x{len(text_data):x}")
    writers = find_writers_to_offset(text_data, text_base, 0xF8)
    print(f"  Found {len(writers)} write-to-[reg+0xF8] sites:")
    for w in writers[:50]:
        print(f"    0x{w['address']:x}: {w['bytes']:24s}  {w['mnemonic']:8s} {w['op_str']}  [base={w['base_reg']} src={w['src']}]")
    if len(writers) > 50:
        print(f"    ... ({len(writers)-50} more)")
