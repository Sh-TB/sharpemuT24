#!/usr/bin/env python3
"""EXP-079: Examine slot 0x801CEEA08 (which stores ptr to dispatcher 0x800AC6080)."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def main():
    img = ElfImage(EBOOT_PATH)
    
    slot_runtime = 0x801CEEA08
    slot_vaddr = slot_runtime - PS5_BASE
    
    # What segment is this in?
    for seg in img.segments:
        if seg['p_type'] == 1 and seg['p_vaddr'] <= slot_vaddr < seg['p_vaddr'] + seg['p_memsz']:
            flags = ''
            if seg['p_flags'] & 4: flags += 'R'
            if seg['p_flags'] & 2: flags += 'W'
            if seg['p_flags'] & 1: flags += 'X'
            print(f"Slot 0x{slot_runtime:X} in segment: vaddr=0x{seg['p_vaddr']:X} memsz=0x{seg['p_memsz']:X} flags={flags}")
            break
    
    # Print 0x80 bytes around the slot
    print(f"\n=== Memory around slot 0x{slot_runtime:X} ===")
    start_vaddr = slot_vaddr - 0x40
    off = img.vaddr_to_offset(start_vaddr)
    if off:
        data = img.raw[off:off + 0x80]
        for i in range(0, len(data), 8):
            val = struct.unpack_from('<Q', data, i)[0]
            addr = start_vaddr + i + PS5_BASE
            marker = " ← DISPATCHER PTR (0x800AC6080)" if addr == slot_runtime else ""
            if 0x800000000 <= val < 0x8020695A0:
                marker += f" (→ code 0x{val:X})"
            elif 0x801000000 <= val < 0x802000000:
                marker += f" (→ data 0x{val:X})"
            print(f"  0x{addr:X}: 0x{val:016X}{marker}")
    
    # Find code that loads this slot
    print(f"\n=== Searching for code that loads slot 0x{slot_runtime:X} ===")
    lea_prefixes_64 = [b'\x48\x8d\x05', b'\x48\x8d\x0d', b'\x48\x8d\x15', b'\x48\x8d\x1d',
                       b'\x48\x8d\x2d', b'\x48\x8d\x35', b'\x48\x8d\x3d',
                       b'\x4c\x8d\x05', b'\x4c\x8d\x0d', b'\x4c\x8d\x15', b'\x4c\x8d\x1d',
                       b'\x4c\x8d\x25', b'\x4c\x8d\x2d', b'\x4c\x8d\x35', b'\x4c\x8d\x3d']
    mov_prefixes_64 = [b'\x48\x8b\x05', b'\x48\x8b\x0d', b'\x48\x8b\x15', b'\x48\x8b\x1d',
                       b'\x48\x8b\x2d', b'\x48\x8b\x35', b'\x48\x8b\x3d',
                       b'\x4c\x8b\x05', b'\x4c\x8b\x0d', b'\x4c\x8b\x15', b'\x4c\x8b\x1d',
                       b'\x4c\x8b\x25', b'\x4c\x8b\x2d', b'\x4c\x8b\x35', b'\x4c\x8b\x3d']
    
    found_lea = []
    found_mov = []
    for seg in img.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1): continue
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        for i in range(len(seg_data) - 7):
            for pfx in lea_prefixes_64:
                if seg_data[i:i+3] == pfx:
                    disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                    target = PS5_BASE + seg['p_vaddr'] + i + 7 + disp32
                    if target == slot_runtime:
                        found_lea.append((PS5_BASE + seg['p_vaddr'] + i, pfx.hex(), 'lea'))
                    break
            for pfx in mov_prefixes_64:
                if seg_data[i:i+3] == pfx:
                    disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                    target = PS5_BASE + seg['p_vaddr'] + i + 7 + disp32
                    if target == slot_runtime:
                        found_mov.append((PS5_BASE + seg['p_vaddr'] + i, pfx.hex(), 'mov'))
                    break
    
    print(f"  LEA refs to slot: {len(found_lea)}")
    for a, p, k in found_lea[:20]:
        print(f"    0x{a:X}: {k} ({p})")
    print(f"  MOV-load refs to slot: {len(found_mov)}")
    for a, p, k in found_mov[:20]:
        print(f"    0x{a:X}: {k} ({p})")
    
    # Disassemble around first hit if any
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for site_list, label in [(found_lea, "LEA"), (found_mov, "MOV")]:
        for site_addr, _, _ in site_list[:3]:
            print(f"\n=== Context around {label} at 0x{site_addr:X} ===")
            vaddr = site_addr - PS5_BASE
            data = img.read_bytes(vaddr - 64, 128)
            for ins in list(md.disasm(data, site_addr - 64))[:30]:
                if ins.address > site_addr + 16: break
                marker = ""
                if ins.mnemonic.startswith("call"): marker = " ← CALL"
                elif ins.mnemonic.startswith("j") and ins.mnemonic != "jmp": marker = " ← COND-JMP"
                elif ins.mnemonic == "jmp": marker = " ← JMP"
                elif ins.mnemonic == "ret": marker = " ← RET"
                op_str = ins.op_str
                for op in ins.operands:
                    if op.type == 2 and op.mem.base == 41:
                        target_addr = ins.address + ins.size + op.mem.disp
                        op_str += f"  ; → 0x{target_addr:X}"
                arrow = "  <<<" if ins.address == site_addr else ""
                print(f"  0x{ins.address:X}:  {ins.bytes.hex():24s}  {ins.mnemonic:8s} {op_str}{marker}{arrow}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
