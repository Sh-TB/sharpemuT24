#!/usr/bin/env python3
"""EXP-081: Find code that loads and calls the dispatcher function pointer at 0x801CEEA08."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

img = ElfImage('/tmp/games/yatzi/eboot.bin')
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

SLOT = 0x801CEEA08
PS5_BASE = 0x800000000

# Search for: mov reg, [rip+disp32] where target = 0x801CEEA08
# or: lea reg, [rip+disp32] where target = 0x801CEEA08
# Encoding: 48 8b XX disp32 (mov r64, [rip+disp32]) or 48 8d XX disp32 (lea)
mov_prefixes = [b'\x48\x8b', b'\x4c\x8b']
lea_prefixes = [b'\x48\x8d', b'\x4c\x8d']

found = []
for seg in img.segments:
    if seg['p_type'] != 1 or not (seg['p_flags'] & 1): continue
    seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
    for i in range(len(seg_data) - 7):
        for pfx in mov_prefixes + lea_prefixes:
            if seg_data[i:i+2] == pfx:
                # Check ModRM: mod=00, r/m=101 (RIP-relative)
                modrm = seg_data[i+2]
                if (modrm & 0xC7) == 0x05:  # mod=00, r/m=101
                    disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                    instr_runtime = PS5_BASE + seg['p_vaddr'] + i
                    target = instr_runtime + 7 + disp32
                    if target == SLOT:
                        found.append((instr_runtime, pfx, 'mov' if pfx in mov_prefixes else 'lea'))
                break

print(f"Found {len(found)} references to slot 0x{SLOT:X}:")
for addr, pfx, kind in found[:20]:
    # Disassemble around this address
    vaddr = addr - PS5_BASE
    data = img.read_bytes(vaddr - 16, 48)
    print(f"\n  {kind} at 0x{addr:X}:")
    for ins in md.disasm(data, addr - 16):
        if ins.address > addr + 16: break
        marker = " <<<" if ins.address == addr else ""
        print(f"    0x{ins.address:X}: {ins.bytes.hex():20s}  {ins.mnemonic:8s} {ins.op_str}{marker}")
