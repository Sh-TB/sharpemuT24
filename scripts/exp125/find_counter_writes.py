#!/usr/bin/env python3
"""
EXP-125 Task 3: Search for code that INCREMENTS [reg+0x90] (the counter).
The dispatcher at 0x804F6E978 does `lock xadd [r14+0x90], eax` with eax=0xFFFFFFFF (-1),
which DECREMENTS the counter. We need to find the code that INCREMENTS it.
Increment would be: lock xadd [reg+0x90], 1 or lock inc [reg+0x90] or lock add [reg+0x90], 1
"""
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

PRX_PATH = '/tmp/exp118_games/yatzi/Il2cppUserAssemblies.prx'
PRX_BASE = 0x804CD5000

with open(PRX_PATH, 'rb') as f:
    raw = f.read()
elf = ELFFile(BytesIO(raw))
text_base = None; text_data = None
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
        text_base = seg['p_vaddr']; text_data = seg.data(); break

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Search for all instructions that write to [reg+0x90]
# disp32 for 0x90 = 0x90 0x00 0x00 0x00
disp_bytes = struct.pack('<I', 0x90)
writers = []
n = len(text_data)
pos = 0
while pos < n - 8:
    idx = text_data.find(disp_bytes, pos)
    if idx < 0:
        break
    pos = idx + 1
    for back in range(1, 8):
        start = idx - back
        if start < 0: continue
        chunk = text_data[start:start + back + 4 + 8]
        insns = list(md.disasm(chunk, start + PRX_BASE))
        if not insns: continue
        ins = insns[0]
        # Check if this instruction accesses [reg+0x90]
        for op in ins.operands:
            if op.type == CS_OP_MEM and op.mem.disp == 0x90 and op.mem.base != 0:
                base_reg = ins.reg_name(op.mem.base)
                if base_reg in ('rsp', 'rbp', 'r12'): continue  # skip stack
                # Check if it's a write (destination operand)
                is_write = (op == ins.operands[0]) if ins.operands else False
                # Check if it's an increment (lock xadd with positive value, lock inc, lock add)
                is_increment = False
                if ins.mnemonic == 'xadd' and 'lock' in ins.bytes.hex():
                    # xadd swaps and adds — if the register value is positive, it's an increment
                    is_increment = True
                elif ins.mnemonic == 'inc' and 'lock' in ins.bytes.hex():
                    is_increment = True
                elif ins.mnemonic == 'add' and 'lock' in ins.bytes.hex():
                    is_increment = True
                elif ins.mnemonic == 'xadd':
                    is_increment = True  # might be increment
                
                writers.append({
                    'address': ins.address,
                    'mnemonic': ins.mnemonic,
                    'op_str': ins.op_str,
                    'bytes': ins.bytes.hex(),
                    'base_reg': base_reg,
                    'is_write': is_write,
                    'is_increment': is_increment,
                    'has_lock': ins.bytes[0] == 0xF0 or (len(ins.bytes) > 1 and ins.bytes[1] == 0xF0),
                })
                break
    break  # only first match per position

# Also search more carefully for lock xadd/inc/add with disp 0x90
print("=== All instructions accessing [reg+0x90] (non-stack) ===")
print(f"Found {len(writers)} sites")
for w in writers:
    inc_marker = ' *** INCREMENT ***' if w['is_increment'] else ''
    lock_marker = ' [LOCK]' if w['has_lock'] else ''
    print(f"  0x{w['address']:x}: {w['bytes']:24s}  {w['mnemonic']:8s} {w['op_str']}  [base={w['base_reg']}]{lock_marker}{inc_marker}")
