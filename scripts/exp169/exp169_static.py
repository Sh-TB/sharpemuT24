#!/usr/bin/env python3
"""EXP-169 TEST 1+2+4: Static analysis of caller, all callers, and paths to init."""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
EBOOT_BASE = 0x800000000
TARGET_FUNC = 0x8013FCE40
INIT_WRITE = 0x8013FD08E
MAIN_ENTRY = 0x800000070

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

def find_callers(data, segments, target, base):
    callers = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1): continue
        for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
            if data[i] == 0xE8:
                rel = struct.unpack_from('<i', data, i + 1)[0]
                call_addr = base + seg['vaddr'] + (i - seg['offset'])
                t = call_addr + 5 + rel
                if t == target:
                    callers.append(call_addr)
    return callers

def find_func_start(data, foff):
    for back in range(0, 8192):
        if foff - back < 0: return None
        if foff - back + 4 <= len(data):
            b = data[foff - back:foff - back + 4]
            if b == b'\x55\x48\x89\xe5':
                if foff - back - 1 >= 0:
                    prev = data[foff - back - 1]
                    if prev in (0xCC, 0xC3, 0xC9): return back
    return None

def main():
    data, segments = parse_elf64(EBOOT_PATH)
    
    # ===== TEST 2: Find ALL callers of 0x8013FCE40 =====
    print("=" * 80)
    print("TEST 2: Find All Callers of 0x%X" % TARGET_FUNC)
    print("=" * 80)
    
    callers = find_callers(data, segments, TARGET_FUNC, EBOOT_BASE)
    print("\nTotal direct CALL references: %d" % len(callers))
    for c in callers:
        foff = runtime_to_file(segments, c, EBOOT_BASE)
        fb = find_func_start(data, foff) if foff else None
        func = c - fb if fb is not None else 0
        print("  CALL at 0x%X (in function 0x%X)" % (c, func))
    
    # ===== TEST 1: Analyze caller function 0x800000070 =====
    print("\n" + "=" * 80)
    print("TEST 1: Analyze Caller 0x%X (eboot main)" % MAIN_ENTRY)
    print("=" * 80)
    
    main_foff = runtime_to_file(segments, MAIN_ENTRY, EBOOT_BASE)
    if main_foff:
        chunk = data[main_foff:main_foff + 192]
        print("\nFirst 192 bytes of eboot main:")
        for i in range(0, 192, 16):
            addr = MAIN_ENTRY + i
            hex_str = ' '.join('%02X' % b for b in chunk[i:i+16])
            print("  0x%X (+0x%02X): %s" % (addr, i, hex_str))
        
        # Decode the full function up to the CALL at +0x3A
        print("\nDecoded instructions (up to CALL at +0x3A):")
        i = 0
        while i < 0x40:
            b0 = chunk[i]
            b1 = chunk[i+1] if i+1 < len(chunk) else 0
            b2 = chunk[i+2] if i+2 < len(chunk) else 0
            addr = MAIN_ENTRY + i
            
            if b0 == 0x55: print("  +0x%02X: push rbp" % i); i += 1; continue
            if b0 == 0x48 and b1 == 0x89 and b2 == 0xE5: print("  +0x%02X: mov rbp, rsp" % i); i += 3; continue
            if b0 == 0x41 and 0x50 <= b1 <= 0x57:
                regs = ['r8','r9','r10','r11','r12','r13','r14','r15']
                print("  +0x%02X: push %s" % (i, regs[b1-0x50])); i += 2; continue
            if b0 == 0x53: print("  +0x%02X: push rbx" % i); i += 1; continue
            if b0 == 0x50: print("  +0x%02X: push rax" % i); i += 1; continue
            
            # 44 8B 37 = mov r14d, [rdi]
            if b0 == 0x44 and b1 == 0x8B and b2 == 0x37:
                print("  +0x%02X: mov r14d, [rdi]  ; *** reads argc from args struct" % i); i += 3; continue
            # 48 89 F3 = mov rbx, rsi
            if b0 == 0x48 and b1 == 0x89 and b2 == 0xF3:
                print("  +0x%02X: mov rbx, rsi  ; rbx = argv (second arg)" % i); i += 3; continue
            # 4C 8D 7F 08 = lea r15, [rdi+8]
            if b0 == 0x4C and b1 == 0x8D and b2 == 0x7F:
                imm = chunk[i+3]
                print("  +0x%02X: lea r15, [rdi+0x%X]  ; r15 = &argv[0]" % (i, imm)); i += 4; continue
            
            # E8 = call
            if b0 == 0xE8:
                rel = struct.unpack_from('<i', chunk, i+1)[0]
                target = addr + 5 + rel
                print("  +0x%02X: call 0x%X" % (i, target)); i += 5; continue
            
            # 48 89 DF = mov rdi, rbx
            if b0 == 0x48 and b1 == 0x89 and b2 == 0xDF:
                print("  +0x%02X: mov rdi, rbx" % i); i += 3; continue
            # 44 89 F7 = mov rdi, r14
            if b0 == 0x44 and b1 == 0x89 and b2 == 0xF7:
                print("  +0x%02X: mov rdi, r14  ; *** rdi = r14 = argc" % i); i += 3; continue
            # 4C 89 FE = mov rsi, r15
            if b0 == 0x4C and b1 == 0x89 and b2 == 0xFE:
                print("  +0x%02X: mov rsi, r15  ; rsi = r15 = &argv[0]" % i); i += 3; continue
            # 31 D2 = xor edx, edx
            if b0 == 0x31 and b1 == 0xD2:
                print("  +0x%02X: xor edx, edx  ; rdx = 0" % i); i += 2; continue
            # 48 8D 3D = lea rdi, [rip+disp32]
            if b0 == 0x48 and b1 == 0x8D and b2 == 0x3D:
                disp = struct.unpack_from('<i', chunk, i+3)[0]
                target = addr + 7 + disp
                print("  +0x%02X: lea rdi, [0x%X]" % (i, target)); i += 7; continue
            
            # 89 C7 = mov edi, eax
            if b0 == 0x89 and b1 == 0xC7:
                print("  +0x%02X: mov edi, eax" % i); i += 2; continue
            # 89 C3 = mov ebx, eax
            if b0 == 0x89 and b1 == 0xC3:
                print("  +0x%02X: mov ebx, eax" % i); i += 2; continue
            
            print("  +0x%02X: byte 0x%02X" % (i, b0)); i += 1
    
    # ===== TEST 4: Check paths to init write =====
    print("\n" + "=" * 80)
    print("TEST 4: Check If Init Can Be Reached Naturally")
    print("=" * 80)
    
    # The function 0x8013FCE40 has only 1 caller (0x800000070)
    # Inside the function, the init write at +0x24E is skipped by jl at +0x91
    # The jl condition is r13d < 2, where r13d = ebx = edi
    # edi = r14 = [rdi] from caller, where rdi is the first arg to main
    
    print("\nFunction 0x%X has %d caller(s):" % (TARGET_FUNC, len(callers)))
    for c in callers:
        print("  0x%X" % c)
    
    print("\nThe only path to 0x8013FCE40 is from eboot main at 0x8000000AA")
    print("The argument rdi = r14 = [main_rdi]")
    print("main_rdi is set by the PS5 loader (SharpEmu's loader)")
    print("")
    print("For init to be reached, r13d must be >= 2")
    print("r13d = edi = r14d = [main_rdi]")
    print("So [main_rdi] must be >= 2")
    print("")
    print("If [main_rdi] is argc (argument count), then argc must be >= 2")
    print("This means the game must be launched with at least 2 arguments")
    print("On PS5, games are typically launched with argc=1 (just the program path)")
    print("")
    print("This suggests [main_rdi] is NOT argc — it's a different loader parameter")
    print("On real PS5, the loader may pass an initialization level or module count")

if __name__ == '__main__':
    main()
