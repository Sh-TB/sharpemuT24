#!/usr/bin/env python3
"""
EXP-122 Task 1: Find non-zero 64-bit writes to [reg+0xF8] and [reg+0x100].
Filter out stack writes. Focus on writes where reg is likely the Worker object.
"""
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EBOOT_PATH = '/tmp/exp118_games/yatzi/eboot.bin'
PRX_PATH = '/tmp/exp118_games/yatzi/Il2cppUserAssemblies.prx'
EBOOT_BASE = 0x800000000
PRX_BASE = 0x804CD5000
STACK_REGS = {'rsp', 'rbp', 'r12'}

def load_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    elf = ELFFile(BytesIO(raw))
    for seg in elf.iter_segments():
        if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
            return seg['p_vaddr'], seg.data(), raw, elf
    return None, None, raw, elf

def find_nonzero_writes(text_data, text_base, target_offset, base_runtime):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    disp_bytes = struct.pack('<I', target_offset)
    writers = []
    n = len(text_data)
    pos = 0
    while pos < n - 8:
        idx = text_data.find(disp_bytes, pos)
        if idx < 0:
            break
        pos = idx + 1
        for back in range(2, 6):
            start = idx - back
            if start < 0:
                continue
            chunk = text_data[start:start + back + 4 + 8]
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
            first_byte = ins.bytes[0] if len(ins.bytes) > 0 else 0
            if first_byte not in (0x48, 0x49, 0x4C, 0x4D):
                continue
            base_reg = ins.reg_name(mem.base)
            if base_reg in STACK_REGS:
                continue
            src = ops[1]
            src_desc = ""
            is_nonzero = False
            if src.type == CS_OP_REG:
                src_desc = f"reg:{ins.reg_name(src.reg)}"
                is_nonzero = True
            elif src.type == CS_OP_IMM:
                src_desc = f"imm:0x{src.imm:x}"
                is_nonzero = src.imm != 0
            elif src.type == CS_OP_MEM:
                src_desc = f"mem:[{ins.reg_name(src.mem.base) if src.mem.base else ''}+0x{src.mem.disp:x}]"
                is_nonzero = True
            if not is_nonzero:
                continue
            writers.append({
                'address': ins.address + base_runtime,
                'elf_va': ins.address,
                'mnemonic': ins.mnemonic,
                'op_str': ins.op_str,
                'bytes': ins.bytes.hex(),
                'base_reg': base_reg,
                'src': src_desc,
                'src_type': 'reg' if src.type == CS_OP_REG else ('imm' if src.type == CS_OP_IMM else 'mem'),
            })
            break
    return writers

print("=" * 78)
print("EXP-122 Task 1: Non-zero 64-bit writes to [reg+0xF8] and [reg+0x100]")
print("(excluding stack writes)")
print("=" * 78)

for name, path, base in [("eboot.bin", EBOOT_PATH, EBOOT_BASE), ("Il2cppUserAssemblies.prx", PRX_PATH, PRX_BASE)]:
    print(f"\n{'='*78}")
    print(f"=== {name} (runtime base 0x{base:x}) ===")
    print(f"{'='*78}")
    text_base, text_data, raw, elf = load_text(path)
    if text_data is None:
        print("  No exec segment found")
        continue
    for offset, field_name in [(0xF8, "func_ptr"), (0x100, "arg")]:
        writers = find_nonzero_writes(text_data, text_base, offset, base)
        by_reg = {}
        for w in writers:
            by_reg.setdefault(w['base_reg'], []).append(w)
        print(f"\n  --- [reg+0x{offset:x}] ({field_name}) — {len(writers)} non-zero 64-bit writes ---")
        for reg in sorted(by_reg.keys(), key=lambda r: -len(by_reg[r])):
            ws = by_reg[reg]
            print(f"    {reg}: {len(ws)} writes")
            for w in ws[:15]:
                src_marker = ""
                if w['src_type'] == 'imm':
                    src_marker = " (CONSTANT)"
                elif w['src_type'] == 'mem':
                    src_marker = " (from memory)"
                print(f"      0x{w['address']:x}: {w['bytes']:24s}  {w['mnemonic']:8s} {w['op_str']}{src_marker}")
            if len(ws) > 15:
                print(f"      ... ({len(ws)-15} more)")
