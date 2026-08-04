#!/usr/bin/env python3
"""
EXP-121 Task 3b: Filter for 64-bit writes to [reg+0xF8] (function pointer writes).
These are the candidates that could write the task function pointer.

64-bit mov writes use REX.W prefix (0x48 or 0x49/0x4C/0x4D).
  mov [reg+0xF8], r64:  48 89 ModRM(disp32) F8 00 00 00
  mov [reg+0xF8], imm:  48 C7 ModRM(disp32) F8 00 00 00 imm32

We specifically look for:
1. REX.W prefix (0x48, 0x49, 0x4C, 0x4D) — 64-bit operation
2. Opcode 89 (mov r/m64, r64) or C7 (mov r/m64, imm32)
3. ModRM with mod=10 (disp32), any reg, any r/m (except rm=4 which needs SIB)
4. Displacement = 0xF8 0x00 0x00 0x00

Also look for writes specifically with base=rbx (the worker object register at crash).
"""
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EBOOT_PATH = '/tmp/exp118_games/yatzi/eboot.bin'
PRX_PATH = '/tmp/exp118_games/yatzi/Il2cppUserAssemblies.prx'
EBOOT_BASE = 0x800000000
PRX_BASE = 0x804CD5000

def load_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    elf = ELFFile(BytesIO(raw))
    for seg in elf.iter_segments():
        if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
            return seg['p_vaddr'], seg.data(), raw, elf
    return None, None, raw, elf

def find_64bit_writers_to_offset(text_data, text_base, target_offset=0xF8):
    """Find all 64-bit mov instructions that write to [reg + target_offset]."""
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
        # Try different instruction start positions (2-5 bytes before disp)
        for back in range(2, 6):
            start = idx - back
            if start < 0:
                continue
            chunk = text_data[start:start + back + 4 + 8]
            insns = list(md.disasm(chunk, text_base + start))
            if not insns:
                continue
            ins = insns[0]
            # Must be a mov or lea
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
            # Check if it's a 64-bit operation (REX.W prefix)
            # REX.W bytes: 0x48, 0x49, 0x4C, 0x4D (W bit set)
            first_byte = ins.bytes[0] if len(ins.bytes) > 0 else 0
            is_64bit = first_byte in (0x48, 0x49, 0x4C, 0x4D)
            if not is_64bit:
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
                'is_rbx': base_reg == 'rbx',
            })
            break
    return writers

print("=" * 78)
print("EXP-121 Task 3b: 64-bit writes to [reg+0xF8] (function pointer writes)")
print("=" * 78)

for name, path, base in [("eboot.bin", EBOOT_PATH, EBOOT_BASE), ("Il2cppUserAssemblies.prx", PRX_PATH, PRX_BASE)]:
    print(f"\n=== {name} (runtime base 0x{base:x}) ===")
    text_base, text_data, raw, elf = load_text(path)
    if text_data is None:
        print("  No exec segment found")
        continue
    writers = find_64bit_writers_to_offset(text_data, text_base, 0xF8)
    rbx_writers = [w for w in writers if w['is_rbx']]
    print(f"  Total 64-bit write-to-[reg+0xF8] sites: {len(writers)}")
    print(f"  Of which [rbx+0xF8]: {len(rbx_writers)}")
    print(f"\n  All 64-bit writes to [reg+0xF8]:")
    for w in writers:
        runtime = w['address'] + base
        marker = " <<< RBX" if w['is_rbx'] else ""
        print(f"    0x{runtime:x} (elf 0x{w['address']:x}): {w['bytes']:24s}  {w['mnemonic']:8s} {w['op_str']}  [src={w['src']}]{marker}")
