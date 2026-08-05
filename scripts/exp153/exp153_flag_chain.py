#!/usr/bin/env python3
"""EXP-153 Step 4: Analyze second gate flag 0x808B55690 and the chain of flags."""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

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

def runtime_to_file(segments, runtime, load_base):
    vaddr = runtime - load_base
    for seg in segments:
        if seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
            return seg['offset'] + (vaddr - seg['vaddr'])
    return None

def find_callers_of(data, segments, target_addr, load_base):
    callers = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
            if data[i] == 0xE8:
                rel = struct.unpack_from('<i', data, i + 1)[0]
                call_addr = load_base + seg['vaddr'] + (i - seg['offset'])
                target = call_addr + 5 + rel
                if target == target_addr:
                    callers.append(call_addr)
    return callers

def main():
    data, segments = parse_elf64(PRX_PATH)
    
    # The flag at 0x808D67BB8 has writers:
    # 0x804FB1C93: mov dword [0x808D67BB8], 1 (inside 0x804FB1B90, at offset +0x103)
    # 0x804FBF59F: mov dword [0x808D67BB8], 0 (inside 0x804FBF250, at offset +0x34F)
    
    # Let's look at the context around 0x804FB1C93
    print("=" * 80)
    print("Context around writer 0x804FB1C93 (sets 0x808D67BB8 = 1)")
    print("=" * 80)
    
    addr = 0x804FB1C93
    foff = runtime_to_file(segments, addr, PRX_BASE)
    if foff:
        context = data[max(0, foff - 32):foff + 32]
        for i in range(0, len(context), 16):
            a = addr - 32 + i
            hex_str = ' '.join(f'{b:02X}' for b in context[i:i+16])
            print(f"  0x{a:X}: {hex_str}")
    
    # And context around 0x804FBF59F (sets 0x808D67BB8 = 0)
    print(f"\n{'='*80}")
    print("Context around writer 0x804FBF59F (sets 0x808D67BB8 = 0)")
    print("=" * 80)
    
    addr = 0x804FBF59F
    foff = runtime_to_file(segments, addr, PRX_BASE)
    if foff:
        context = data[max(0, foff - 32):foff + 32]
        for i in range(0, len(context), 16):
            a = addr - 32 + i
            hex_str = ' '.join(f'{b:02X}' for b in context[i:i+16])
            print(f"  0x{a:X}: {hex_str}")
    
    # Now let's search for ALL flags in the 0x808D67B90-0x808D67BC0 range
    # These might be part of the same structure
    print(f"\n{'='*80}")
    print("Searching for ALL writes to 0x808D67B90-0x808D67BC0 range")
    print("=" * 80)
    
    range_start = 0x808D67B90
    range_end = 0x808D67BC0
    
    all_writers = []
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
                if opcode not in (0xC6, 0xC7, 0x88, 0x89, 0x80, 0x81, 0x83):
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
                instr_addr = PRX_BASE + seg['vaddr'] + i
                computed = instr_addr + instr_len + disp
                
                if range_start <= computed < range_end:
                    is_cmp = (opcode in (0x80, 0x81, 0x83) and reg == 7)
                    if is_cmp:
                        continue
                    raw = seg_data[i:i+instr_len].hex()
                    # Get the immediate value
                    imm_val = None
                    if imm_len == 1:
                        imm_val = seg_data[i + base_len]
                    elif imm_len == 4:
                        imm_val = struct.unpack_from('<I', seg_data, i + base_len)[0]
                    
                    all_writers.append({
                        'address': instr_addr,
                        'target': computed,
                        'opcode': f'0x{opcode:02X}',
                        'reg': reg,
                        'imm': imm_val,
                        'raw': raw,
                    })
                    break
    
    print(f"\nFound {len(all_writers)} write instructions:")
    for w in all_writers:
        imm_str = f'imm=0x{w["imm"]:X}' if w['imm'] is not None else 'no imm'
        print(f"  0x{w['address']:X}: write to 0x{w['target']:X} {w['opcode']} reg={w['reg']} {imm_str} bytes={w['raw']}")
    
    # Group by target
    print(f"\nGrouped by target:")
    from collections import defaultdict
    groups = defaultdict(list)
    for w in all_writers:
        groups[w['target']].append(w)
    
    for target in sorted(groups.keys()):
        writers = groups[target]
        print(f"\n  0x{target:X}: {len(writers)} writers")
        for w in writers:
            imm_str = f'= {w["imm"]}' if w['imm'] is not None else ''
            print(f"    0x{w['address']:X}: {w['opcode']} reg={w['reg']} {imm_str}")
    
    # ===== Key analysis: What is at 0x808D67B98 in the IL2CPP metadata? =====
    print(f"\n{'='*80}")
    print("Flag structure analysis")
    print("=" * 80)
    
    # The flags at 0x808D67B98 and 0x808D67BB8 are 0x20 bytes apart
    # This could be a structure with fields at different offsets
    # Let's check all flags in the range and their offsets
    
    print(f"\nFlag addresses and offsets from 0x808D67B90:")
    for target in sorted(groups.keys()):
        offset = target - 0x808D67B90
        print(f"  0x{target:X} (offset +0x{offset:X}): {len(groups[target])} writers")

if __name__ == '__main__':
    main()
