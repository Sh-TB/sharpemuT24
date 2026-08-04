#!/usr/bin/env python3
"""EXP-037 Task 1: Identify the global pointer at [rip+0xaf33cc]."""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000
FILE_OFFSET_DELTA = 0x4000

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Compute global address
# 80135DE6D: mov rax, [rip + 0xaf33cc]  (7 bytes)
# RIP after = 0x80135DE74
global_addr = 0x80135DE74 + 0xAF33CC
print(f"=== Global pointer address ===")
print(f"  Global address: 0x{global_addr:X}")
print(f"  Vaddr: 0x{global_addr - IMAGE_BASE:X}")
print()

# Check segments
e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
e_phnum = struct.unpack_from("<H", data, 0x38)[0]

print(f"=== Segment check ===")
in_segment = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from("<I", data, off)[0]
    if p_type != 1: continue  # LOAD
    p_offset = struct.unpack_from("<Q", data, off + 8)[0]
    p_vaddr = struct.unpack_from("<Q", data, off + 16)[0]
    p_filesz = struct.unpack_from("<Q", data, off + 32)[0]
    p_memsz = struct.unpack_from("<Q", data, off + 40)[0]
    mapped_vaddr = p_vaddr + IMAGE_BASE
    mapped_end = mapped_vaddr + p_memsz
    if mapped_vaddr <= global_addr < mapped_end:
        file_off = p_offset + (global_addr - mapped_vaddr)
        print(f"  PH[{i}]: vaddr=0x{mapped_vaddr:X}..0x{mapped_end:X} offset=0x{p_offset:X}")
        print(f"  *** Global is in PH[{i}] ***")
        print(f"  *** File offset = 0x{file_off:X} ***")
        if file_off < len(data):
            val = struct.unpack_from("<Q", data, file_off)[0]
            print(f"  *** Value at load time: 0x{val:X} ***")
        else:
            print(f"  *** Beyond file size — in BSS (zero-initialized) ***")
        in_segment = i
        break

if in_segment is None:
    print(f"  Global 0x{global_addr:X} is NOT in any LOAD segment!")
print()

# Search for all RIP-relative references to this global
print(f"=== Searching for references to 0x{global_addr:X} ===")
text_start = 0x4000
text_size = 0x1938C2C
references = []
chunk_size = 0x200000

for chunk_start in range(text_start, text_start + text_size, chunk_size):
    chunk_end = min(chunk_start + chunk_size, text_start + text_size)
    chunk = data[chunk_start:chunk_end]
    chunk_vaddr = chunk_start - FILE_OFFSET_DELTA + IMAGE_BASE
    
    for insn in md.disasm(chunk, chunk_vaddr):
        for op in insn.operands:
            if op.type == 3:  # X86_OP_MEM
                if op.mem.base == 41:  # X86_REG_RIP
                    target = insn.address + insn.size + op.mem.disp
                    if target == global_addr:
                        references.append((insn.address, insn.mnemonic, insn.op_str))
                        break

print(f"Found {len(references)} references:")
for addr, mnemonic, op_str in references[:40]:
    # Determine read vs write: if memory operand (with [rip+...]) is first, it's a write
    is_write = False
    if "," in op_str:
        first_op = op_str.split(",", 1)[0].strip()
        if "rip" in first_op or "[" in first_op:
            is_write = True
    else:
        # Single operand instructions like 'lea'
        pass
    kind = "WRITE" if is_write else "READ/LEA"
    print(f"  0x{addr:X}: {mnemonic} {op_str} [{kind}]")
