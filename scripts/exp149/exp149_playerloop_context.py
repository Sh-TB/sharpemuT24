#!/usr/bin/env python3
"""
EXP-149 Step 4b: Analyze PlayerLoop strings in eboot and dt_init call chain.
"""

import struct

PRX_PATH = "/tmp/exp125_games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
EBOOT_PATH = "/tmp/exp125_games/yatzi/eboot.bin"
PRX_BASE = 0x804CD5000
EBOOT_BASE = 0x800000000

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

def read_string_at(data, offset, max_len=256):
    result = []
    for i in range(max_len):
        if offset + i >= len(data):
            break
        b = data[offset + i]
        if b == 0:
            break
        if 32 <= b < 127:
            result.append(chr(b))
        else:
            result.append(f'\\x{b:02X}')
    return ''.join(result)

def main():
    print("=" * 80)
    print("EXP-149 Step 4b: PlayerLoop Strings + dt_init Call Chain Analysis")
    print("=" * 80)
    
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    
    # ===== PlayerLoop strings in eboot =====
    print("\n[1] PlayerLoop strings in eboot:")
    playerloop_strs = [
        (0x801B22270, "PlayerLoop"),
        (0x801B90C4B, "PlayerLoop"),
        (0x801B4D292, "PlayerLoopInternal"),
        (0x801BD21F6, "PlayerLoopInternal"),
        (0x801BE2F04, "PlayerLoopInternal"),
    ]
    
    for addr, expected in playerloop_strs:
        foff = runtime_to_file(eboot_segs, addr, EBOOT_BASE)
        if foff:
            s = read_string_at(eboot_data, foff, 128)
            print(f"  0x{addr:X}: '{s}'")
    
    # ===== Find what references these PlayerLoop strings =====
    print("\n[2] Finding references to PlayerLoop strings:")
    for addr, _ in playerloop_strs:
        # Search for 64-bit LE reference to this address
        ref_bytes = struct.pack('<Q', addr)
        print(f"\n  Searching for 64-bit ref to 0x{addr:X}...")
        for seg in eboot_segs:
            if seg['type'] != 1:
                continue
            seg_data = eboot_data[seg['offset']:seg['offset'] + seg['filesz']]
            idx = 0
            while True:
                i = seg_data.find(ref_bytes, idx)
                if i == -1:
                    break
                ref_runtime = EBOOT_BASE + seg['vaddr'] + i
                seg_type = 'CODE' if seg['flags'] & 1 else ('DATA-W' if seg['flags'] & 2 else 'DATA-R')
                print(f"    Ref at 0x{ref_runtime:X} ({seg_type})")
                idx = i + 1
    
    # ===== dt_init call chain analysis =====
    print("\n[3] dt_init (module_start) call chain analysis:")
    dt_init = 0x804CD5010
    
    # The dt_init calls several functions. Let's identify them.
    # From the previous output:
    calls_in_dt_init = [
        (0x804CD507D, 0x851CCD9CE),   # Likely a relative call that wrapped around
        (0x804CD50E5, 0x804FA6470),
        (0x804CD50F6, 0x804FA6470),
        (0x804CD5141, 0x804FA60D0),
        (0x804CD5160, 0x804FA6480),
        (0x804CD5174, 0x804FA6480),
        (0x804CD517F, 0x804FA6030),
        (0x804CD5191, 0x804FA6480),
        (0x804CD51AB, 0x804FA6480),
        (0x804CD51B6, 0x804FA6030),
        (0x804CD51EC, 0x804F48390),
        (0x804CD51FC, 0x804F48390),
    ]
    
    # Actually 0x851CCD9CE is way too high — likely a misparse. Let me recalculate.
    # dt_init is at file offset 0x4010 in PRX
    dt_foff = runtime_to_file(prx_segs, dt_init, PRX_BASE)
    if dt_foff:
        chunk = prx_data[dt_foff:dt_foff + 1024]
        print(f"  dt_init at file offset 0x{dt_foff:X}, reading 1024 bytes")
        print(f"  CALL instructions:")
        for i in range(len(chunk) - 5):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = dt_init + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:  # Valid PRX range
                    print(f"    0x{call_addr:X}: call 0x{target:X}")
    
    # ===== Check what 0x804FA6470, 0x804FA6480, 0x804FA60D0, 0x804FA6030, 0x804F48390 are =====
    print("\n[4] Identifying functions called by dt_init:")
    called_funcs = [0x804FA6470, 0x804FA6480, 0x804FA60D0, 0x804FA6030, 0x804F48390]
    
    for func_addr in called_funcs:
        foff = runtime_to_file(prx_segs, func_addr, PRX_BASE)
        if foff:
            chunk = prx_data[foff:foff + 64]
            print(f"\n  Function at 0x{func_addr:X} (file: 0x{foff:X}):")
            print(f"    First 32 bytes: {chunk[:32].hex()}")
            # Check if it starts with push rbp
            if chunk[0] == 0x55:
                print(f"    Starts with push rbp (function prologue)")
    
    # ===== Find the function that calls dispatch loop (0x804F6E510) =====
    # From EXP-148, the 5 callers are:
    # 0x804F455B0, 0x804F45650, 0x804FA1D60, 0x804FA2130, 0x804FA2160
    # Let's check which of these is reachable from dt_init
    
    print("\n[5] Checking if dt_init call chain reaches dispatch loop callers:")
    dispatch_callers = [0x804F455B0, 0x804F45650, 0x804FA1D60, 0x804FA2130, 0x804FA2160]
    
    for caller_func in dispatch_callers:
        # Check if any of the dt_init-called functions match
        print(f"\n  Dispatch loop caller: 0x{caller_func:X}")
        # Find callers of this function
        caller_bytes = b'\xE8'  # CALL rel32
        # We need to search for E8 rel32 where call_addr + 5 + rel = caller_func
        for seg in prx_segs:
            if seg['type'] != 1 or not (seg['flags'] & 1):
                continue
            for i in range(seg['offset'], seg['offset'] + seg['filesz'] - 5):
                if i >= len(prx_data):
                    break
                if prx_data[i] == 0xE8:
                    rel = struct.unpack_from('<i', prx_data, i + 1)[0]
                    call_addr = PRX_BASE + seg['vaddr'] + (i - seg['offset'])
                    target = call_addr + 5 + rel
                    if target == caller_func:
                        print(f"    Called from 0x{call_addr:X}")
    
    # ===== Check the GC thread entry function =====
    print("\n[6] GC thread entry (0x804F88AA0) analysis:")
    gc_entry = 0x804F88AA0
    gc_foff = runtime_to_file(prx_segs, gc_entry, PRX_BASE)
    if gc_foff:
        chunk = prx_data[gc_foff:gc_foff + 256]
        print(f"  File offset: 0x{gc_foff:X}")
        print(f"  First 64 bytes: {chunk[:64].hex()}")
        print(f"  CALL instructions in first 256 bytes:")
        for i in range(len(chunk) - 5):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = gc_entry + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:
                    print(f"    0x{call_addr:X}: call 0x{target:X}")
    
    # ===== Check what's at 0x804FA6030 — this might be il2cpp_init =====
    print("\n[7] Checking 0x804FA6030 (called by dt_init, might be il2cpp_init):")
    func_addr = 0x804FA6030
    foff = runtime_to_file(prx_segs, func_addr, PRX_BASE)
    if foff:
        chunk = prx_data[foff:foff + 512]
        print(f"  File offset: 0x{foff:X}")
        print(f"  First 128 bytes: {chunk[:128].hex()}")
        print(f"  CALL instructions in first 512 bytes:")
        for i in range(len(chunk) - 5):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = func_addr + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:
                    print(f"    0x{call_addr:X}: call 0x{target:X}")
    
    # ===== Check the PlayerLoop string context =====
    print("\n[8] PlayerLoop string context in eboot:")
    # Read 256 bytes around each PlayerLoop string
    for addr, _ in playerloop_strs[:2]:
        foff = runtime_to_file(eboot_segs, addr, EBOOT_BASE)
        if foff:
            # Read 128 bytes before and after
            start = max(0, foff - 64)
            chunk = eboot_data[start:foff + 192]
            print(f"\n  Context around 0x{addr:X}:")
            # Find all null-terminated strings in this region
            i = 0
            while i < len(chunk):
                # Skip null bytes
                while i < len(chunk) and chunk[i] == 0:
                    i += 1
                if i >= len(chunk):
                    break
                # Read string
                s_start = i
                while i < len(chunk) and chunk[i] != 0:
                    i += 1
                s = chunk[s_start:i]
                if len(s) > 3 and all(32 <= b < 127 for b in s):
                    str_addr = addr - 64 + s_start
                    print(f"    0x{str_addr:X}: '{s.decode('ascii', errors='replace')}'")
    
    print("\n" + "=" * 80)
    print("Analysis Complete")
    print("=" * 80)

if __name__ == '__main__':
    main()
