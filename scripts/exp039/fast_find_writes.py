#!/usr/bin/env python3
"""EXP-039 Task 4: Fast search for writes to 0x801EE7610 and 0x801E51240.

Instead of disassembling the entire text segment, scan for the RIP-relative
displacement bytes that would reference these addresses.

For a MOV [rip+disp32], reg instruction:
  48 89 XX YY YY YY YY (6-7 bytes)
  where disp32 = target - (insn_addr + insn_size)

We scan all text bytes and for each position, check if any valid instruction
encoding at that position would reference our target.
"""
import struct
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()

# For each address in text, the displacement needed to reach our target is:
# disp32 = target - (addr + 7)  for 7-byte instructions
# disp32 = target - (addr + 6)  for 6-byte instructions
# disp32 = target - (addr + 3)  for 3-byte instructions

targets = {
    0x801EE7610: "hash_table_ptr",
    0x801E51240: "global_ptr",
}

text_start = 0x4000
text_size = 0x1938C2C

print("=== Fast scan for RIP-relative references ===")
for target_addr, target_name in targets.items():
    # For 7-byte instructions (mov [rip+disp32], reg with REX.W)
    # Pattern: 48 89 XX <disp32> or 4C 89 XX <disp32>
    # The disp32 = target - (insn_vaddr + 7)
    
    found_7byte = []
    found_6byte = []
    
    for i in range(text_start, text_start + text_size - 7):
        insn_vaddr = i - 0x4000 + IMAGE_BASE
        
        # 7-byte: REX.W + opcode + modrm + disp32
        # REX.W = 0x48 or 0x4C
        if data[i] in (0x48, 0x4C):
            # Check for MOV [rip+disp32], reg (opcode 89) or MOV reg, [rip+disp32] (opcode 8B)
            if data[i+1] in (0x89, 0x8B):
                modrm = data[i+2]
                # modrm for [rip+disp32]: mod=00, rm=101
                if (modrm & 0xC7) == 0x05:
                    disp32 = struct.unpack_from('<i', data, i+3)[0]
                    effective = insn_vaddr + 7 + disp32
                    if effective == target_addr:
                        found_7byte.append((insn_vaddr, data[i+1], modrm))
        
        # 6-byte: no REX, opcode + modrm + disp32
        if data[i] in (0x89, 0x8B):
            modrm = data[i+1]
            if (modrm & 0xC7) == 0x05:
                disp32 = struct.unpack_from('<i', data, i+2)[0]
                effective = insn_vaddr + 6 + disp32
                if effective == target_addr:
                    found_6byte.append((insn_vaddr, data[i], modrm))
    
    print(f"\n  {target_name} (0x{target_addr:X}):")
    print(f"    7-byte refs: {len(found_7byte)}")
    for addr, opcode, modrm in found_7byte[:20]:
        # Determine read vs write
        # opcode 0x89 = MOV r/m, r (write to mem)
        # opcode 0x8B = MOV r, r/m (read from mem)
        kind = "WRITE" if opcode == 0x89 else "READ"
        # Determine register from modrm reg field
        reg_idx = ((modrm >> 3) & 7)
        rex_r = (data[addr - 0x800000000 + 0x4000] >> 2) & 1
        reg_names = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi',
                     'r8','r9','r10','r11','r12','r13','r14','r15']
        reg = reg_names[reg_idx + (8 if rex_r else 0)]
        print(f"      0x{addr:X}: MOV [{'mem' if opcode==0x89 else reg}], [{reg if opcode==0x89 else 'mem'}] [{kind}]")
    
    print(f"    6-byte refs: {len(found_6byte)}")
    for addr, opcode, modrm in found_6byte[:10]:
        kind = "WRITE" if opcode == 0x89 else "READ"
        print(f"      0x{addr:X}: [{kind}]")
