#!/usr/bin/env python3
"""EXP-120 Task 2/3: Disassemble around caller RIP 0x800AA01D4 in eboot.bin
to find the exact instruction that transferred control to NULL."""
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EBOOT_PATH = '/tmp/exp118_games/yatzi/eboot.bin'
EBOOT_BASE = 0x800000000
CALLER_RIP = 0x800AA01D4

with open(EBOOT_PATH, 'rb') as f:
    raw = f.read()
elf = ELFFile(BytesIO(raw))

text_base = None
text_data = None
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
        text_base = seg['p_vaddr']
        text_data = seg.data()
        print(f"Exec segment: vaddr=0x{text_base:x} size=0x{len(text_data):x}")
        break

caller_elf_va = CALLER_RIP - EBOOT_BASE
print(f"Caller RIP: 0x{CALLER_RIP:x} (runtime) = 0x{caller_elf_va:x} (ELF VA)")

if not (text_base <= caller_elf_va < text_base + len(text_data)):
    print(f"ERROR: caller not in exec segment")
    exit(1)

start_va = caller_elf_va - 0x100
end_va = caller_elf_va + 0x40
start_off = start_va - text_base
chunk = text_data[start_off:start_off + (end_va - start_va)]

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

print(f"\n=== Disassembly 0x{start_va + EBOOT_BASE:x} .. 0x{end_va + EBOOT_BASE:x} ===")
print(f"(caller RIP 0x{CALLER_RIP:x} is the return address — instruction AFTER the call to NULL)\n")

for ins in md.disasm(chunk, start_va + EBOOT_BASE):
    marker = ''
    if ins.address == CALLER_RIP:
        marker = '  <--- CALLER RET ADDR (instruction AFTER the call to NULL)'
    if ins.mnemonic in ('call', 'jmp') and ins.address >= CALLER_RIP - 0x20 and ins.address < CALLER_RIP:
        ops_detail = []
        for op in ins.operands:
            if op.type == CS_OP_REG:
                ops_detail.append(f"reg:{ins.reg_name(op.reg)}")
            elif op.type == CS_OP_MEM:
                mem = op.mem
                base = ins.reg_name(mem.base) if mem.base else None
                index = ins.reg_name(mem.index) if mem.index else None
                disp = mem.disp
                ops_detail.append(f"mem[base={base} idx={index} disp=0x{disp & 0xffffffffffffffff:x}]")
            elif op.type == CS_OP_IMM:
                ops_detail.append(f"imm:0x{op.imm:x}")
        marker += f'  <=== LIKELY THE CALL TO NULL  ops={ops_detail}'
    print(f"  0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}{marker}")
