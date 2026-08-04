#!/usr/bin/env python3
"""EXP-039 Task 4: Find all writes to 0x801EE7610 (hash table pointer).

The hash table at 0x801EE7610 is NULL. Find all code that writes to it.
Also find writes to 0x801E51240 (the global that crash function reads).
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
targets = {
    0x801EE7610: "hash_table_ptr",
    0x801E51240: "global_ptr",
}

print("=== Searching for ALL code references to hash_table and global ===")
text_start = 0x4000
text_size = 0x1938C2C
chunk_size = 0x200000

for target_addr, target_name in targets.items():
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
                        if t == target_addr:
                            refs.append((insn.address, insn.mnemonic, insn.op_str, insn.bytes))
                            break
    
    print(f"\n  {target_name} (0x{target_addr:X}): {len(refs)} references")
    for addr, mnemonic, op_str, insn_bytes in refs[:30]:
        # Determine read vs write
        is_write = False
        is_lea = (mnemonic == "lea")
        if not is_lea and "," in op_str:
            first_op = op_str.split(",", 1)[0].strip()
            if "[" in first_op or "rip" in first_op:
                is_write = True
        kind = "WRITE" if is_write else ("LEA" if is_lea else "READ")
        print(f"    0x{addr:X}: {mnemonic} {op_str} [{kind}] (bytes: {insn_bytes.hex()})")

# Now search the PRX too
print("\n\n=== Searching Il2cppUserAssemblies.prx ===")
PRX = Path("/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx")
prx_data = PRX.read_bytes()
prx_base = 0x804CD5000

e_phoff = struct.unpack_from('<Q', prx_data, 0x20)[0]
e_phnum = struct.unpack_from('<H', prx_data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', prx_data, 0x36)[0]

# Find text segment
text_start_prx = None
text_size_prx = None
text_vaddr_prx = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', prx_data, off)[0]
    p_flags = struct.unpack_from('<I', prx_data, off + 4)[0]
    if p_type == 1 and (p_flags & 1):  # LOAD + X
        text_start_prx = struct.unpack_from('<Q', prx_data, off + 8)[0]
        text_size_prx = struct.unpack_from('<Q', prx_data, off + 32)[0]
        text_vaddr_prx = struct.unpack_from('<Q', prx_data, off + 16)[0]
        break

if text_start_prx:
    print(f"PRX text: offset=0x{text_start_prx:X} vaddr=0x{text_vaddr_prx:X} size=0x{text_size_prx:X}")
    
    for target_addr, target_name in targets.items():
        refs = []
        chunk_size = 0x200000
        for chunk_start in range(text_start_prx, text_start_prx + text_size_prx, chunk_size):
            chunk_end = min(chunk_start + chunk_size, text_start_prx + text_size_prx)
            chunk = prx_data[chunk_start:chunk_end]
            chunk_vaddr = chunk_start - text_start_prx + text_vaddr_prx + prx_base
            
            for insn in md.disasm(chunk, chunk_vaddr):
                for op in insn.operands:
                    if op.type == 3:  # X86_OP_MEM
                        if op.mem.base == 41:  # RIP
                            t = insn.address + insn.size + op.mem.disp
                            if t == target_addr:
                                refs.append((insn.address, insn.mnemonic, insn.op_str))
                                break
        
        print(f"\n  {target_name} (0x{target_addr:X}): {len(refs)} references in PRX")
        for addr, mnemonic, op_str in refs[:20]:
            is_write = False
            is_lea = (mnemonic == "lea")
            if not is_lea and "," in op_str:
                first_op = op_str.split(",", 1)[0].strip()
                if "[" in first_op or "rip" in first_op:
                    is_write = True
            kind = "WRITE" if is_write else ("LEA" if is_lea else "READ")
            print(f"    0x{addr:X}: {mnemonic} {op_str} [{kind}]")
