#!/usr/bin/env python3
"""
EXP-162: Full cross-validation of Chain A (0x801E518C8) vs Chain B (0x801D1E558).
Addresses all 5 required tests.
"""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
PRX_PATH = "/tmp/exp162_games/Il2cppUserAssemblies.prx"
EBOOT_BASE = 0x800000000
PRX_BASE = 0x804CD5000

TARGETS = {
    "0x801E518C8 (Chain A)": 0x801E518C8,
    "0x801D1E558 (Chain B)": 0x801D1E558,
    "0x801E51240 (Global)": 0x801E51240,
}

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

def check_mapping(data, segments, addr, base, label):
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
                    return f"MAPPED: FILE-BACKED ({flags}), value=0x{val:X}, file_offset=0x{foff:X}"
                else:
                    return f"MAPPED: BSS ({flags}), value=0x0 at runtime"
    return f"NOT MAPPED (vaddr 0x{vaddr:X} not in any segment)"

def search_writes(data, segments, target, base):
    writes = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(seg_data) - 11):
            for plen in range(2):
                if plen == 1 and seg_data[i] not in (0xF0, 0x48, 0x4C, 0x66):
                    continue
                oc_off = plen
                oc = seg_data[i + oc_off] if i + oc_off < len(seg_data) else 0
                if oc not in (0xC6, 0xC7, 0x89, 0x88, 0x80, 0x81, 0x83):
                    continue
                mr_off = oc_off + 1
                if i + mr_off >= len(seg_data):
                    continue
                modrm = seg_data[i + mr_off]
                if (modrm >> 6) & 3 != 0 or (modrm & 7) != 5:
                    continue
                doff = mr_off + 1
                if i + doff + 4 > len(seg_data):
                    continue
                disp = struct.unpack_from('<i', seg_data, i + doff)[0]
                reg = (modrm >> 3) & 7
                blen = doff + 4
                ilen = 0
                if oc in (0xC6, 0x80, 0x83): ilen = 1
                elif oc in (0xC7, 0x81): ilen = 4
                total = blen + ilen
                addr = base + seg['vaddr'] + i
                comp = addr + total + disp
                if comp == target:
                    if oc in (0x80, 0x81, 0x83) and reg == 7:
                        continue  # CMP, not write
                    # Decode instruction
                    raw = seg_data[i:i+total].hex()
                    imm_val = None
                    if ilen == 1: imm_val = seg_data[i + blen]
                    elif ilen == 4: imm_val = struct.unpack_from('<I', seg_data, i + blen)[0]
                    
                    if oc == 0xC7:
                        desc = f"mov qword [0x{target:X}], 0x{imm_val:X}" if imm_val is not None else f"mov qword [0x{target:X}], imm"
                    elif oc == 0x89:
                        regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']
                        rex_r = (seg_data[i] >> 2) & 1 if plen == 1 else 0
                        idx = reg + (rex_r * 8); rname = regs[idx] if idx < 16 else f'r{idx}'
                        desc = f"mov [0x{target:X}], {rname}"
                    else:
                        desc = f"write 0x{oc:02X}"
                    
                    writes.append((addr, desc, raw))
                    break
    return writes

def search_reads(data, segments, target, base):
    reads = 0
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(seg_data) - 7):
            b0 = seg_data[i]
            b1 = seg_data[i+1] if i+1 < len(seg_data) else 0
            if b0 in (0x48, 0x4C) and b1 == 0x8B:
                modrm = seg_data[i+2]
                if (modrm >> 6) & 3 == 0 and (modrm & 7) == 5:
                    disp = struct.unpack_from('<i', seg_data, i+3)[0]
                    comp = base + seg['vaddr'] + i + 7 + disp
                    if comp == target:
                        reads += 1
            if b0 == 0x83 and b1 == 0x3D:
                disp = struct.unpack_from('<i', seg_data, i+2)[0]
                comp = base + seg['vaddr'] + i + 7 + disp
                if comp == target:
                    reads += 1
    return reads

def search_64bit_const(data, segments, target, base):
    target_bytes = struct.pack('<Q', target)
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
            hits.append(base + seg['vaddr'] + i)
            idx = i + 1
    return hits

def main():
    print("=" * 80)
    print("EXP-162: Full Cross-Validation — Chain A vs Chain B")
    print("=" * 80)
    
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    
    for label, addr in TARGETS.items():
        print(f"\n{'='*80}")
        print(f"  {label}")
        print(f"{'='*80}")
        
        # Eboot
        eboot_map = check_mapping(eboot_data, eboot_segs, addr, EBOOT_BASE, "eboot")
        print(f"\n  EBOOT: {eboot_map}")
        
        eboot_writes = search_writes(eboot_data, eboot_segs, addr, EBOOT_BASE)
        print(f"  Eboot writes: {len(eboot_writes)}")
        for w, desc, raw in eboot_writes[:5]:
            print(f"    0x{w:X}: {desc} bytes={raw}")
        
        eboot_reads = search_reads(eboot_data, eboot_segs, addr, EBOOT_BASE)
        print(f"  Eboot reads: {eboot_reads}")
        
        eboot_consts = search_64bit_const(eboot_data, eboot_segs, addr, EBOOT_BASE)
        print(f"  Eboot 64-bit constants: {len(eboot_consts)}")
        
        # PRX
        prx_map = check_mapping(prx_data, prx_segs, addr, PRX_BASE, "PRX")
        print(f"\n  PRX: {prx_map}")
        
        prx_writes = search_writes(prx_data, prx_segs, addr, PRX_BASE)
        print(f"  PRX writes: {len(prx_writes)}")
        
        prx_reads = search_reads(prx_data, prx_segs, addr, PRX_BASE)
        print(f"  PRX reads: {prx_reads}")
        
        prx_consts = search_64bit_const(prx_data, prx_segs, addr, PRX_BASE)
        print(f"  PRX 64-bit constants: {len(prx_consts)}")
    
    # ===== Decoder Chain B verification =====
    print(f"\n{'='*80}")
    print("  Decoder Chain B Address Verification")
    print(f"{'='*80}")
    
    # Decoder claims: 0x80135DC74 = mov rcx,[0x801D1E558]
    decoder_addrs = [0x80135DC74, 0x80135DC81]
    for addr in decoder_addrs:
        vaddr = addr - EBOOT_BASE
        foff = None
        for seg in eboot_segs:
            if seg['type'] == 1 and seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
                foff = seg['offset'] + (vaddr - seg['vaddr'])
                break
        if foff and foff + 16 <= len(eboot_data):
            chunk = eboot_data[foff:foff + 16]
            print(f"\n  0x{addr:X} (file 0x{foff:X}): {chunk.hex()}")
            # Check if it's mov rcx, [rip+disp32] = 48 8B 0D xx xx xx xx
            if chunk[0] == 0x48 and chunk[1] == 0x8B and chunk[2] == 0x0D:
                disp = struct.unpack_from('<i', chunk, 3)[0]
                target = addr + 7 + disp
                print(f"    → mov rcx, [rip+0x{disp:X}] = [0x{target:X}]")
                if target == 0x801D1E558:
                    print(f"    *** MATCHES 0x801D1E558 ***")
                else:
                    print(f"    Does NOT match 0x801D1E558 (target=0x{target:X})")
            else:
                print(f"    Byte 0 = 0x{chunk[0]:02X} — NOT a REX prefix (0x48)")
                print(f"    Decoder's instruction mapping is WRONG")
        else:
            print(f"\n  0x{addr:X}: NOT MAPPED in eboot")

if __name__ == '__main__':
    main()
