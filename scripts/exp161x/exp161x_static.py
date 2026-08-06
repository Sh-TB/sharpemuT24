#!/usr/bin/env python3
"""
EXP-161X: Cross-validation static analysis.
Check both 0x801E518C8 and 0x801D1E558 in eboot AND PRX.
"""

import struct

EBOOT_PATH = "/tmp/exp158_games/eboot.bin"
PRX_PATH = "/tmp/exp158_games/Il2cppUserAssemblies.prx"
EBOOT_BASE = 0x800000000
PRX_BASE = 0x804CD5000

TARGETS = [
    ("0x801E518C8 (Chain A)", 0x801E518C8),
    ("0x801D1E558 (Chain B)", 0x801D1E558),
    ("0x801E51240 (Global)", 0x801E51240),
]

def parse_elf64(path):
    data = open(path, 'rb').read()
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_flags = struct.unpack_from('<I', data, off + 4)[0]
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        p_memsz = struct.unpack_from('<Q', data, off + 40)[0]
        segments.append({'type': p_type, 'flags': p_flags, 'offset': p_offset,
                         'vaddr': p_vaddr, 'filesz': p_filesz, 'memsz': p_memsz})
    return data, segments

def check_address(data, segments, addr, base, binary_name):
    """Check if address is mapped, find its location and value."""
    vaddr = addr - base
    for seg in segments:
        if seg['type'] == 1:
            end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= vaddr < end:
                file_backed = seg['vaddr'] + seg['filesz']
                flags = ''
                if seg['flags'] & 1: flags += 'X'
                if seg['flags'] & 2: flags += 'W'
                if seg['flags'] & 4: flags += 'R'
                if vaddr < file_backed:
                    foff = seg['offset'] + (vaddr - seg['vaddr'])
                    val = struct.unpack_from('<Q', data, foff)[0] if foff + 8 <= len(data) else 0
                    return f"FILE-BACKED ({flags}), value=0x{val:X}, file_offset=0x{foff:X}"
                else:
                    return f"BSS ({flags}), value=0x0 at runtime"
    return f"NOT MAPPED (vaddr 0x{vaddr:X} not in any segment)"

def search_writes(data, segments, target_addr, base, binary_name):
    """Search for RIP-relative write instructions to target_addr."""
    writes = []
    write_opcodes = {0xC6, 0xC7, 0x89, 0x88, 0x80, 0x81, 0x83}
    
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(seg_data) - 11):
            for prefix_len in range(0, 2):
                if prefix_len == 1:
                    p = seg_data[i]
                    if p not in (0xF0, 0x48, 0x4C, 0x66):
                        continue
                opcode_offset = prefix_len
                if i + opcode_offset >= len(seg_data):
                    continue
                opcode = seg_data[i + opcode_offset]
                if opcode not in write_opcodes:
                    continue
                modrm_offset = opcode_offset + 1
                if i + modrm_offset >= len(seg_data):
                    continue
                modrm = seg_data[i + modrm_offset]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod != 0 or rm != 5:
                    continue
                disp_offset = modrm_offset + 1
                if i + disp_offset + 4 > len(seg_data):
                    continue
                disp = struct.unpack_from('<i', seg_data, i + disp_offset)[0]
                reg = (modrm >> 3) & 7
                base_len = disp_offset + 4
                imm_len = 0
                if opcode in (0xC6, 0x80, 0x83):
                    imm_len = 1
                elif opcode in (0xC7, 0x81):
                    imm_len = 4
                instr_len = base_len + imm_len
                instr_addr = base + seg['vaddr'] + i
                computed = instr_addr + instr_len + disp
                if computed == target_addr:
                    is_cmp = (opcode in (0x80, 0x81, 0x83) and reg == 7)
                    if is_cmp:
                        continue
                    writes.append(instr_addr)
                    break
    return writes

def search_reads(data, segments, target_addr, base, binary_name):
    """Search for RIP-relative reads (mov reg, [rip+disp32]) from target_addr."""
    reads = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(seg_data) - 7):
            b0 = seg_data[i]
            b1 = seg_data[i + 1] if i + 1 < len(seg_data) else 0
            if b0 in (0x48, 0x4C) and b1 == 0x8B:
                modrm = seg_data[i + 2]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod == 0 and rm == 5:
                    disp = struct.unpack_from('<i', seg_data, i + 3)[0]
                    instr_addr = base + seg['vaddr'] + i
                    computed = instr_addr + 7 + disp
                    if computed == target_addr:
                        reads.append(instr_addr)
            # Also check CMP byte [rip+disp32], imm8 (83 3D)
            if b0 == 0x83 and b1 == 0x3D:
                disp = struct.unpack_from('<i', seg_data, i + 2)[0]
                instr_addr = base + seg['vaddr'] + i
                computed = instr_addr + 7 + disp
                if computed == target_addr:
                    reads.append(instr_addr)
    return reads

def search_64bit_constant(data, segments, target_addr, base):
    """Search for the address as a 64-bit constant in data sections."""
    target_bytes = struct.pack('<Q', target_addr)
    hits = []
    for seg in segments:
        if seg['type'] != 1:
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(target_bytes, idx)
            if i == -1:
                break
            runtime = base + seg['vaddr'] + i
            hits.append(runtime)
            idx = i + 1
    return hits

def main():
    print("=" * 80)
    print("EXP-161X: Cross-Validation Static Analysis")
    print("=" * 80)
    
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    
    for label, addr in TARGETS:
        print(f"\n{'='*80}")
        print(f"  {label}")
        print(f"{'='*80}")
        
        # Check in eboot
        eboot_loc = check_address(eboot_data, eboot_segs, addr, EBOOT_BASE, "eboot")
        print(f"\n  Eboot: {eboot_loc}")
        
        eboot_writes = search_writes(eboot_data, eboot_segs, addr, EBOOT_BASE, "eboot")
        print(f"  Eboot writes: {len(eboot_writes)}")
        for w in eboot_writes[:5]:
            print(f"    0x{w:X}")
        
        eboot_reads = search_reads(eboot_data, eboot_segs, addr, EBOOT_BASE, "eboot")
        print(f"  Eboot reads: {len(eboot_reads)}")
        
        eboot_consts = search_64bit_constant(eboot_data, eboot_segs, addr, EBOOT_BASE)
        print(f"  Eboot 64-bit constants: {len(eboot_consts)}")
        for c in eboot_consts[:3]:
            print(f"    0x{c:X}")
        
        # Check in PRX
        prx_loc = check_address(prx_data, prx_segs, addr, PRX_BASE, "PRX")
        print(f"\n  PRX: {prx_loc}")
        
        prx_writes = search_writes(prx_data, prx_segs, addr, PRX_BASE, "PRX")
        print(f"  PRX writes: {len(prx_writes)}")
        for w in prx_writes[:5]:
            print(f"    0x{w:X}")
        
        prx_reads = search_reads(prx_data, prx_segs, addr, PRX_BASE, "PRX")
        print(f"  PRX reads: {len(prx_reads)}")
        
        prx_consts = search_64bit_constant(prx_data, prx_segs, addr, PRX_BASE)
        print(f"  PRX 64-bit constants: {len(prx_consts)}")
        for c in prx_consts[:3]:
            print(f"    0x{c:X}")
    
    # ===== Also check the decoder's specific addresses =====
    print(f"\n{'='*80}")
    print("Decoder Chain B specific addresses:")
    print(f"{'='*80}")
    
    # 0x80135DC74: mov rcx,[0x801D1E558]
    # 0x80135DC81: mov rax,[rcx]
    decoder_addrs = [0x80135DC74, 0x80135DC81]
    for addr in decoder_addrs:
        vaddr = addr - EBOOT_BASE
        foff = None
        for seg in eboot_segs:
            if seg['type'] == 1 and seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
                foff = seg['offset'] + (vaddr - seg['vaddr'])
                break
        if foff and foff + 8 <= len(eboot_data):
            chunk = eboot_data[foff:foff + 16]
            print(f"\n  0x{addr:X} (file 0x{foff:X}): {chunk.hex()}")
        else:
            print(f"\n  0x{addr:X}: NOT MAPPED in eboot")

if __name__ == '__main__':
    main()
