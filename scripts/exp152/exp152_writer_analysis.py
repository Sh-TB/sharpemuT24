#!/usr/bin/env python3
"""
EXP-152 Step 2c: Analyze the 3 writer instructions and find their calling context.
"""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

WRITER_ADDRS = [0x804FB1C1B, 0x804FBF45B, 0x804FBF509]

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
    """Find function start by searching backward for prologue."""
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

def find_callers_of(data, segments, target_addr, load_base):
    """Find all E8 CALL instructions targeting target_addr."""
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

def follow_jmp(data, segments, addr, load_base, depth=0, visited=None):
    if visited is None:
        visited = set()
    if addr in visited or depth > 10:
        return addr
    visited.add(addr)
    foff = runtime_to_file(segments, addr, load_base)
    if foff is None or foff >= len(data) - 5:
        return addr
    if data[foff] == 0xE9:
        rel = struct.unpack_from('<i', data, foff + 1)[0]
        target = addr + 5 + rel
        return follow_jmp(data, segments, target, load_base, depth + 1, visited)
    return addr

def main():
    print("=" * 80)
    print("EXP-152 Step 2c: Writer Instruction Analysis")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    for writer_addr in WRITER_ADDRS:
        print(f"\n{'='*80}")
        print(f"Writer at 0x{writer_addr:X}")
        print(f"{'='*80}")
        
        # Show context (32 bytes before and after)
        foff = runtime_to_file(segments, writer_addr, PRX_BASE)
        if foff:
            context_start = max(0, foff - 32)
            context = data[context_start:foff + 32]
            print(f"Context (32 bytes before, 32 after):")
            for i in range(0, len(context), 16):
                addr = writer_addr - 32 + i
                hex_str = ' '.join(f'{b:02X}' for b in context[i:i+16])
                print(f"  0x{addr:X}: {hex_str}")
        
        # Find function start
        func_start = find_function_start(data, segments, writer_addr, PRX_BASE)
        if func_start:
            print(f"\nFunction starts at 0x{func_start:X} (writer is at offset +0x{writer_addr - func_start:X})")
            
            # Read function prologue
            func_foff = runtime_to_file(segments, func_start, PRX_BASE)
            if func_foff:
                chunk = data[func_foff:func_foff + 64]
                print(f"Function prologue: {chunk[:32].hex()}")
                
                # Find CALLs in the function (first 512 bytes)
                print(f"\nCALLs in function (first 512 bytes):")
                for i in range(min(512, len(chunk) - 5)):
                    if chunk[i] == 0xE8:
                        rel = struct.unpack_from('<i', chunk, i + 1)[0]
                        call_addr = func_start + i
                        target = call_addr + 5 + rel
                        if 0x804CD5000 <= target < 0x810000000:
                            # Follow JMP thunks
                            real_target = follow_jmp(data, segments, target, PRX_BASE)
                            if real_target != target:
                                print(f"  0x{call_addr:X}: call 0x{target:X} -> 0x{real_target:X}")
                            else:
                                print(f"  0x{call_addr:X}: call 0x{target:X}")
            
            # Find callers of this function
            print(f"\nCallers of function 0x{func_start:X}:")
            callers = find_callers_of(data, segments, func_start, PRX_BASE)
            print(f"  Direct callers: {len(callers)}")
            for c in callers[:10]:
                # Find the calling function
                caller_func = find_function_start(data, segments, c, PRX_BASE)
                if caller_func:
                    print(f"    CALL at 0x{c:X} (in function 0x{caller_func:X})")
                else:
                    print(f"    CALL at 0x{c:X}")
            
            if len(callers) == 0:
                # Check if called via thunk
                print(f"  No direct callers — searching for thunks...")
                # Search for JMP to this function
                for seg in segments:
                    if seg['type'] != 1 or not (seg['flags'] & 1):
                        continue
                    for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
                        if data[i] == 0xE9:
                            rel = struct.unpack_from('<i', data, i + 1)[0]
                            jmp_addr = PRX_BASE + seg['vaddr'] + (i - seg['offset'])
                            target = jmp_addr + 5 + rel
                            if target == func_start:
                                print(f"    JMP thunk at 0x{jmp_addr:X}")
                                # Find callers of this thunk
                                thunk_callers = find_callers_of(data, segments, jmp_addr, PRX_BASE)
                                print(f"    Thunk callers: {len(thunk_callers)}")
                                for tc in thunk_callers[:5]:
                                    tc_func = find_function_start(data, segments, tc, PRX_BASE)
                                    print(f"      CALL at 0x{tc:X} (in function 0x{tc_func:X})")
                                break
        else:
            print(f"Could not find function start")
    
    # ===== Analyze the writer functions more deeply =====
    print(f"\n{'='*80}")
    print(f"Summary: Writer functions and their reachability")
    print(f"{'='*80}")
    
    for writer_addr in WRITER_ADDRS:
        func_start = find_function_start(data, segments, writer_addr, PRX_BASE)
        if func_start:
            callers = find_callers_of(data, segments, func_start, PRX_BASE)
            print(f"\n  Writer 0x{writer_addr:X} in function 0x{func_start:X}:")
            print(f"    Direct callers: {len(callers)}")
            if len(callers) == 0:
                # Check thunks
                for seg in segments:
                    if seg['type'] != 1 or not (seg['flags'] & 1):
                        continue
                    for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
                        if data[i] == 0xE9:
                            rel = struct.unpack_from('<i', data, i + 1)[0]
                            jmp_addr = PRX_BASE + seg['vaddr'] + (i - seg['offset'])
                            target = jmp_addr + 5 + rel
                            if target == func_start:
                                thunk_callers = find_callers_of(data, segments, jmp_addr, PRX_BASE)
                                print(f"    Via thunk 0x{jmp_addr:X}: {len(thunk_callers)} callers")
                                break

if __name__ == '__main__':
    main()
