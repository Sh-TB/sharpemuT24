#!/usr/bin/env python3
"""EXP-123 Task 1: Disassemble IL2CPP thread entry 0x804F88AA0 in Il2cppUserAssemblies.prx."""
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

PRX_PATH = '/tmp/exp118_games/yatzi/Il2cppUserAssemblies.prx'
PRX_BASE = 0x804CD5000
THREAD_ENTRY = 0x804F88AA0

with open(PRX_PATH, 'rb') as f:
    raw = f.read()
elf = ELFFile(BytesIO(raw))
text_base = None; text_data = None
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
        text_base = seg['p_vaddr']; text_data = seg.data(); break

entry_elf = THREAD_ENTRY - PRX_BASE
print(f"Thread entry: 0x{THREAD_ENTRY:x} (runtime) = 0x{entry_elf:x} (ELF VA)")
print()

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
chunk = text_data[entry_elf:entry_elf + 0x200]
print(f"=== Disassembly of 0x{THREAD_ENTRY:x} (first 0x200 bytes) ===")
print()
for ins in md.disasm(chunk, entry_elf + PRX_BASE):
    marker = ''
    if ins.mnemonic == 'call':
        op = ins.operands[0] if ins.operands else None
        if op and op.type == CS_OP_IMM:
            target = op.imm
            if target == 0x801937720: marker = '  <=== sceKernelWaitSema'
            elif target == 0x8019377b0: marker = '  <=== sceKernelSignalSema'
            else: marker = f'  <=== call 0x{target:x}'
        elif op and op.type == CS_OP_REG:
            marker = f'  <=== call {ins.reg_name(op.reg)} (indirect)'
        elif op and op.type == CS_OP_MEM:
            marker = '  <=== call [mem] (indirect)'
    if ins.mnemonic == 'mov' and len(ins.operands) >= 2:
        dst = ins.operands[0]
        if dst.type == CS_OP_MEM and dst.mem.base != 0:
            disp = dst.mem.disp
            if disp in (0x68, 0xB0, 0xF8, 0x100, 0x108):
                marker = f'  <=== WRITE [reg+0x{disp:x}]'
    print(f"  0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}{marker}")
    if ins.mnemonic in ('ret', 'ud2') and ins.address > THREAD_ENTRY + 0x10:
        break
