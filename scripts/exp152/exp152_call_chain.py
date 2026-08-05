#!/usr/bin/env python3
"""
EXP-152 Step 3: Trace the call chain from dt_init to the writer function.
Also identify the owner type of the flag.
"""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

WRITER_FUNC = 0x804FB1B90  # Contains the flag writer at 0x804FB1C1B
DT_INIT = 0x804CD5010

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

def find_call_chain(data, segments, start_func, target_func, load_base, depth=0, visited=None, max_depth=5):
    """Find if there's a call chain from start_func to target_func."""
    if visited is None:
        visited = set()
    if start_func in visited or depth > max_depth:
        return None
    visited.add(start_func)
    
    if start_func == target_func:
        return [start_func]
    
    # Find all functions called by start_func
    foff = runtime_to_file(segments, start_func, load_base)
    if foff is None:
        return None
    
    chunk = data[foff:foff + 2048]  # Check first 2048 bytes
    for i in range(len(chunk) - 5):
        if chunk[i] == 0xE8:
            rel = struct.unpack_from('<i', chunk, i + 1)[0]
            call_addr = start_func + i
            target = call_addr + 5 + rel
            if 0x804CD5000 <= target < 0x810000000:
                # Follow JMP thunks
                real_target = follow_jmp(data, segments, target, load_base)
                
                if real_target == target_func:
                    return [start_func, target_func]
                
                # Recursively search
                result = find_call_chain(data, segments, real_target, target_func, load_base, depth + 1, visited.copy(), max_depth)
                if result:
                    return [start_func] + result
    
    return None

def main():
    print("=" * 80)
    print("EXP-152 Step 3: Call Chain Analysis + Owner Type Identification")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    # ===== Trace call chain from dt_init to writer function =====
    print(f"\n[1] Finding call chain from dt_init (0x{DT_INIT:X}) to writer (0x{WRITER_FUNC:X})...")
    
    chain = find_call_chain(data, segments, DT_INIT, WRITER_FUNC, PRX_BASE, max_depth=5)
    if chain:
        print(f"  FOUND CHAIN (depth {len(chain)-1}):")
        for i, func in enumerate(chain):
            print(f"    {'→ ' if i > 0 else '  '}{func:X}")
    else:
        print(f"  No direct call chain found within depth 5")
        print(f"  The writer function may not be reachable from dt_init")
    
    # ===== Analyze the writer function's callers =====
    print(f"\n[2] Analyzing callers of writer function 0x{WRITER_FUNC:X}...")
    
    callers = find_callers_of(data, segments, WRITER_FUNC, PRX_BASE)
    print(f"  Direct callers: {len(callers)}")
    
    for c in callers:
        caller_func = find_function_start(data, segments, c, PRX_BASE)
        if caller_func:
            print(f"\n  Caller function 0x{caller_func:X} (CALL at 0x{c:X}):")
            
            # Find callers of this caller
            parent_callers = find_callers_of(data, segments, caller_func, PRX_BASE)
            print(f"    Parent callers: {len(parent_callers)}")
            for pc in parent_callers[:5]:
                pc_func = find_function_start(data, segments, pc, PRX_BASE)
                print(f"      CALL at 0x{pc:X} (in function 0x{pc_func:X})")
            
            # Check if this is reachable from dt_init
            chain2 = find_call_chain(data, segments, DT_INIT, caller_func, PRX_BASE, max_depth=5)
            if chain2:
                print(f"    *** REACHABLE from dt_init! ***")
                for i, func in enumerate(chain2):
                    print(f"      {'→ ' if i > 0 else '      '}{func:X}")
    
    # ===== Analyze the second condition byte =====
    print(f"\n[3] Analyzing second condition byte at 0x808A75690...")
    cond_byte = 0x808A75690
    cond_vaddr = cond_byte - PRX_BASE
    print(f"  Runtime: 0x{cond_byte:X}")
    print(f"  Vaddr in PRX: 0x{cond_vaddr:X}")
    
    # Check which segment
    for seg in segments:
        if seg['type'] == 1:
            end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= cond_vaddr < end:
                file_backed = seg['vaddr'] + seg['filesz']
                if cond_vaddr < file_backed:
                    byte_foff = seg['offset'] + (cond_vaddr - seg['vaddr'])
                    byte_val = data[byte_foff]
                    print(f"  In file-backed data: value = 0x{byte_val:X}")
                else:
                    print(f"  In BSS (value = 0 at runtime)")
                break
    
    # ===== Search for writes to the condition byte =====
    print(f"\n[4] Searching for writes to condition byte 0x{cond_byte:X}...")
    cond_writers = []
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
                
                # Only check write opcodes
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
                
                base_len = disp_offset + 4
                imm_len = 0
                reg = (modrm >> 3) & 7
                if opcode in (0xC6, 0x80, 0x83):
                    imm_len = 1
                elif opcode in (0xC7, 0x81):
                    imm_len = 4
                
                instr_len = base_len + imm_len
                instr_addr = PRX_BASE + seg['vaddr'] + i
                computed = instr_addr + instr_len + disp
                
                if computed == cond_byte:
                    # Only report actual writes (not cmp which is reg=7)
                    if opcode == 0x83 and reg == 7:
                        continue  # cmp, not write
                    if opcode == 0x80 and reg == 7:
                        continue  # cmp, not write
                    if opcode == 0x81 and reg == 7:
                        continue  # cmp, not write
                    
                    prefix_str = ''
                    if prefix_len == 1:
                        p = seg_data[i]
                        if p == 0xF0: prefix_str = 'lock '
                        elif p in (0x48, 0x4C): prefix_str = 'rex.W '
                    
                    raw = seg_data[i:i+instr_len].hex()
                    cond_writers.append(f"  0x{instr_addr:X}: {prefix_str}write [0x{computed:X}] bytes={raw}")
                    break
    
    print(f"  Found {len(cond_writers)} write instructions")
    for w in cond_writers[:10]:
        print(w)
    
    # ===== Check the writer function's full logic =====
    print(f"\n[5] Full analysis of writer function 0x{WRITER_FUNC:X}...")
    foff = runtime_to_file(segments, WRITER_FUNC, PRX_BASE)
    if foff:
        chunk = data[foff:foff + 256]
        print(f"  First 256 bytes:")
        for i in range(0, min(256, len(chunk)), 16):
            addr = WRITER_FUNC + i
            hex_str = ' '.join(f'{b:02X}' for b in chunk[i:i+16])
            print(f"    0x{addr:X}: {hex_str}")
        
        # The function starts with:
        # 55               push rbp
        # 48 89 E5         mov rbp, rsp
        # 83 3D 1D 60 DB 03 00  cmp byte [0x808D67B98], 0  ; check flag
        # 74 02            je +2 (-> ret)
        # 5D               pop rbp
        # C3               ret
        # ...
        
        # So the function ITSELF checks the flag at the start!
        # If flag == 0: je taken -> pop rbp -> ret (return early, DON'T set flag)
        # If flag != 0: fall through -> continue execution
        
        # Wait, that means:
        # - If flag is 0 (not initialized): return early (DON'T set it!)
        # - If flag is non-zero (already initialized): continue and set it again
        
        # This is a "run-once" guard for the writer function itself!
        # The flag is checked by BOTH:
        # 1. The gate function (0x804FB8E60) - checks before running methods
        # 2. The writer function (0x804FB1B90) - checks before setting the flag
        
        # But BOTH check the SAME byte! If the byte is 0, BOTH return early!
        # The writer never gets a chance to set the flag!
        
        # This is a chicken-and-egg problem:
        # - The flag needs to be non-zero for the writer to run
        # - The writer is the only one that sets the flag
        # - Something ELSE must set the flag initially
        
        # The "something else" is likely:
        # 1. The .cctor (static constructor) - sets the flag via a different path
        # 2. IL2CPP metadata initialization
        # 3. A different function we haven't found
        
        print(f"\n  FUNCTION LOGIC ANALYSIS:")
        print(f"  The writer function 0x{WRITER_FUNC:X} ALSO checks the flag at the start!")
        print(f"  0x{WRITER_FUNC:X}: push rbp; mov rbp, rsp")
        print(f"  0x{WRITER_FUNC+5:X}: cmp byte [0x808D67B98], 0  ; check SAME flag")
        print(f"  0x{WRITER_FUNC+12:X}: je +2 → ret  ; if 0, return early!")
        print(f"  0x{WRITER_FUNC+14:X}: pop rbp; ret")
        print(f"  ... (continues if flag != 0)")
        print(f"")
        print(f"  CHICKEN-AND-EGG PROBLEM:")
        print(f"  - Gate function checks flag → if 0, skip method")
        print(f"  - Writer function checks flag → if 0, return early (DON'T set)")
        print(f"  - Both check the SAME byte!")
        print(f"  - If flag starts at 0, NEITHER runs!")
        print(f"  - Something ELSE must set the flag initially!")
        print(f"")
        print(f"  The initial setter must be:")
        print(f"  - The .cctor (static constructor)")
        print(f"  - IL2CPP type initialization code")
        print(f"  - A function called BEFORE the gate and writer")

if __name__ == '__main__':
    main()
