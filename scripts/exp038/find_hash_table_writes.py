#!/usr/bin/env python3
"""EXP-038: Find what writes to the hash table pointer at 0x801EE7610.

The hash table pointer at 0x801EE7610 is NULL. Find all code that
WRITES to this address. Also find what function is at [0x801EA49D8]
(the indirect call that leads to the crash function).
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Target addresses
HASH_TABLE_PTR = 0x801EE7610  # The hash table pointer that's NULL
GLOBAL_PTR = 0x801E51240      # The global that should be set
INDIRECT_CALL_GLOBAL = 0x801EA49D8  # The global used for call [rip+...] at 0x80134FA69

targets = [HASH_TABLE_PTR, GLOBAL_PTR, INDIRECT_CALL_GLOBAL]

print("=== Searching for ALL code references to key globals ===")
text_start = 0x4000
text_size = 0x1938C2C
chunk_size = 0x200000

for target in targets:
    refs = []
    for chunk_start in range(text_start, text_start + text_size, chunk_size):
        chunk_end = min(chunk_start + chunk_size, text_start + text_size)
        chunk = data[chunk_start:chunk_end]
        chunk_vaddr = chunk_start - 0x4000 + IMAGE_BASE
        
        for insn in md.disasm(chunk, chunk_vaddr):
            for op in insn.operands:
                if op.type == 3:  # X86_OP_MEM
                    if op.mem.base == 41:  # RIP
                        t = insn.address + insn.size + op.mem.disp
                        if t == target:
                            refs.append((insn.address, insn.mnemonic, insn.op_str))
                            break
    
    print(f"\n  0x{target:X}: {len(refs)} references")
    for addr, mnemonic, op_str in refs[:15]:
        # Determine read vs write
        is_write = False
        if "," in op_str:
            first_op = op_str.split(",", 1)[0].strip()
            if "rip" in first_op or "[" in first_op:
                is_write = True
        kind = "WRITE" if is_write else ("LEA" if mnemonic == "lea" else "READ")
        print(f"    0x{addr:X}: {mnemonic} {op_str} [{kind}]")

# Also check: what relocation is at 0x801EA49D8?
print(f"\n=== Relocation at 0x801EA49D8 (indirect call global) ===")
e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

dyn_foff = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type == 2:
        dyn_foff = struct.unpack_from('<Q', data, off + 8)[0]
        dyn_size = struct.unpack_from('<Q', data, off + 32)[0]
        break

rela_addr = rela_size = 0
i = 0
while i < dyn_size:
    d_tag, d_val = struct.unpack_from('<qQ', data, dyn_foff + i)
    if d_tag == 0: break
    if d_tag == 7: rela_addr = d_val
    elif d_tag == 8: rela_size = d_val
    i += 16

def vaddr_to_foff(vaddr):
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type != 1: continue
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        if p_vaddr <= vaddr < p_vaddr + p_filesz:
            return p_offset + (vaddr - p_vaddr)
    return None

rela_foff = vaddr_to_foff(rela_addr)

# Search for relocations at our target addresses
for target_name, target_vaddr in [("0x801EA49D8", 0x1EA49D8),
                                     ("0x801EE7610", 0x1EE7610),
                                     ("0x801E51240", 0x1E51240)]:
    print(f"\n  Relocations at {target_name}:")
    for i in range(0, rela_size, 24):
        r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
        if r_offset == target_vaddr:
            rel_type = r_info & 0xFFFFFFFF
            sym_idx = r_info >> 32
            type_names = {8: 'RELATIVE', 6: 'GLOB_DAT', 7: 'JUMP_SLOT', 1: 'R_X86_64_64'}
            runtime_val = IMAGE_BASE + r_addend if rel_type == 8 else r_addend
            print(f"    type={type_names.get(rel_type, rel_type)} sym={sym_idx} addend=0x{r_addend:X} -> runtime=0x{runtime_val:X}")
