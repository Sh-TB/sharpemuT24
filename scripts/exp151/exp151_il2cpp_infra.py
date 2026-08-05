#!/usr/bin/env python3
"""
EXP-151: Find the function that references il2cpp_runtime_invoke string
and analyze the IL2CPP method invocation infrastructure.
"""

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

def find_function_start(data, foff):
    """Find function start by searching backward for prologue."""
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
    print("EXP-151: IL2CPP Method Invocation Infrastructure Analysis")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    # The LEA at 0x804ED7171 references 'il2cpp_runtime_invoke' string
    lea_addr = 0x804ED7171
    lea_foff = runtime_to_file(segments, lea_addr, PRX_BASE)
    
    print(f"\nLEA to 'il2cpp_runtime_invoke' at 0x{lea_addr:X} (file: 0x{lea_foff:X})")
    
    # Find function start
    back = find_function_start(data, lea_foff)
    if back is not None:
        func_start = lea_addr - back
        func_foff = lea_foff - back
        print(f"Function starts at 0x{func_start:X} (back {back} bytes)")
        
        # Read first 512 bytes
        chunk = data[func_foff:func_foff + 512]
        print(f"First 128 bytes: {chunk[:128].hex()}")
        
        # Find CALLs
        print(f"\nCALL instructions in first 512 bytes:")
        for i in range(min(512, len(chunk) - 5)):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = func_start + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:
                    print(f"  0x{call_addr:X}: call 0x{target:X}")
        
        # Find LEAs
        print(f"\nLEA instructions in first 512 bytes:")
        for i in range(min(512, len(chunk) - 7)):
            b0 = chunk[i]
            b1 = chunk[i + 1] if i + 1 < len(chunk) else 0
            if b0 in (0x48, 0x4C) and b1 == 0x8D:
                modrm = chunk[i + 2]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod == 0 and rm == 5:
                    disp = struct.unpack_from('<i', chunk, i + 3)[0]
                    lea_addr2 = func_start + i
                    target = lea_addr2 + 7 + disp
                    reg = (modrm >> 3) & 7
                    regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']
                    rex_r = (b0 >> 2) & 1
                    reg_name = regs[reg + (rex_r * 8)] if reg + (rex_r * 8) < 16 else f'r{reg + (rex_r * 8)}'
                    print(f"  0x{lea_addr2:X}: lea {reg_name}, [rip+0x{disp:X}] -> 0x{target:X}")
    
    # ===== Search for the IL2CPP codegen initialize pattern =====
    print("\n" + "=" * 80)
    print("Searching for IL2CPP codegen patterns")
    print("=" * 80)
    
    # The gate function at 0x804FB8E60 is called 59,744 times
    # This is the "il2cpp_codegen_initialize_runtime_metadata" or similar
    # Let's check what the callers look like
    
    # Find callers of the thunk 0x804FA6030
    thunk_addr = 0x804FA6030
    callers = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
            if data[i] == 0xE8:
                rel = struct.unpack_from('<i', data, i + 1)[0]
                call_addr = PRX_BASE + seg['vaddr'] + (i - seg['offset'])
                target = call_addr + 5 + rel
                if target == thunk_addr:
                    callers.append(call_addr)
    
    print(f"\nThunk 0x{thunk_addr:X} has {len(callers)} callers")
    
    # Show the first 5 callers with context
    print(f"\nFirst 5 callers with context:")
    for c in callers[:5]:
        c_foff = runtime_to_file(segments, c, PRX_BASE)
        if c_foff:
            # Read 16 bytes before and 16 after the CALL
            chunk = data[max(0, c_foff - 16):c_foff + 21]
            print(f"\n  Caller at 0x{c:X}:")
            for i in range(0, len(chunk), 16):
                addr = c - 16 + i
                hex_str = ' '.join(f'{b:02X}' for b in chunk[i:i+16])
                print(f"    0x{addr:X}: {hex_str}")
    
    # ===== Analyze the gate function's actual purpose =====
    print("\n" + "=" * 80)
    print("Gate function purpose analysis")
    print("=" * 80)
    
    # The gate at 0x804FB8E60:
    # 83 3D 31 ED DA 03 00   cmp byte [rip+0x3DAED31], 0
    # 74 28                   je +0x28  (-> 0x804FB8E91 = ret)
    # B8 12 0F 00 00          mov eax, 0x0F12
    # BA 01 00 00 00          mov edx, 1
    # 48 8D 0D 1E C8 B9 03    lea rcx, [rip+0x3B9C81E]  -> 0x808B55698
    # C4 E2 F8 F7 C7          ... (BMI2 instruction: BLSI rdi, rdi?)
    # 48 C1 EF 0C             shr rdi, 12
    # C4 E2 C1 F7 D2          ... (BMI2 instruction)
    # F0 48 09 94 C1 D8 64 04 00  lock or [rcx+r8*8+0x464D8], rdx
    # C3                      ret
    
    # Actually, let me decode the BMI2 instructions:
    # C4 E2 F8 F7 C7 = BLSI rdi, rdi (extract lowest set bit)
    # Wait, VEX prefix C4 E2 F8 = VEX.4F.01.F8
    # Actually this is: C4 E2 F8 F7 /r = BLSI r64, r/m64
    # modrm = C7 = mod=3, reg=0, rm=7 → BLSI rdi, rdi
    
    # C4 E2 C1 F7 D2 = BLSR rdx, rdx (reset lowest set bit)
    # VEX.4F.01.C1: C4 E2 C1 F7 /r = BLSR r64, r/m64
    # modrm = D2 = mod=3, reg=2, rm=2 → BLSR rdx, rdx
    
    # So the full sequence is:
    # 1. Check byte[type_index] == 0
    # 2. If 0, return (type not initialized)
    # 3. eax = 0x0F12 (method token or hash?)
    # 4. edx = 1 (bit to set)
    # 5. rcx = flag_array_base (0x808B55698)
    # 6. BLSI rdi, rdi → rdi = lowest set bit of rdi (isolate a bit)
    # 7. shr rdi, 12 → shift right by 12
    # 8. BLSR rdx, rdx → rdx = rdx with lowest set bit cleared
    # 9. lock or [rcx+r8*8+0x464D8], rdx → set bit in flag array
    # 10. ret
    
    # This is a complex bit manipulation. The function:
    # - Checks if a type is initialized (byte != 0)
    # - If initialized, marks a method as "executed" in a flag array
    # - Returns
    
    # The method index comes from r8 (passed by caller)
    # The flag array is at rcx + r8*8 + 0x464D8
    
    # This is likely the IL2CPP "method initialized" tracking
    # After a method runs for the first time, it's marked as "initialized"
    
    print("""
Gate function decoded:
  cmp byte [0x808D67B98], 0    ; check type initialized flag
  je ret                        ; if 0 (not init), return early
  mov eax, 0x0F12               ; method token/hash
  mov edx, 1                    ; bit to set
  lea rcx, [0x808B55698]        ; flag array base
  BLSI rdi, rdi                 ; isolate lowest set bit of rdi
  shr rdi, 12                   ; shift right 12
  BLSR rdx, rdx                 ; clear lowest set bit of rdx
  lock or [rcx+r8*8+0x464D8], rdx  ; mark method as executed
  ret

INTERPRETATION:
  This is the IL2CPP "method execution tracker".
  - It checks if the type is initialized (byte != 0)
  - If initialized, it marks the method as executed in a flag array
  - If NOT initialized (byte == 0), it returns without marking

The byte at 0x808D67B98 is the TYPE INITIALIZED flag.
It should be set by the type's .cctor (static constructor).

The .cctor is called via TryCallGuestFunction.
If TryCallGuestFunction doesn't propagate RAX correctly (EXP-138 bug),
the .cctor may not complete properly, and the flag is never set.

This is the ROOT CAUSE:
  EXP-138 RAX bug → .cctor doesn't set type flag → gate returns early
  → methods never marked as executed → PlayerLoop.Initialize never runs
  → no bootstrap job → WaitSema(0x81) deadlock
""")
    
    # ===== Check if the gate byte is a known IL2CPP structure =====
    print("=" * 80)
    print("Checking gate byte address against IL2CPP structures")
    print("=" * 80)
    
    # The gate byte is at 0x808D67B98
    # PRX base is 0x804CD5000
    # Offset from PRX base = 0x808D67B98 - 0x804CD5000 = 0x4092B98
    
    # The flag array base is at 0x808B55698
    # Offset from PRX base = 0x808B55698 - 0x804CD5000 = 0x3E80698
    
    # The flag array entries are at [rcx + r8*8 + 0x464D8]
    # For rcx = 0x808B55698:
    #   Entry 0: 0x808B55698 + 0*8 + 0x464D8 = 0x808B9BB70
    #   Entry 1: 0x808B55698 + 1*8 + 0x464D8 = 0x808B9BB78
    
    # The gate byte at 0x808D67B98 is at offset 0x464D8 + N*8 from the flag array base
    # 0x808D67B98 - 0x808B55698 = 0x212500
    # 0x212500 - 0x464D8 = 0x1CC028
    # 0x1CC028 / 8 = 0x39805 (entry 235013)
    
    # Wait, that doesn't match. The gate byte is checked separately from the flag array.
    # The gate byte is at 0x808D67B98 (BSS)
    # The flag array is at 0x808B55698 + 0x464D8 (also BSS?)
    
    gate_byte = 0x808D67B98
    flag_array_base = 0x808B55698
    flag_array_offset = 0x464D8
    
    print(f"\nGate byte: 0x{gate_byte:X} (offset 0x{gate_byte - PRX_BASE:X} from PRX base)")
    print(f"Flag array base: 0x{flag_array_base:X} (offset 0x{flag_array_base - PRX_BASE:X})")
    print(f"Flag array offset: 0x{flag_array_offset:X}")
    print(f"Flag array entry 0: 0x{flag_array_base + flag_array_offset:X}")
    print(f"Flag array entry 1: 0x{flag_array_base + flag_array_offset + 8:X}")
    
    # Check if both are in BSS
    for name, addr in [("Gate byte", gate_byte), ("Flag array base", flag_array_base), 
                       ("Flag array entry 0", flag_array_base + flag_array_offset)]:
        vaddr = addr - PRX_BASE
        for seg in segments:
            if seg['type'] == 1:
                end = seg['vaddr'] + seg['memsz']
                if seg['vaddr'] <= vaddr < end:
                    file_backed = seg['vaddr'] + seg['filesz']
                    if vaddr < file_backed:
                        print(f"  {name}: in file-backed data (vaddr=0x{vaddr:X})")
                    else:
                        print(f"  {name}: in BSS (vaddr=0x{vaddr:X}, beyond file-backed 0x{file_backed:X})")
                    break


if __name__ == '__main__':
    main()
