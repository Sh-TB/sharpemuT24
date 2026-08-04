#!/usr/bin/env python3
"""EXP-081 TASK 2: Find ALL writes to [reg+0xF8] in EBOOT executable segment."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

img = ElfImage('/tmp/games/yatzi/eboot.bin')
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

print("=== All writes to [reg+0xF8] in EBOOT ===")
print("(filtering: mov/qword/dword/byte [reg+0xF8], <src>)")
print()

# Byte-pattern scan for disp32 = 0x000000F8 = F8 00 00 00
writes = []
for seg in img.segments:
    if seg['p_type'] != 1 or not (seg['p_flags'] & 1): continue
    seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
    seg_vaddr_runtime = 0x800000000 + seg['p_vaddr']
    
    i = 0
    while i < len(seg_data) - 7:
        # Look for disp32 = F8 00 00 00
        if seg_data[i:i+4] == b'\xf8\x00\x00\x00':
            # Check various instruction encodings
            # MOV r/m, r64: 48 89 ModRM(mod=10) disp32  or  4C 89 ...
            # MOV r/m, imm32: 48 C7 ModRM(mod=10) disp32 imm32
            # MOV r/m8, imm8: C6 ModRM(mod=10) disp32 imm8
            for back in range(2, 8):
                if i - back < 0: break
                chunk = seg_data[i-back:i+8]
                insns = list(md.disasm(chunk, seg_vaddr_runtime + i - back))
                for ins in insns:
                    if ins.address <= seg_vaddr_runtime + i < ins.address + ins.size:
                        if '0xf8]' in ins.op_str or '0xF8]' in ins.op_str:
                            parts = ins.op_str.split(',', 1)
                            if len(parts) == 2 and '0xf8]' in parts[0].lower():
                                writes.append((ins.address, ins.mnemonic, ins.op_str, ins.bytes.hex()))
                        break
            i += 4
        else:
            i += 1

# Deduplicate
seen = set()
unique_writes = []
for addr, mn, ops, hex_b in writes:
    if addr not in seen:
        seen.add(addr)
        unique_writes.append((addr, mn, ops, hex_b))

print(f"Total unique write-to-[reg+0xF8] sites: {len(unique_writes)}")
print()

# Categorize by type
qword_writes = [(a,m,o,h) for a,m,o,h in unique_writes if 'qword' in o]
dword_writes = [(a,m,o,h) for a,m,o,h in unique_writes if 'dword' in o]
byte_writes = [(a,m,o,h) for a,m,o,h in unique_writes if 'byte' in o]
other_writes = [(a,m,o,h) for a,m,o,h in unique_writes if 'qword' not in o and 'dword' not in o and 'byte' not in o]

print(f"Qword writes (mov qword [reg+0xF8], ...): {len(qword_writes)}")
print(f"Dword writes: {len(dword_writes)}")
print(f"Byte writes: {len(byte_writes)}")
print(f"Other: {len(other_writes)}")
print()

print("=== Qword writes to [reg+0xF8] (first 30) ===")
for addr, mn, ops, hex_b in sorted(qword_writes)[:30]:
    print(f"  0x{addr:X}: {hex_b:24s}  {mn} {ops}")

# Also check for vmovups writes to [reg+0xF8] (SIMD zeroing)
print()
print("=== vmovups/xmm writes to [reg+0xF8] (zeroing) ===")
for addr, mn, ops, hex_b in sorted(unique_writes):
    if 'xmm' in ops.lower() and '0xf8]' in ops.lower():
        print(f"  0x{addr:X}: {hex_b:24s}  {mn} {ops}")
