#!/usr/bin/env python3
"""
EXP-121 Task 3c: Find the worker object allocation/initialization site.
Search for RIP-relative lea instructions that compute the worker function
address 0x800AA0170, which is stored at [worker_obj+0x28].
"""
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EBOOT_PATH = '/tmp/exp118_games/yatzi/eboot.bin'
EBOOT_BASE = 0x800000000
WORKER_FUNC = 0x800AA0170

with open(EBOOT_PATH, 'rb') as f:
    raw = f.read()
elf = ELFFile(BytesIO(raw))
text_base = None; text_data = None
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 1):
        text_base = seg['p_vaddr']; text_data = seg.data(); break

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# The worker function address is 0x800AA0170.
# RIP-relative lea: 8D ModRM(mod=00, rm=101) disp32
# target = rip + insn_size + disp32
# So disp32 = target - (insn_addr + insn_size)
# insn_size for lea r64, [rip+disp32] = 7 bytes (REX.W + 8D + ModRM + 4-byte disp)
# So disp32 = 0x800AA0170 - (insn_addr + 7)
# = 0x800AA0170 - insn_addr - 7

# We search for all lea instructions and check if they compute 0x800AA0170.
# To make this fast, we scan the text for the pattern:
#   [REX.W] 8D ModRM(00, reg, 101) disp32
# REX.W = 0x48 or 0x4C (for r8-r15)
# ModRM for rip-relative: mod=00, rm=101 → ModRM & 0xC7 == 0x05
# So ModRM is 0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D (for reg=0-7)
# With REX.R (0x4C): reg=8-15 → ModRM 0x05, 0x0D, ...

print(f"Searching for lea r64, [rip+disp32] instructions that compute 0x{WORKER_FUNC:x}...")
print()

n = len(text_data)
found = []
pos = 0
while pos < n - 7:
    # Check for REX.W prefix
    if text_data[pos] in (0x48, 0x4C):
        # Check for opcode 8D (lea)
        if text_data[pos + 1] == 0x8D:
            modrm = text_data[pos + 2]
            # Check for rip-relative (mod=00, rm=101)
            if (modrm & 0xC7) == 0x05:
                # Read disp32
                disp32 = struct.unpack_from('<i', text_data, pos + 3)[0]
                insn_addr = text_base + pos
                insn_size = 7
                target = insn_addr + insn_size + disp32 + EBOOT_BASE
                if target == WORKER_FUNC:
                    reg_field = (modrm >> 3) & 0x07
                    if text_data[pos] == 0x4C:
                        reg_name = f"r{8 + reg_field}"
                    else:
                        reg_names = ['rax', 'rcx', 'rdx', 'rbx', 'rsp', 'rbp', 'rsi', 'rdi']
                        reg_name = reg_names[reg_field]
                    found.append({
                        'addr': insn_addr + EBOOT_BASE,
                        'elf_va': insn_addr,
                        'reg': reg_name,
                        'disp': disp32,
                        'bytes': text_data[pos:pos+7].hex(),
                    })
    pos += 1

print(f"Found {len(found)} lea instructions that compute 0x{WORKER_FUNC:x}:")
for f in found:
    print(f"  0x{f['addr']:x} (elf 0x{f['elf_va']:x}): {f['bytes']:14s}  lea {f['reg']}, [rip+0x{f['disp'] & 0xffffffff:x}]  -> 0x{WORKER_FUNC:x}")

# Now disassemble around each found site to see the full initialization
print()
print("=== Disassembly context around each lea (looking for nearby mov [reg+0x28]) ===")
for f in found:
    print(f"\n--- Around 0x{f['addr']:x} ---")
    start = f['elf_va'] - 0x40
    if start < 0: start = 0
    chunk = text_data[start:start + 0x100]
    for ins in md.disasm(chunk, start + EBOOT_BASE):
        marker = ''
        if ins.address == f['addr']:
            marker = '  <=== lea worker_func'
        # Highlight writes to [reg+0x28] (the field that stores the worker func)
        if ins.mnemonic == 'mov' and len(ins.operands) >= 2:
            dst = ins.operands[0]
            if dst.type == CS_OP_MEM and dst.mem.disp == 0x28 and dst.mem.base != 0:
                marker += '  <=== write to [reg+0x28]'
        # Highlight writes to [reg+0xF8]
        if ins.mnemonic == 'mov' and len(ins.operands) >= 2:
            dst = ins.operands[0]
            if dst.type == CS_OP_MEM and dst.mem.disp == 0xF8 and dst.mem.base != 0:
                marker += '  <=== write to [reg+0xF8]'
        print(f"  0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}{marker}")
