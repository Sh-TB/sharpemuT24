#!/usr/bin/env python3
"""EXP-043 Task 1: Exhaustive write tracing for 0x801E51240.

Previous scans only checked RIP-relative MOV [rip+disp32], reg.
Now search ALL possible write patterns:
1. mov [absolute], reg (rare in x86-64)
2. mov [reg+offset], reg where reg holds base of metadata struct
3. mov [reg+offset], imm
4. lea + store patterns
5. memcpy/memmove initialization

Also search for writes via register that holds 0x801E51240's address.
The address 0x801E51240 is in BSS. It might be written via:
- A register loaded with the address (lea rXX, [0x801E51240])
- A struct base + offset where the struct includes 0x801E51240
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000
TARGET_VADDR = 0x1E51240  # vaddr of 0x801E51240 (relative to image base)

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# Strategy: find ALL LEA instructions that compute 0x801E51240
# A LEA rXX, [rip+disp] that targets 0x801E51240 means the register
# will hold the address. A subsequent MOV [rXX], val would write to it.
# This catches indirect writes through a register.

print("=== Task 1: Exhaustive write tracing for 0x801E51240 ===")
print()

# Step 1: Find ALL LEA instructions targeting 0x801E51240
text_start = 0x4000
text_size = 0x1938C2C

lea_targets = []
chunk_size = 0x200000

for chunk_start in range(text_start, text_start + text_size, chunk_size):
    chunk_end = min(chunk_start + chunk_size, text_start + text_size)
    chunk = data[chunk_start:chunk_end]
    chunk_vaddr = chunk_start - 0x4000 + IMAGE_BASE
    
    for insn in md.disasm(chunk, chunk_vaddr):
        if insn.mnemonic == "lea":
            for op in insn.operands:
                if op.type == 3 and op.mem.base == 41:  # RIP-relative
                    target = insn.address + insn.size + op.mem.disp
                    if target == 0x801E51240:
                        # Found LEA targeting our global
                        reg_idx = (insn.reg_operand if hasattr(insn, 'reg_operand') else 0)
                        # Get destination register from op_str
                        dest_reg = insn.op_str.split(",")[0].strip()
                        lea_targets.append((insn.address, dest_reg))
                        break

print(f"LEA instructions targeting 0x801E51240: {len(lea_targets)}")
for addr, reg in lea_targets[:30]:
    print(f"  0x{addr:X}: lea {reg}, [0x801E51240]")

# Step 2: For each LEA, check if there's a subsequent MOV [reg], val
# within the next 20 instructions
print()
print("=== Checking for stores after LEA ===")
for lea_addr, dest_reg in lea_targets[:30]:
    # Disassemble next 200 bytes after the LEA
    offset = lea_addr - IMAGE_BASE + 0x4000
    chunk = data[offset:offset+200]
    found_store = False
    for insn in md.disasm(chunk, lea_addr):
        if insn.address == lea_addr:
            continue  # Skip the LEA itself
        # Check if this instruction writes to [dest_reg]
        if insn.mnemonic == "mov" and f"[{dest_reg}]" in insn.op_str:
            # Check if [dest_reg] is the destination (first operand)
            parts = insn.op_str.split(",", 1)
            if len(parts) > 0 and f"[{dest_reg}]" in parts[0]:
                print(f"  0x{lea_addr:X}: lea {dest_reg} → 0x{insn.address:X}: {insn.mnemonic} {insn.op_str}")
                found_store = True
                break
        if insn.mnemonic == "ret" or insn.mnemonic == "call":
            break
    if not found_store:
        # Check for MOV [reg+offset], val patterns where offset=0
        for insn in md.disasm(chunk, lea_addr):
            if insn.address == lea_addr:
                continue
            if insn.mnemonic == "mov" and dest_reg in insn.op_str:
                parts = insn.op_str.split(",", 1)
                if len(parts) > 0 and dest_reg in parts[0] and "[" in parts[0]:
                    print(f"  0x{lea_addr:X}: lea {dest_reg} → 0x{insn.address:X}: {insn.mnemonic} {insn.op_str}")
                    found_store = True
                    break
            if insn.mnemonic == "ret" or insn.mnemonic == "call":
                break

# Step 3: Also check PRX for writes
print()
print("=== Searching PRX for LEA targeting 0x801E51240 ===")
PRX = Path("/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx")
prx_data = PRX.read_bytes()
PRX_BASE = 0x804CD5000

e_phoff = struct.unpack_from('<Q', prx_data, 0x20)[0]
e_phnum = struct.unpack_from('<H', prx_data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', prx_data, 0x36)[0]

prx_text_start = prx_text_size = 0
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', prx_data, off)[0]
    p_flags = struct.unpack_from('<I', prx_data, off + 4)[0]
    if p_type == 1 and (p_flags & 1):
        prx_text_start = struct.unpack_from('<Q', prx_data, off + 8)[0]
        prx_text_size = struct.unpack_from('<Q', prx_data, off + 32)[0]
        prx_text_vaddr = struct.unpack_from('<Q', prx_data, off + 16)[0]
        break

prx_lea_count = 0
for i in range(prx_text_start, prx_text_start + prx_text_size - 7):
    insn_vaddr = i - prx_text_start + prx_text_vaddr + PRX_BASE
    if prx_data[i] in (0x48, 0x4C) and prx_data[i+1] == 0x8D:
        modrm = prx_data[i+2]
        if (modrm & 0xC7) == 0x05:  # [rip+disp32]
            disp32 = struct.unpack_from('<i', prx_data, i+3)[0]
            effective = insn_vaddr + 7 + disp32
            if effective == 0x801E51240:
                prx_lea_count += 1
                reg_idx = ((modrm >> 3) & 7)
                reg_names = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']
                reg = reg_names[reg_idx + (8 if prx_data[i] == 0x4C else 0)]
                print(f"  0x{insn_vaddr:X}: lea {reg}, [0x801E51240]")

print(f"PRX LEA count: {prx_lea_count}")
