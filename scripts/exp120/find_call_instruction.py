#!/usr/bin/env python3
"""EXP-120 Task 2/3: Find the call instruction immediately before caller RIP 0x800AA01D4.
The caller RIP is the RETURN address (next instruction after the call).
So the call instruction ends at 0x800AA01D4. We need to find a call instruction
that ends exactly at 0x800AA01D4.

Strategy: disassemble from various start points before 0x800AA01D4 and find
an instruction that ends exactly at 0x800AA01D4.
"""
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EBOOT_PATH = '/tmp/exp118_games/yatzi/eboot.bin'
EBOOT_BASE = 0x800000000
CALLER_RIP = 0x800AA01D4  # return address — call instruction ends here

with open(EBOOT_PATH, 'rb') as f:
    raw = f.read()
elf = ELFFile(BytesIO(raw))

text_base = None
text_data = None
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
        text_base = seg['p_vaddr']
        text_data = seg.data()
        break

caller_elf_va = CALLER_RIP - EBOOT_BASE
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Try starting disassembly from various offsets before the caller RIP.
# x86_64 instructions are 1-15 bytes. A call instruction is typically 2-7 bytes.
# Try start offsets from caller_elf_va - 16 to caller_elf_va - 1.
print(f"=== Searching for call instruction ending at 0x{CALLER_RIP:x} ===\n")

found_calls = []
for back in range(1, 16):
    start_va = caller_elf_va - back
    start_off = start_va - text_base
    if start_off < 0:
        continue
    chunk = text_data[start_off:start_off + back + 16]
    insns = list(md.disasm(chunk, start_va + EBOOT_BASE))
    for ins in insns:
        ins_end = ins.address + ins.size
        if ins_end == CALLER_RIP and ins.mnemonic in ('call', 'jmp'):
            found_calls.append(ins)
            print(f"  FOUND: 0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}")
            # Show operand details
            for op in ins.operands:
                if op.type == CS_OP_REG:
                    print(f"    operand: register {ins.reg_name(op.reg)}")
                elif op.type == CS_OP_MEM:
                    mem = op.mem
                    base = ins.reg_name(mem.base) if mem.base else None
                    index = ins.reg_name(mem.index) if mem.index else None
                    disp = mem.disp
                    print(f"    operand: memory [base={base} index={index} disp=0x{disp & 0xffffffffffffffff:x}]")
                elif op.type == CS_OP_IMM:
                    print(f"    operand: immediate 0x{op.imm:x}")
            print(f"    instruction size: {ins.size} bytes")
            print()

if not found_calls:
    print("  No call/jmp instruction found ending at caller RIP.")
    print("  Trying wider scan (1-32 bytes before)...")
    for back in range(1, 33):
        start_va = caller_elf_va - back
        start_off = start_va - text_base
        if start_off < 0:
            continue
        chunk = text_data[start_off:start_off + back + 16]
        insns = list(md.disasm(chunk, start_va + EBOOT_BASE))
        for ins in insns:
            ins_end = ins.address + ins.size
            if ins_end == CALLER_RIP:
                print(f"  Instruction ending at caller RIP: 0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str} (size={ins.size})")

# Now disassemble a wider window around the most likely call site
# to show context
print(f"\n=== Full context around the call site (0x80 bytes before, 0x40 after) ===")
print(f"=== Disassembling from 0x{CALLER_RIP - 0x80:x} ===\n")
start_va = caller_elf_va - 0x80
start_off = start_va - text_base
chunk = text_data[start_off:start_off + 0xC0]
for ins in md.disasm(chunk, start_va + EBOOT_BASE):
    marker = ''
    if ins.address + ins.size == CALLER_RIP and ins.mnemonic in ('call', 'jmp'):
        marker = '  <=== THIS IS THE CALL TO NULL (ends at caller RIP)'
        for op in ins.operands:
            if op.type == CS_OP_REG:
                marker += f' reg={ins.reg_name(op.reg)}'
            elif op.type == CS_OP_MEM:
                mem = op.mem
                base = ins.reg_name(mem.base) if mem.base else None
                disp = mem.disp
                marker += f' mem[{base}+0x{disp & 0xffffffffffffffff:x}]'
    elif ins.address == CALLER_RIP:
        marker = '  <--- caller ret addr'
    print(f"  0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}{marker}")
