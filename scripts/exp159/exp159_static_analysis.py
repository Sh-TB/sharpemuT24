#!/usr/bin/env python3
"""
EXP-159: Static analysis of global 0x801E51240.
Find all writes and reads to this address in eboot.bin.
"""

import struct

EBOOT_PATH = "/tmp/exp158_games/eboot.bin"
PRX_PATH = "/tmp/exp158_games/Il2cppUserAssemblies.prx"
EBOOT_BASE = 0x800000000
PRX_BASE = 0x804CD5000
TARGET_ADDR = 0x801E51240

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

def runtime_to_file(segments, runtime, base):
    vaddr = runtime - base
    for seg in segments:
        if seg['type'] == 1 and seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
            return seg['offset'] + (vaddr - seg['vaddr'])
    return None

def search_rip_relative_refs(data, segments, target_addr, base, binary_name):
    """Search for ALL RIP-relative instructions (reads and writes) to target_addr."""
    refs = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(seg_data) - 11):
            # Check for RIP-relative addressing with various prefixes
            for prefix_len in range(0, 3):
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
                
                # All opcodes with ModRM that can use RIP-relative addressing
                modrm_opcodes = {0x8B, 0x89, 0x88, 0xC6, 0xC7, 0x80, 0x81, 0x83, 
                                0x09, 0x01, 0x08, 0x21, 0x31, 0xFE, 0xF6, 0x3B,
                                0x0F, 0xFF, 0x85, 0x3D, 0x05, 0x0D, 0x15, 0x1D,
                                0x25, 0x2D, 0x35, 0x3D}
                
                if opcode not in modrm_opcodes:
                    continue
                
                # Handle 2-byte opcodes (0F xx)
                if opcode == 0x0F and i + opcode_offset + 1 < len(seg_data):
                    b2 = seg_data[i + opcode_offset + 1]
                    if b2 in (0xB6, 0xBE, 0xAF, 0xB1, 0xB0):  # movzx, movsx, imul, cmpxchg
                        modrm_offset = opcode_offset + 2
                    else:
                        continue
                else:
                    modrm_offset = opcode_offset + 1
                
                if i + modrm_offset >= len(seg_data):
                    continue
                modrm = seg_data[i + modrm_offset]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod != 0 or rm != 5:  # Not RIP-relative
                    continue
                
                disp_offset = modrm_offset + 1
                if i + disp_offset + 4 > len(seg_data):
                    continue
                disp = struct.unpack_from('<i', seg_data, i + disp_offset)[0]
                
                # Calculate instruction length and target
                reg = (modrm >> 3) & 7
                base_len = disp_offset + 4
                imm_len = 0
                if opcode in (0xC6, 0x80, 0x83, 0xFE):
                    imm_len = 1
                elif opcode in (0xC7, 0x81):
                    imm_len = 4
                elif opcode == 0xF6 and reg in (0, 1):
                    imm_len = 1
                
                instr_len = base_len + imm_len
                instr_addr = base + seg['vaddr'] + i
                computed = instr_addr + instr_len + disp
                
                if computed == target_addr:
                    # Classify as read or write
                    is_write = False
                    if opcode in (0xC6, 0xC7, 0x89, 0x88):  # mov [mem], reg/imm
                        is_write = True
                    elif opcode in (0x80, 0x81, 0x83) and reg != 7:  # add/or/and/xor/sub (not cmp)
                        is_write = True
                    elif opcode in (0x09, 0x01, 0x08, 0x21, 0x31):  # or/add/and/xor [mem], reg
                        is_write = True
                    elif opcode == 0xFE:  # inc/dec
                        is_write = True
                    elif opcode == 0xF6 and reg in (2, 3):  # not/neg
                        is_write = True
                    
                    # Also check for LEA (load address)
                    is_lea = (opcode == 0x8D)
                    
                    # Determine instruction name
                    prefix_str = ''
                    if prefix_len >= 1:
                        p = seg_data[i]
                        if p == 0xF0: prefix_str = 'lock '
                        elif p in (0x48, 0x4C): prefix_str = 'rex '
                    
                    raw = seg_data[i:i+instr_len].hex()
                    op_name = 'write' if is_write else ('lea' if is_lea else 'read')
                    
                    refs.append({
                        'address': instr_addr,
                        'computed': computed,
                        'is_write': is_write,
                        'is_lea': is_lea,
                        'raw_bytes': raw,
                        'opcode': f'0x{opcode:02X}',
                        'prefix': prefix_str,
                        'binary': binary_name,
                    })
                    break
    
    return refs

def find_function_start(data, foff):
    for back in range(0, 8192):
        if foff - back < 0:
            return None
        if foff - back + 4 <= len(data):
            b = data[foff - back:foff - back + 4]
            if b == b'\x55\x48\x89\xe5':
                if foff - back - 1 >= 0:
                    prev = data[foff - back - 1]
                    if prev in (0xCC, 0xC3, 0xC9):
                        return back
    return None

def main():
    print("=" * 80)
    print("EXP-159: Static Analysis of Global 0x801E51240")
    print("=" * 80)
    
    target = TARGET_ADDR
    print(f"\nTarget address: 0x{target:X}")
    print(f"Eboot base: 0x{EBOOT_BASE:X}")
    print(f"PRX base: 0x{PRX_BASE:X}")
    print(f"Target vaddr in eboot: 0x{target - EBOOT_BASE:X}")
    
    # Check which segment the target is in
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    target_vaddr = target - EBOOT_BASE
    for seg in eboot_segs:
        if seg['type'] == 1:
            end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= target_vaddr < end:
                file_backed = seg['vaddr'] + seg['filesz']
                if target_vaddr < file_backed:
                    foff = seg['offset'] + (target_vaddr - seg['vaddr'])
                    val = eboot_data[foff:foff + 8]
                    print(f"\nTarget is in FILE-BACKED data segment")
                    print(f"  Segment: vaddr=0x{seg['vaddr']:X} flags={'X' if seg['flags']&1 else 'W' if seg['flags']&2 else 'R'}")
                    print(f"  File offset: 0x{foff:X}")
                    print(f"  Current value (8 bytes): {val.hex()}")
                    val_qword = struct.unpack_from('<Q', eboot_data, foff)[0]
                    print(f"  Current value (qword): 0x{val_qword:X}")
                else:
                    print(f"\nTarget is in BSS (beyond file-backed region)")
                    print(f"  Segment: vaddr=0x{seg['vaddr']:X} memsz=0x{seg['memsz']:X}")
                    print(f"  Value at runtime: 0x0 (BSS zero-initialized)")
                break
    
    # Search for references in eboot
    print(f"\n{'='*80}")
    print(f"Searching for RIP-relative references to 0x{target:X} in eboot.bin...")
    eboot_refs = search_rip_relative_refs(eboot_data, eboot_segs, target, EBOOT_BASE, "eboot.bin")
    
    writes = [r for r in eboot_refs if r['is_write']]
    reads = [r for r in eboot_refs if not r['is_write'] and not r['is_lea']]
    leas = [r for r in eboot_refs if r['is_lea']]
    
    print(f"\n  Total references: {len(eboot_refs)}")
    print(f"  Writes: {len(writes)}")
    print(f"  Reads: {len(reads)}")
    print(f"  LEAs: {len(leas)}")
    
    print(f"\n  WRITES:")
    for w in writes:
        foff = runtime_to_file(eboot_segs, w['address'], EBOOT_BASE)
        func_back = find_function_start(eboot_data, foff) if foff else None
        func_str = f" (in func 0x{w['address'] - func_back:X})" if func_back else ""
        print(f"    0x{w['address']:X}: {w['prefix']}write {w['opcode']} bytes={w['raw_bytes']}{func_str}")
        # Show context
        if foff:
            context = eboot_data[max(0, foff-16):foff+32]
            print(f"      Context: ...{context.hex()}...")
    
    print(f"\n  READS (first 20):")
    for r in reads[:20]:
        foff = runtime_to_file(eboot_segs, r['address'], EBOOT_BASE)
        func_back = find_function_start(eboot_data, foff) if foff else None
        func_str = f" (in func 0x{r['address'] - func_back:X})" if func_back else ""
        print(f"    0x{r['address']:X}: {r['prefix']}read {r['opcode']} bytes={r['raw_bytes']}{func_str}")
    
    if len(reads) > 20:
        print(f"    ... and {len(reads) - 20} more reads")
    
    print(f"\n  LEAs:")
    for l in leas:
        print(f"    0x{l['address']:X}: lea bytes={l['raw_bytes']}")
    
    # Also search in PRX
    print(f"\n{'='*80}")
    print(f"Searching for references to 0x{target:X} in PRX...")
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    prx_refs = search_rip_relative_refs(prx_data, prx_segs, target, PRX_BASE, "PRX")
    print(f"  Total PRX references: {len(prx_refs)}")
    for r in prx_refs[:5]:
        print(f"    0x{r['address']:X}: {'write' if r['is_write'] else 'read'} {r['opcode']} bytes={r['raw_bytes']}")
    
    # Also search for the address as a 64-bit constant
    print(f"\n{'='*80}")
    print(f"Searching for 0x{target:X} as 64-bit constant in eboot data sections...")
    target_bytes = struct.pack('<Q', target)
    for seg in eboot_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = eboot_data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(target_bytes, idx)
            if i == -1:
                break
            runtime = EBOOT_BASE + seg['vaddr'] + i
            print(f"  Found at 0x{runtime:X} (data section)")
            idx = i + 1
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"""
  Target: 0x{target:X}
  Location: {'BSS' if target_vaddr >= file_backed else 'FILE-BACKED'}
  Initial value: {'0 (BSS)' if target_vaddr >= file_backed else f'0x{val_qword:X}'}
  
  Eboot references: {len(eboot_refs)} total
    Writes: {len(writes)}
    Reads: {len(reads)}
    LEAs: {len(leas)}
  
  PRX references: {len(prx_refs)} total
  
  The decoder hypothesis claims a store at:
    DT_INIT → 0x13FCE40 → 0x13EB6B0 → MOV [0x801E51240], RAX
  
  Let's check if function 0x13EB6B0 exists and contains the store:
""")
    
    # Check the decoder's claimed call chain
    decoder_addrs = [0x13FCE40, 0x13EB6B0]
    for addr_vaddr in decoder_addrs:
        addr_runtime = EBOOT_BASE + addr_vaddr
        foff = runtime_to_file(eboot_segs, addr_runtime, EBOOT_BASE)
        if foff and foff < len(eboot_data) - 16:
            chunk = eboot_data[foff:foff + 32]
            print(f"  Function at 0x{addr_runtime:X} (vaddr 0x{addr_vaddr:X}, file 0x{foff:X}):")
            print(f"    First 32 bytes: {chunk.hex()}")
            if chunk[:4] == b'\x55\x48\x89\xe5':
                print(f"    Starts with push rbp; mov rbp, rsp (valid function)")
            else:
                print(f"    Does NOT start with standard prologue")
        else:
            print(f"  Function at 0x{addr_runtime:X}: NOT MAPPED")

if __name__ == '__main__':
    main()
