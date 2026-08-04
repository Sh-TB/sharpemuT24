#!/usr/bin/env python3
"""EXP-125 Task 2/3: Analyze dispatcher function at 0x804F6E960 and find writes to [reg+0x90]."""
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

# Find function start by searching backward for push rbp after INT3
start_search = 0x804F6E960 - PRX_BASE
func_start = None
for off in range(start_search, start_search - 0x400, -1):
    if off < 0: break
    if text_data[off] == 0x55 and off > 0 and text_data[off-1] == 0xCC:
        chunk = text_data[off:off+4]
        if chunk[1] == 0x48 and chunk[2] == 0x89 and chunk[3] == 0xE5:
            func_start = off
            break
if not func_start:
    func_start = start_search - 0x40

# Disassemble the full function
chunk = text_data[func_start:func_start + 0x300]
print(f"=== Dispatcher function at 0x{func_start + PRX_BASE:x} ===\n")
for ins in md.disasm(chunk, func_start + PRX_BASE):
    marker = ''
    if ins.mnemonic == 'call' and ins.operands:
        op = ins.operands[0]
        if op.type == CS_OP_IMM:
            t = op.imm
            if t == 0x801937720: marker = '  <=== WaitSema'
            elif t == 0x8019377b0: marker = '  <=== SignalSema'
            else: marker = f'  <=== call 0x{t:x}'
        elif op.type == CS_OP_REG:
            marker = f'  <=== call {ins.reg_name(op.reg)}'
        elif op.type == CS_OP_MEM:
            marker = '  <=== call [mem]'
    # Highlight key offsets
    for op in ins.operands:
        if op.type == CS_OP_MEM and op.mem.base != 0:
            disp = op.mem.disp
            if disp == 0x88: marker += '  *** [reg+0x88] SEMA ***'
            elif disp == 0x90: marker += '  *** [reg+0x90] COUNTER ***'
    if ins.address == 0x804F6E9E6: marker += '  <=== WaitSema CALL'
    if ins.address == 0x804F6E9EB: marker += '  <=== STALL'
    print(f"  0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}{marker}")
    if ins.mnemonic in ('ret', 'ud2') and ins.address > func_start + PRX_BASE + 0x20:
        break
