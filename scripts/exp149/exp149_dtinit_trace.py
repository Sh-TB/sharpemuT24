#!/usr/bin/env python3
"""
EXP-149 Step 4c: Trace dt_init thunks and find the real IL2CPP init path.
dt_init calls JMP thunks (0xE9) that redirect to real functions.
"""

import struct

PRX_PATH = "/tmp/exp125_games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
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
        segments.append({'type': p_type, 'flags': p_flags, 'offset': p_offset,
                         'vaddr': p_vaddr, 'filesz': p_filesz})
    return data, segments

def runtime_to_file(segments, runtime, load_base):
    vaddr = runtime - load_base
    for seg in segments:
        if seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
            return seg['offset'] + (vaddr - seg['vaddr'])
    return None

def follow_jmp(data, segments, addr, load_base, depth=0, visited=None):
    """Follow JMP thunks to find the real function."""
    if visited is None:
        visited = set()
    if addr in visited or depth > 10:
        return addr
    visited.add(addr)
    
    foff = runtime_to_file(segments, addr, load_base)
    if foff is None or foff >= len(data) - 5:
        return addr
    
    # Check if first byte is JMP rel32 (E9)
    if data[foff] == 0xE9:
        rel = struct.unpack_from('<i', data, foff + 1)[0]
        target = addr + 5 + rel
        return follow_jmp(data, segments, target, load_base, depth + 1, visited)
    
    return addr

def main():
    print("=" * 80)
    print("EXP-149 Step 4c: Trace dt_init Thunks to Real Functions")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    # dt_init calls these functions (from previous analysis):
    dt_init_calls = [
        0x804FA6470,
        0x804FA6480,
        0x804FA60D0,
        0x804FA6030,
        0x804F48390,
        0x804FA6450,
        0x804FA6290,
        0x804FA62C0,
        0x804FA6430,
        0x804FC29A0,
        0x804FC29D0,
        0x804FA6400,
        0x804FC2990,
    ]
    
    print("\n[1] Following JMP thunks from dt_init calls:")
    for call_target in dt_init_calls:
        real_func = follow_jmp(data, segments, call_target, PRX_BASE)
        if real_func != call_target:
            print(f"  0x{call_target:X} → JMP → 0x{real_func:X}")
        else:
            print(f"  0x{call_target:X} (direct function, no thunk)")
    
    # Now analyze the real functions
    print("\n[2] Analyzing real functions (after thunk resolution):")
    real_funcs = set()
    for call_target in dt_init_calls:
        real_func = follow_jmp(data, segments, call_target, PRX_BASE)
        real_funcs.add(real_func)
    
    for func_addr in sorted(real_funcs):
        foff = runtime_to_file(segments, func_addr, PRX_BASE)
        if foff and foff < len(data) - 32:
            chunk = data[foff:foff + 64]
            print(f"\n  Function at 0x{func_addr:X} (file: 0x{foff:X}):")
            print(f"    First 32 bytes: {chunk[:32].hex()}")
            # Find CALL instructions in first 256 bytes
            print(f"    CALL instructions in first 256 bytes:")
            for i in range(min(256, len(chunk) - 5)):
                if chunk[i] == 0xE8:
                    rel = struct.unpack_from('<i', chunk, i + 1)[0]
                    call_addr = func_addr + i
                    target = call_addr + 5 + rel
                    if 0x804CD5000 <= target < 0x810000000:
                        # Follow thunk
                        real_target = follow_jmp(data, segments, target, PRX_BASE)
                        if real_target != target:
                            print(f"      0x{call_addr:X}: call 0x{target:X} → 0x{real_target:X}")
                        else:
                            print(f"      0x{call_addr:X}: call 0x{target:X}")
    
    # ===== Key function: 0x804F48390 (real function, not thunk) =====
    print("\n[3] Deep analysis of 0x804F48390 (called by dt_init, real function):")
    func_addr = 0x804F48390
    foff = runtime_to_file(segments, func_addr, PRX_BASE)
    if foff:
        chunk = data[foff:foff + 1024]
        print(f"  File offset: 0x{foff:X}")
        print(f"  First 128 bytes: {chunk[:128].hex()}")
        print(f"  CALL instructions in first 1024 bytes:")
        for i in range(min(1024, len(chunk) - 5)):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = func_addr + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:
                    real_target = follow_jmp(data, segments, target, PRX_BASE)
                    if real_target != target:
                        print(f"    0x{call_addr:X}: call 0x{target:X} → 0x{real_target:X}")
                    else:
                        print(f"    0x{call_addr:X}: call 0x{target:X}")
    
    # ===== Check what the dispatch loop callers call BEFORE the dispatch loop =====
    print("\n[4] What do dispatch loop callers do BEFORE calling dispatch loop?")
    dispatch_caller_funcs = [0x804F455B0, 0x804F45650, 0x804FA1D60, 0x804FA2130, 0x804FA2160]
    
    for func_addr in dispatch_caller_funcs:
        foff = runtime_to_file(segments, func_addr, PRX_BASE)
        if foff:
            chunk = data[foff:foff + 512]
            print(f"\n  Function 0x{func_addr:X}:")
            print(f"    First 64 bytes: {chunk[:64].hex()}")
            # Find all CALL instructions
            calls = []
            for i in range(min(512, len(chunk) - 5)):
                if chunk[i] == 0xE8:
                    rel = struct.unpack_from('<i', chunk, i + 1)[0]
                    call_addr = func_addr + i
                    target = call_addr + 5 + rel
                    if 0x804CD5000 <= target < 0x810000000:
                        calls.append((call_addr, target))
            print(f"    CALLs: {len(calls)}")
            for ca, ct in calls[:10]:
                real_target = follow_jmp(data, segments, ct, PRX_BASE)
                if real_target != ct:
                    print(f"      0x{ca:X}: call 0x{ct:X} → 0x{real_target:X}")
                else:
                    print(f"      0x{ca:X}: call 0x{ct:X}")
    
    # ===== Find what calls 0x804F48390 (the real function called by dt_init) =====
    print("\n[5] Finding all callers of 0x804F48390:")
    target_addr = 0x804F48390
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        for i in range(seg['offset'], seg['offset'] + seg['filesz'] - 5):
            if i >= len(data):
                break
            if data[i] == 0xE8:
                rel = struct.unpack_from('<i', data, i + 1)[0]
                call_addr = PRX_BASE + seg['vaddr'] + (i - seg['offset'])
                t = call_addr + 5 + rel
                if t == target_addr:
                    # Find function start
                    func_start = None
                    for back in range(0, 2048):
                        if i - back < 0:
                            break
                        if data[i - back:i - back + 4] == b'\x55\x48\x89\xe5':
                            if i - back - 1 >= 0 and data[i - back - 1] in (0xCC, 0xC3, 0xC9):
                                func_start = call_addr - back
                                break
                    print(f"  Called from 0x{call_addr:X} (in function 0x{func_start:X})" if func_start else f"  Called from 0x{call_addr:X}")
    
    print("\n" + "=" * 80)
    print("Analysis Complete")
    print("=" * 80)

if __name__ == '__main__':
    main()
