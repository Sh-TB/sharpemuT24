#!/usr/bin/env python3
"""
EXP-152 Step 2: Exhaustive Static Writer Search for 0x808D67B98.
"""

import struct
import json

EBOOT_PATH = "/tmp/exp151_games/eboot.bin"
PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"

PRX_MODULES = [
    "/tmp/exp151_games/Il2cppUserAssemblies.prx",
    "/tmp/exp151_games/libc.prx",
    "/tmp/exp151_games/libSceNpCppWebApi.prx",
    "/tmp/exp151_games/PS5Util.prx",
    "/tmp/exp151_games/PSNCommon.prx",
    "/tmp/exp151_games/PSNCore.prx",
    "/tmp/exp151_games/SaveData.prx",
    "/tmp/exp151_games/lib_burst_generated.prx",
]

PRX_BASE = 0x804CD5000
EBOOT_BASE = 0x800000000
TARGET_BYTE_ADDR = 0x808D67B98

def parse_elf64(path):
    data = open(path, 'rb').read()
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    e_shoff = struct.unpack_from('<Q', data, 0x28)[0]
    e_shentsize = struct.unpack_from('<H', data, 0x3A)[0]
    e_shnum = struct.unpack_from('<H', data, 0x3C)[0]
    e_shstrndx = struct.unpack_from('<H', data, 0x3E)[0]
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
    sections = []
    if e_shoff > 0 and e_shnum > 0 and e_shoff < len(data):
        shstr_hdr_off = e_shoff + e_shstrndx * e_shentsize
        if shstr_hdr_off + e_shentsize <= len(data):
            shstr_offset = struct.unpack_from('<Q', data, shstr_hdr_off + 0x18)[0]
            for i in range(e_shnum):
                sh_off = e_shoff + i * e_shentsize
                if sh_off + e_shentsize > len(data):
                    break
                sh_name_idx = struct.unpack_from('<I', data, sh_off)[0]
                sh_type = struct.unpack_from('<I', data, sh_off + 4)[0]
                sh_offset = struct.unpack_from('<Q', data, sh_off + 0x18)[0]
                sh_size = struct.unpack_from('<Q', data, sh_off + 0x20)[0]
                sh_entsize = struct.unpack_from('<Q', data, sh_off + 0x38)[0]
                name_start = shstr_offset + sh_name_idx
                name_end = data.find(b'\x00', name_start)
                name = data[name_start:name_end].decode('ascii', errors='replace') if name_end > name_start else ''
                sections.append({'name': name, 'type': sh_type, 'offset': sh_offset, 'size': sh_size, 'entsize': sh_entsize})
    return data, segments, sections

def search_rip_relative_writes(data, segments, target_addr, load_base, binary_name):
    """Search for ALL RIP-relative instructions that write to target_addr."""
    writers = []
    write_opcodes = {0xC6, 0xC7, 0x88, 0x89, 0x80, 0x81, 0x83, 0x09, 0x01, 0x08, 0x21, 0x31, 0xFE, 0xF6}
    
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        seg_vaddr_start = seg['vaddr']
        
        for i in range(len(seg_data) - 11):
            # Try different prefix combinations
            for prefix_len in range(0, 3):
                if i + prefix_len >= len(seg_data):
                    break
                opcode_byte = seg_data[i + prefix_len]
                
                # Check prefix validity
                if prefix_len == 1:
                    p = seg_data[i]
                    if p not in (0xF0, 0x48, 0x4C, 0x66, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47):
                        continue
                elif prefix_len == 2:
                    p1 = seg_data[i]
                    p2 = seg_data[i+1]
                    valid = (p1 in (0xF0, 0x48, 0x4C, 0x66) and p2 in (0xF0, 0x48, 0x4C, 0x66))
                    if not valid:
                        continue
                
                if opcode_byte not in write_opcodes:
                    continue
                
                modrm_offset = prefix_len + 1
                if i + modrm_offset >= len(seg_data):
                    continue
                modrm = seg_data[i + modrm_offset]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod != 0 or rm != 5:
                    continue
                
                # RIP-relative
                disp_offset = modrm_offset + 1
                if i + disp_offset + 4 > len(seg_data):
                    continue
                disp = struct.unpack_from('<i', seg_data, i + disp_offset)[0]
                
                # Calculate instruction length
                base_len = disp_offset + 4
                imm_len = 0
                reg = (modrm >> 3) & 7
                if opcode_byte in (0xC6, 0x80, 0xFE, 0xF6):
                    imm_len = 1
                elif opcode_byte in (0xC7, 0x81):
                    imm_len = 4
                elif opcode_byte == 0x83:
                    imm_len = 1
                
                instr_len = base_len + imm_len
                instr_addr = load_base + seg_vaddr_start + i
                computed = instr_addr + instr_len + disp
                
                if computed == target_addr:
                    prefix_str = ''
                    if prefix_len >= 1:
                        p = seg_data[i]
                        if p == 0xF0: prefix_str = 'lock '
                        elif p in (0x48, 0x4C): prefix_str = 'rex '
                    if prefix_len >= 2:
                        p2 = seg_data[i+1]
                        if p2 == 0xF0: prefix_str += 'lock '
                    
                    op_names = {
                        0xC6: 'mov byte', 0xC7: 'mov dword', 0x88: 'mov byte', 0x89: 'mov',
                        0x80: 'or/and/xor byte', 0x81: 'or/and/xor dword', 0x83: 'or/and/xor',
                        0x09: 'or', 0x01: 'add', 0x08: 'or byte', 0x21: 'and', 0x31: 'xor',
                        0xFE: 'inc/dec byte', 0xF6: 'test/not/neg byte'
                    }
                    op_name = op_names.get(opcode_byte, f'0x{opcode_byte:02X}')
                    raw = seg_data[i:i+instr_len].hex()
                    writers.append({
                        'address': f'0x{instr_addr:X}',
                        'binary': binary_name,
                        'instruction': f'{prefix_str}{op_name} [rip+0x{disp:X}] -> 0x{computed:X}',
                        'raw_bytes': raw,
                        'instruction_length': instr_len
                    })
    return writers

def search_rela_for_target(data, sections, target_vaddr, search_range=8):
    """Search RELA sections for relocations targeting target_vaddr (±search_range)."""
    rela_entries = []
    for sec in sections:
        if sec['type'] != 4:
            continue
        entry_count = sec['size'] // 24
        for j in range(entry_count):
            entry_off = sec['offset'] + j * 24
            if entry_off + 24 > len(data):
                break
            r_offset = struct.unpack_from('<Q', data, entry_off)[0]
            if abs(r_offset - target_vaddr) <= search_range:
                r_info = struct.unpack_from('<Q', data, entry_off + 8)[0]
                r_addend = struct.unpack_from('<q', data, entry_off + 16)[0]
                r_type = r_info & 0xFFFFFFFF
                r_sym = r_info >> 32
                type_names = {1: 'R_X86_64_64', 7: 'JUMP_SLOT', 8: 'RELATIVE', 9: 'GLOB_DAT', 0x16: 'IRELATIVE'}
                type_name = type_names.get(r_type, f'type={r_type}')
                rela_entries.append({
                    'entry_index': j,
                    'r_offset': f'0x{r_offset:X}',
                    'r_info': f'0x{r_info:X}',
                    'r_addend': f'0x{r_addend:X}',
                    'type': type_name,
                    'symbol': r_sym,
                    'offset_diff': r_offset - target_vaddr
                })
    return rela_entries

def main():
    print("=" * 80)
    print("EXP-152 Step 2: Exhaustive Static Writer Search for 0x808D67B98")
    print("=" * 80)
    
    all_writers = []
    all_rela = []
    
    # Search Il2cppUserAssemblies.prx
    print(f"\n[1] Searching Il2cppUserAssemblies.prx (load base 0x{PRX_BASE:X})...")
    prx_data, prx_segs, prx_secs = parse_elf64(PRX_PATH)
    target_vaddr = TARGET_BYTE_ADDR - PRX_BASE
    print(f"  Target runtime: 0x{TARGET_BYTE_ADDR:X}")
    print(f"  Target vaddr in PRX: 0x{target_vaddr:X}")
    
    writers = search_rip_relative_writes(prx_data, prx_segs, TARGET_BYTE_ADDR, PRX_BASE, "Il2cppUserAssemblies.prx")
    all_writers.extend(writers)
    print(f"  Found {len(writers)} RIP-relative write instructions")
    for w in writers[:20]:
        print(f"    {w['address']}: {w['instruction']}")
        print(f"      bytes: {w['raw_bytes']}")
    
    # Search for the address as a 64-bit constant
    print(f"\n  Searching for 0x{TARGET_BYTE_ADDR:X} as 64-bit constant in PRX...")
    target_bytes = struct.pack('<Q', TARGET_BYTE_ADDR)
    idx = prx_data.find(target_bytes)
    count = 0
    while idx >= 0 and count < 10:
        for seg in prx_segs:
            if seg['offset'] <= idx < seg['offset'] + seg['filesz']:
                runtime = PRX_BASE + seg['vaddr'] + (idx - seg['offset'])
                seg_type = 'CODE' if seg['flags'] & 1 else ('DATA-W' if seg['flags'] & 2 else 'DATA-R')
                print(f"  Found at 0x{runtime:X} ({seg_type})")
                count += 1
                break
        idx = prx_data.find(target_bytes, idx + 1)
    if count == 0:
        print(f"  Not found as 64-bit constant")
    
    # Search RELA
    print(f"\n  Searching RELA for r_offset near 0x{target_vaddr:X}...")
    rela_entries = search_rela_for_target(prx_data, prx_secs, target_vaddr)
    all_rela.extend(rela_entries)
    print(f"  Found {len(rela_entries)} RELA entries")
    for e in rela_entries[:10]:
        print(f"    Entry #{e['entry_index']}: r_offset={e['r_offset']} type={e['type']} addend={e['r_addend']} diff={e['offset_diff']}")
    
    # Search eboot
    print(f"\n[2] Searching eboot.bin for 0x{TARGET_BYTE_ADDR:X} as 64-bit constant...")
    eboot_data, eboot_segs, eboot_secs = parse_elf64(EBOOT_PATH)
    idx = eboot_data.find(target_bytes)
    count = 0
    while idx >= 0 and count < 10:
        for seg in eboot_segs:
            if seg['offset'] <= idx < seg['offset'] + seg['filesz']:
                runtime = EBOOT_BASE + seg['vaddr'] + (idx - seg['offset'])
                seg_type = 'CODE' if seg['flags'] & 1 else 'DATA'
                print(f"  Found at 0x{runtime:X} ({seg_type})")
                count += 1
                break
        idx = eboot_data.find(target_bytes, idx + 1)
    if count == 0:
        print(f"  Not found in eboot")
    
    # Search other PRX modules
    print(f"\n[3] Searching other PRX modules for 0x{TARGET_BYTE_ADDR:X} as 64-bit constant...")
    for prx_path in PRX_MODULES[1:]:
        try:
            mod_data = open(prx_path, 'rb').read()
            mod_name = prx_path.split('/')[-1]
            idx = mod_data.find(target_bytes)
            if idx >= 0:
                print(f"  {mod_name}: Found at file offset 0x{idx:X}")
        except:
            pass
    
    # Also search for the flag array base
    print(f"\n[4] Searching for flag array base 0x808B55698...")
    flag_array_base = 0x808B55698
    flag_array_vaddr = flag_array_base - PRX_BASE
    target_bytes2 = struct.pack('<Q', flag_array_base)
    idx = prx_data.find(target_bytes2)
    count = 0
    while idx >= 0 and count < 5:
        for seg in prx_segs:
            if seg['offset'] <= idx < seg['offset'] + seg['filesz']:
                runtime = PRX_BASE + seg['vaddr'] + (idx - seg['offset'])
                seg_type = 'CODE' if seg['flags'] & 1 else ('DATA-W' if seg['flags'] & 2 else 'DATA-R')
                print(f"  Flag array base at 0x{runtime:X} ({seg_type})")
                count += 1
                break
        idx = prx_data.find(target_bytes2, idx + 1)
    
    rela2 = search_rela_for_target(prx_data, prx_secs, flag_array_vaddr)
    print(f"  RELA entries for flag array base: {len(rela2)}")
    for e in rela2[:5]:
        print(f"    Entry #{e['entry_index']}: r_offset={e['r_offset']} type={e['type']} addend={e['r_addend']}")
    
    # Generate JSON
    database = {
        "target_address": f"0x{TARGET_BYTE_ADDR:X}",
        "target_vaddr_in_prx": f"0x{target_vaddr:X}",
        "flag_array_base": f"0x{flag_array_base:X}",
        "writers": all_writers,
        "rela_entries": all_rela,
        "summary": {
            "total_writers_found": len(all_writers),
            "total_rela_entries": len(all_rela),
        }
    }
    with open('/home/z/my-project/scripts/exp152/FLAG_WRITER_DATABASE.json', 'w') as f:
        json.dump(database, f, indent=2)
    
    print(f"\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if len(all_writers) == 0:
        print(f"  *** NO RIP-RELATIVE WRITES FOUND ***")
        print(f"  No instruction writes to 0x{TARGET_BYTE_ADDR:X} via RIP-relative addressing")
        print(f"  Possible explanations:")
        print(f"    1. Flag set by indirect addressing (register-based, not RIP-relative)")
        print(f"    2. Flag set by IL2CPP runtime C code (not generated code)")
        print(f"    3. Flag set by metadata processing (not code at all)")
        print(f"    4. Flag set by a .cctor via computed address")
    else:
        print(f"  Found {len(all_writers)} write instructions!")

if __name__ == '__main__':
    main()
