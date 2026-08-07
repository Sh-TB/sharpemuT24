#!/usr/bin/env python3
"""EXP-166 TEST 2: Static analysis — find all conditional branches between 0x8013FCE40 and 0x8013FD08E."""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
EBOOT_BASE = 0x800000000

FUNC_START = 0x8013FCE40
INIT_WRITE = 0x8013FD08E

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

def main():
    data, segments = parse_elf64(EBOOT_PATH)
    
    # Find file offset
    func_vaddr = FUNC_START - EBOOT_BASE
    foff = None
    for seg in segments:
        if seg['type'] == 1 and seg['vaddr'] <= func_vaddr < seg['vaddr'] + seg['filesz']:
            foff = seg['offset'] + (func_vaddr - seg['vaddr'])
            break
    
    if not foff:
        print("Function not found")
        return
    
    init_offset = INIT_WRITE - FUNC_START  # 0x24E
    print("Function 0x%X, init write at +0x%X (0x%X)" % (FUNC_START, init_offset, INIT_WRITE))
    print("Analyzing first 0x%X bytes..." % (init_offset + 16))
    
    # Read the function up to the init write + some extra
    chunk = data[foff:foff + init_offset + 32]
    
    # Find all conditional branches and global accesses
    branches = []
    globals_accessed = []
    
    i = 0
    while i < len(chunk) - 6:
        b0 = chunk[i]
        b1 = chunk[i+1] if i+1 < len(chunk) else 0
        addr = FUNC_START + i
        
        # Conditional jump rel32 (0F 8x)
        if b0 == 0x0F and 0x80 <= b1 <= 0x8F:
            rel = struct.unpack_from('<i', chunk, i+2)[0]
            target = addr + 6 + rel
            cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b1 - 0x80]
            branches.append((addr, cc, target, i))
            i += 6
            continue
        
        # Conditional jump rel8 (7x)
        if 0x70 <= b0 <= 0x7F:
            rel = struct.unpack_from('<b', chunk, i+1)[0]
            target = addr + 2 + rel
            cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b0 - 0x70]
            branches.append((addr, cc, target, i))
            i += 2
            continue
        
        # CMP byte [rip+disp32], imm8 (83 3D)
        if b0 == 0x83 and b1 == 0x3D:
            disp = struct.unpack_from('<i', chunk, i+2)[0]
            target = addr + 7 + disp
            imm = chunk[i+6]
            # Check if BSS
            tvaddr = target - EBOOT_BASE
            loc = "UNKNOWN"
            for seg in segments:
                if seg['type'] == 1:
                    end = seg['vaddr'] + seg.get('memsz', seg['filesz'])
                    if seg['vaddr'] <= tvaddr < end:
                        fb = seg['vaddr'] + seg['filesz']
                        loc = "BSS(0)" if tvaddr >= fb else "FILE"
                        break
            globals_accessed.append((addr, "cmp byte [0x%X], %d (%s)" % (target, imm, loc), i))
            i += 7
            continue
        
        # MOV reg, [rip+disp32] (48 8B xx or 4C 8B xx)
        if b0 in (0x48, 0x4C) and b1 == 0x8B:
            modrm = chunk[i+2]
            if (modrm >> 6) & 3 == 0 and (modrm & 7) == 5:
                disp = struct.unpack_from('<i', chunk, i+3)[0]
                target = addr + 7 + disp
                reg = (modrm >> 3) & 7
                regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']
                rex_r = (b0 >> 2) & 1
                idx = reg + (rex_r * 8)
                rn = regs[idx] if idx < 16 else 'r%d' % idx
                tvaddr = target - EBOOT_BASE
                loc = "UNKNOWN"
                for seg in segments:
                    if seg['type'] == 1:
                        end = seg['vaddr'] + seg.get('memsz', seg['filesz'])
                        if seg['vaddr'] <= tvaddr < end:
                            fb = seg['vaddr'] + seg['filesz']
                            loc = "BSS(0)" if tvaddr >= fb else "FILE"
                            break
                globals_accessed.append((addr, "mov %s, [0x%X] (%s)" % (rn, target, loc), i))
                i += 7
                continue
        
        # CALL (E8)
        if b0 == 0xE8:
            rel = struct.unpack_from('<i', chunk, i+1)[0]
            target = addr + 5 + rel
            globals_accessed.append((addr, "call 0x%X" % target, i))
            i += 5
            continue
        
        # TEST (85 /r or 48 85 /r)
        if b0 == 0x48 and b1 == 0x85:
            modrm = chunk[i+2]
            if (modrm >> 6) & 3 == 3:
                reg = (modrm >> 3) & 7
                rm = modrm & 7
                regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']
                globals_accessed.append((addr, "test %s, %s" % (regs[reg], regs[rm]), i))
                i += 3
                continue
        
        i += 1
    
    print("\n=== Conditional branches (before init write at +0x%X) ===" % init_offset)
    for addr, cc, target, off in branches:
        direction = "FORWARD" if target > addr else "BACKWARD"
        skip = "*** SKIPS INIT ***" if target > INIT_WRITE else ""
        print("  +0x%03X (0x%X): %s 0x%X (%s) %s" % (off, addr, cc, target, direction, skip))
    
    print("\n=== Global accesses (before init write) ===")
    for addr, desc, off in globals_accessed:
        print("  +0x%03X (0x%X): %s" % (off, addr, desc))
    
    # Identify branches that skip past the init write
    print("\n=== Branches that SKIP the init write ===")
    for addr, cc, target, off in branches:
        if target > INIT_WRITE:
            print("  +0x%03X (0x%X): %s 0x%X — SKIPS init at 0x%X" % (off, addr, cc, target, INIT_WRITE))

if __name__ == '__main__':
    main()
