#!/usr/bin/env python3
"""EXP-039 Task 4b: Search PRX for writes to 0x801EE7610.

The hash table pointer at 0x801EE7610 is never written via RIP-relative
in eboot.bin. It must be written by the PRX (Il2cppUserAssemblies.prx).
"""
import struct
from pathlib import Path

PRX = Path("/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx")
IMAGE_BASE = 0x804CD5000

data = PRX.read_bytes()

# Find text segment
e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

text_start = None
text_size = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    p_flags = struct.unpack_from('<I', data, off + 4)[0]
    if p_type == 1 and (p_flags & 1):  # LOAD + X
        text_start = struct.unpack_from('<Q', data, off + 8)[0]
        text_size = struct.unpack_from('<Q', data, off + 32)[0]
        text_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        break

print(f"PRX text: offset=0x{text_start:X} vaddr=0x{text_vaddr:X} size=0x{text_size:X}")
print(f"PRX base: 0x{IMAGE_BASE:X}")

# Fast scan for RIP-relative references to 0x801EE7610
target_addr = 0x801EE7610

found_7byte = []
found_6byte = []

for i in range(text_start, text_start + text_size - 7):
    # In the PRX, the vaddr = i - text_start + text_vaddr + base
    insn_vaddr = i - text_start + text_vaddr + IMAGE_BASE
    
    if data[i] in (0x48, 0x4C):
        if data[i+1] in (0x89, 0x8B):
            modrm = data[i+2]
            if (modrm & 0xC7) == 0x05:  # [rip+disp32]
                disp32 = struct.unpack_from('<i', data, i+3)[0]
                effective = insn_vaddr + 7 + disp32
                if effective == target_addr:
                    found_7byte.append((insn_vaddr, data[i+1], modrm, data[i]))
    
    if data[i] in (0x89, 0x8B):
        modrm = data[i+1]
        if (modrm & 0xC7) == 0x05:
            disp32 = struct.unpack_from('<i', data, i+2)[0]
            effective = insn_vaddr + 6 + disp32
            if effective == target_addr:
                found_6byte.append((insn_vaddr, data[i], modrm))

print(f"\n=== hash_table_ptr (0x{target_addr:X}) in PRX ===")
print(f"7-byte refs: {len(found_7byte)}")
for addr, opcode, modrm, rex in found_7byte[:20]:
    kind = "WRITE" if opcode == 0x89 else "READ"
    reg_idx = ((modrm >> 3) & 7)
    rex_r = (rex >> 2) & 1
    reg_names = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi',
                 'r8','r9','r10','r11','r12','r13','r14','r15']
    reg = reg_names[reg_idx + (8 if rex_r else 0)]
    print(f"  0x{addr:X}: opcode=0x{opcode:02X} [{kind}] reg={reg}")

print(f"6-byte refs: {len(found_6byte)}")
for addr, opcode, modrm in found_6byte[:10]:
    kind = "WRITE" if opcode == 0x89 else "READ"
    print(f"  0x{addr:X}: opcode=0x{opcode:02X} [{kind}]")

# Also check: the PRX might reference the hash table via a DIFFERENT global
# that points TO 0x801EE7610. Let me check if 0x801EE7610 appears as a
# RELATIVE relocation addend anywhere.
print(f"\n=== Checking PRX relocations for addend = 0x1EE7610 ===")
dyn_foff = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type == 2:  # PT_DYNAMIC
        dyn_foff = struct.unpack_from('<Q', data, off + 8)[0]
        dyn_size = struct.unpack_from('<Q', data, off + 32)[0]
        break

if dyn_foff:
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
    if rela_foff:
        for i in range(0, rela_size, 24):
            r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
            # Check if addend points to 0x1EE7610 (relative to image base 0)
            # or if r_offset is 0x1EE7610
            if r_addend == 0x1EE7610 or r_offset == 0x1EE7610:
                print(f"  r_offset=0x{r_offset:X} addend=0x{r_addend:X}")
