#!/usr/bin/env python3
"""EXP-153 Step 1: Deep analysis of all 3 flag writer functions."""

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

def hex_dump(data, foff, count, base_addr):
    for i in range(0, count, 16):
        if foff + i >= len(data):
            break
        addr = base_addr + i
        chunk = data[foff + i:foff + min(i + 16, count)]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        print(f"  0x{addr:X}: {hex_str}")

WRITERS = [(0x804FB1C1B, 0x804FB1B90), (0x804FBF45B, 0x804FBF250), (0x804FBF509, 0x804FBF250)]

def main():
    print("=" * 80)
    print("EXP-153 Step 1: Deep Analysis of Flag Writer Functions")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    analyzed = set()
    for writer_addr, func_addr in WRITERS:
        if func_addr in analyzed:
            continue
        analyzed.add(func_addr)
        
        print(f"\n{'='*80}")
        print(f"Writer Function: 0x{func_addr:X} (writer at 0x{writer_addr:X})")
        print(f"{'='*80}")
        
        foff = runtime_to_file(segments, func_addr, PRX_BASE)
        if not foff:
            continue
        
        print(f"\nFirst 512 bytes:")
        hex_dump(data, foff, 512, func_addr)
        
        # Find CMP instructions
        chunk = data[foff:foff + 512]
        print(f"\nCMP byte [rip+disp32], imm8 instructions:")
        for i in range(len(chunk) - 7):
            if chunk[i] == 0x83 and chunk[i+1] == 0x3D:
                disp = struct.unpack_from('<i', chunk, i + 2)[0]
                check_addr = func_addr + i + 7 + disp
                imm = chunk[i + 6]
                print(f"  0x{func_addr + i:X}: cmp byte [0x{check_addr:X}], {imm}")
        
        # Find conditional jumps
        print(f"\nConditional jumps:")
        for i in range(len(chunk) - 6):
            b = chunk[i]
            if 0x70 <= b <= 0x7F:
                rel = struct.unpack_from('<b', chunk, i + 1)[0]
                target = func_addr + i + 2 + rel
                cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b - 0x70]
                print(f"  0x{func_addr + i:X}: {cc} +{rel} -> 0x{target:X}")
            elif b == 0x0F and i + 5 < len(chunk) and 0x80 <= chunk[i+1] <= 0x8F:
                rel = struct.unpack_from('<i', chunk, i + 2)[0]
                target = func_addr + i + 6 + rel
                cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][chunk[i+1] - 0x80]
                print(f"  0x{func_addr + i:X}: {cc} -> 0x{target:X}")
        
        # Find CALLs
        print(f"\nCALL instructions:")
        for i in range(len(chunk) - 5):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = func_addr + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:
                    print(f"  0x{call_addr:X}: call 0x{target:X}")
        
        # Find callers
        callers = find_callers_of(data, segments, func_addr, PRX_BASE)
        print(f"\nCallers: {len(callers)}")
        for c in callers[:10]:
            c_foff = runtime_to_file(segments, c, PRX_BASE)
            if c_foff:
                back = find_function_start(data, c_foff)
                if back is not None:
                    print(f"  CALL at 0x{c:X} in func 0x{c - back:X}")

if __name__ == '__main__':
    main()
