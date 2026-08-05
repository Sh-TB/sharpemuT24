#!/usr/bin/env python3
"""
EXP-152 Step 4: Find the INITIAL flag setter — the one that doesn't check the flag first.
The writer function 0x804FB1B90 checks the flag before setting it (chicken-and-egg).
There must be another writer that sets the flag UNCONDITIONALLY.
"""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000
TARGET_BYTE_ADDR = 0x808D67B98

# Known writers (all check the flag before setting):
# 0x804FB1C1B: mov dword [0x808D67B98], 1  (in function 0x804FB1B90 which checks flag first)
# 0x804FBF45B: mov dword [0x808D67B98], 1  (in function 0x804FBF250)
# 0x804FBF509: mov dword [0x808D67B98], 1  (in function 0x804FBF250)

# But the flag is 4 bytes (dword). Let's search for writes to the full 4-byte range.
# The flag occupies 0x808D67B98 to 0x808D67B9B (4 bytes for dword).

# Also search for writes to nearby addresses that might overlap:
# 0x808D67B90 to 0x808D67BA0

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

def find_function_start(data, segments, addr, load_base):
    foff = runtime_to_file(segments, addr, load_base)
    if foff is None:
        return None
    for back in range(0, 8192):
        if foff - back < 0:
            return None
        if foff - back + 4 <= len(data):
            b = data[foff - back:foff - back + 4]
            if b == b'\x55\x48\x89\xe5':
                if foff - back - 1 >= 0:
                    prev = data[foff - back - 1]
                    if prev in (0xCC, 0xC3, 0xC9):
                        return addr - back
    return None

def main():
    print("=" * 80)
    print("EXP-152 Step 4: Find Initial Flag Setter (Unconditional Writer)")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    # Search for writes to the entire flag range: 0x808D67B90 to 0x808D67BA0
    # This catches writes to the dword, byte, qword, or any overlapping access
    flag_start = 0x808D67B90
    flag_end = 0x808D67BA0
    
    print(f"\nSearching for writes to range 0x{flag_start:X} to 0x{flag_end:X}...")
    
    all_writers = []
    
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        
        for i in range(len(seg_data) - 11):
            for prefix_len in range(0, 3):
                if i + prefix_len >= len(seg_data):
                    break
                if prefix_len >= 1:
                    p = seg_data[i]
                    if p not in (0xF0, 0x48, 0x4C, 0x66, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47):
                        continue
                if prefix_len >= 2:
                    p2 = seg_data[i + 1]
                    if p2 not in (0xF0, 0x48, 0x4C, 0x66):
                        continue
                
                opcode_offset = prefix_len
                if i + opcode_offset >= len(seg_data):
                    continue
                opcode = seg_data[i + opcode_offset]
                
                # Write opcodes
                write_opcodes = {0xC6, 0xC7, 0x88, 0x89, 0x80, 0x81, 0x83, 0x09, 0x01, 0x08, 0x21, 0x31, 0xFE, 0xF6}
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
                
                base_len = disp_offset + 4
                imm_len = 0
                reg = (modrm >> 3) & 7
                if opcode in (0xC6, 0x80, 0xFE, 0xF6, 0x83):
                    imm_len = 1
                elif opcode in (0xC7, 0x81):
                    imm_len = 4
                
                instr_len = base_len + imm_len
                instr_addr = PRX_BASE + seg['vaddr'] + i
                computed = instr_addr + instr_len + disp
                
                # Check if computed falls within the flag range
                if flag_start <= computed < flag_end:
                    # Skip CMP (read-only)
                    is_cmp = (opcode in (0x80, 0x81, 0x83) and reg == 7)
                    is_test = (opcode == 0xF6 and reg in (0, 1))
                    if is_cmp or is_test:
                        continue
                    
                    # Also check for lock or atomic writes
                    prefix_str = ''
                    if prefix_len >= 1:
                        p = seg_data[i]
                        if p == 0xF0: prefix_str = 'lock '
                        elif p in (0x48, 0x4C): prefix_str = 'rex.W '
                    if prefix_len >= 2:
                        p2 = seg_data[i + 1]
                        if p2 == 0xF0: prefix_str += 'lock '
                    
                    raw = seg_data[i:i+instr_len].hex()
                    func_start = find_function_start(data, segments, instr_addr, PRX_BASE)
                    
                    all_writers.append({
                        'address': instr_addr,
                        'computed': computed,
                        'instruction': f'{prefix_str}opcode 0x{opcode:02X} [0x{computed:X}]',
                        'raw_bytes': raw,
                        'function': func_start,
                    })
                    break
    
    print(f"\nFound {len(all_writers)} write instructions to flag range")
    for w in all_writers:
        func_str = f'0x{w["function"]:X}' if w['function'] else 'unknown'
        print(f"  0x{w['address']:X} in func {func_str}: {w['instruction']} bytes={w['raw_bytes']}")
    
    # Now for each writer, check if the containing function checks the flag BEFORE the write
    print(f"\n{'='*80}")
    print("Checking if each writer's function checks the flag BEFORE writing:")
    print("=" * 80)
    
    for w in all_writers:
        func_start = w['function']
        if not func_start:
            continue
        
        writer_offset = w['address'] - func_start
        func_foff = runtime_to_file(segments, func_start, PRX_BASE)
        if not func_foff:
            continue
        
        # Read the function up to the writer instruction
        chunk = data[func_foff:func_foff + writer_offset + 20]
        
        # Search for CMP byte [0x808D67B98], 0 in the function BEFORE the writer
        # Pattern: 83 3D <disp32> 00 where computed == 0x808D67B98
        flag_check_found = False
        for i in range(min(writer_offset, len(chunk) - 7)):
            if chunk[i] == 0x83 and chunk[i+1] == 0x3D:
                disp = struct.unpack_from('<i', chunk, i + 2)[0]
                check_addr = func_start + i + 7 + disp
                if check_addr == TARGET_BYTE_ADDR:
                    flag_check_found = True
                    # Check what follows
                    je_byte = chunk[i + 7] if i + 7 < len(chunk) else 0
                    print(f"\n  Writer 0x{w['address']:X} in func 0x{func_start:X}:")
                    print(f"    Flag check at offset +0x{i:X} (0x{func_start + i:X})")
                    print(f"    cmp byte [0x{TARGET_BYTE_ADDR:X}], 0")
                    if je_byte == 0x74:  # je
                        je_off = chunk[i + 8]
                        print(f"    je +{je_off} (skip if flag == 0)")
                        print(f"    *** FUNCTION CHECKS FLAG BEFORE WRITING ***")
                        print(f"    *** If flag == 0, writer is SKIPPED ***")
                    elif je_byte == 0x75:  # jne
                        jne_off = chunk[i + 8]
                        print(f"    jne +{jne_off} (skip if flag != 0)")
                    break
        
        if not flag_check_found:
            print(f"\n  Writer 0x{w['address']:X} in func 0x{func_start:X}:")
            print(f"    *** NO FLAG CHECK BEFORE WRITER ***")
            print(f"    *** THIS IS THE INITIAL SETTER! ***")
            print(f"    *** This function writes the flag UNCONDITIONALLY ***")
    
    # ===== Also search for the flag address as part of a larger structure =====
    print(f"\n{'='*80}")
    print("Searching for the flag as part of IL2CPP metadata structures:")
    print("=" * 80)
    
    # The flag at 0x808D67B98 might be part of a larger structure
    # Let's check what's around it
    
    # Read the data around the flag (from the file if possible, or note it's in BSS)
    flag_vaddr = TARGET_BYTE_ADDR - PRX_BASE
    print(f"\nFlag vaddr: 0x{flag_vaddr:X}")
    
    # Check which segment
    for seg in segments:
        if seg['type'] == 1:
            end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= flag_vaddr < end:
                file_backed = seg['vaddr'] + seg['filesz']
                if flag_vaddr < file_backed:
                    # Read from file
                    foff = seg['offset'] + (flag_vaddr - seg['vaddr'])
                    surrounding = data[foff - 32:foff + 32]
                    print(f"  In file-backed data. Surrounding bytes:")
                    for i in range(0, len(surrounding), 16):
                        addr = TARGET_BYTE_ADDR - 32 + i
                        hex_str = ' '.join(f'{b:02X}' for b in surrounding[i:i+16])
                        print(f"    0x{addr:X}: {hex_str}")
                else:
                    print(f"  In BSS — no file data available")
                    print(f"  The flag is at offset 0x{flag_vaddr - seg['vaddr']:X} from segment start")
                    print(f"  Segment: vaddr=0x{seg['vaddr']:X} memsz=0x{seg['memsz']:X}")
                break

if __name__ == '__main__':
    main()
