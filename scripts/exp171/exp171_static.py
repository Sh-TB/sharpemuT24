#!/usr/bin/env python3
"""EXP-171 TEST 2+3: Complete producer search + branch ladder for 0x801E51240."""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
PRX_PATH = "/tmp/exp162_games/Il2cppUserAssemblies.prx"
EBOOT_BASE = 0x800000000
PRX_BASE = 0x804CD5000
TARGET = 0x801E51240
CONSUMER = 0x8013EB6B0
INIT_WRITE_OFFSET = 0x3969  # 0x8013EF019 - 0x8013EB6B0

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

def search_writes(data, segments, target, base, label):
    writes = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1): continue
        sd = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(sd) - 11):
            for plen in range(2):
                if plen == 1 and sd[i] not in (0xF0, 0x48, 0x4C, 0x66): continue
                oc = sd[i + plen]
                if oc not in (0xC6, 0xC7, 0x89, 0x88): continue
                mr = sd[i + plen + 1]
                if (mr >> 6) & 3 != 0 or (mr & 7) != 5: continue
                disp = struct.unpack_from('<i', sd, i + plen + 2)[0]
                ilen = 0
                if oc == 0xC6: ilen = 1
                elif oc == 0xC7: ilen = 4
                total = plen + 2 + 4 + ilen
                addr = base + seg['vaddr'] + i
                comp = addr + total + disp
                if comp == target:
                    foff = seg['offset'] + i
                    fb = find_func_start(data, foff)
                    func = addr - fb if fb is not None else 0
                    if oc == 0xC7:
                        imm = struct.unpack_from('<I', sd, i + plen + 6)[0]
                        writes.append((addr, "mov qword [0x%X], 0x%X" % (comp, imm), func, "clear" if imm == 0 else "init"))
                    elif oc == 0x89:
                        reg = (mr >> 3) & 7
                        regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']
                        rex_r = (sd[i] >> 2) & 1 if plen == 1 else 0
                        idx = reg + (rex_r * 8)
                        rn = regs[idx] if idx < 16 else 'r%d' % idx
                        writes.append((addr, "mov [0x%X], %s" % (comp, rn), func, "init"))
                    break
    return writes

def main():
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    
    print("=" * 80)
    print("TEST 2: Complete Producer Search for 0x%X" % TARGET)
    print("=" * 80)
    
    # Eboot writes
    print("\nEboot writes:")
    ew = search_writes(eboot_data, eboot_segs, TARGET, EBOOT_BASE, "eboot")
    for addr, desc, func, wtype in ew:
        print("  0x%X: %s (in func 0x%X) [%s]" % (addr, desc, func, wtype))
    
    # PRX writes
    print("\nPRX writes:")
    pw = search_writes(prx_data, prx_segs, TARGET, PRX_BASE, "PRX")
    if pw:
        for addr, desc, func, wtype in pw:
            print("  0x%X: %s (in func 0x%X) [%s]" % (addr, desc, func, wtype))
    else:
        print("  None")
    
    # Classification
    print("\nClassification:")
    init_writers = [(a, d, f, t) for a, d, f, t in ew if t == "init"]
    clear_writers = [(a, d, f, t) for a, d, f, t in ew if t == "clear"]
    print("  Init writers: %d" % len(init_writers))
    print("  Clear writers: %d" % len(clear_writers))
    print("  PRX writers: %d" % len(pw))
    print("  From EXP-160: clear at 0x800804175 EXECUTES")
    print("  From EXP-160: init at 0x8013EF019 NEVER EXECUTES (with argc=1)")
    print("  From EXP-170: init at 0x8013EF019 NEVER EXECUTES (with argc=2)")
    
    # ===== TEST 3: Branch ladder =====
    print("\n" + "=" * 80)
    print("TEST 3: Branch Ladder in Consumer 0x%X" % CONSUMER)
    print("=" * 80)
    
    func_vaddr = CONSUMER - EBOOT_BASE
    foff = None
    for seg in eboot_segs:
        if seg['type'] == 1 and seg['vaddr'] <= func_vaddr < seg['vaddr'] + seg['filesz']:
            foff = seg['offset'] + (func_vaddr - seg['vaddr'])
            break
    
    chunk = eboot_data[foff:foff + INIT_WRITE_OFFSET + 16]
    
    # Find ALL conditional branches between +0x72 and +0x3969
    # Also find CMP and TEST instructions before each branch
    branches = []
    i = 0x72
    while i < INIT_WRITE_OFFSET:
        b0 = chunk[i]
        b1 = chunk[i+1] if i+1 < len(chunk) else 0
        
        # jcc rel32
        if b0 == 0x0F and 0x80 <= b1 <= 0x8F and i + 5 < len(chunk):
            rel = struct.unpack_from('<i', chunk, i+2)[0]
            target_off = i + 6 + rel
            cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b1 - 0x80]
            skips = target_off > INIT_WRITE_OFFSET
            branches.append((i, cc, target_off, skips, "rel32"))
            i += 6
            continue
        
        # jcc rel8
        if 0x70 <= b0 <= 0x7F and i + 1 < len(chunk):
            rel = struct.unpack_from('<b', chunk, i+1)[0]
            target_off = i + 2 + rel
            cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b0 - 0x70]
            skips = target_off > INIT_WRITE_OFFSET
            branches.append((i, cc, target_off, skips, "rel8"))
            i += 2
            continue
        
        i += 1
    
    # Show skip branches with context
    skip_branches = [b for b in branches if b[3]]
    print("\nBranches that SKIP init write at +0x%X:" % INIT_WRITE_OFFSET)
    print("Total: %d\n" % len(skip_branches))
    
    for off, cc, target_off, skips, fmt in skip_branches[:15]:
        addr = CONSUMER + off
        target_addr = CONSUMER + target_off
        # Find what's before the branch (TEST/CMP)
        context = ""
        for back in range(1, 10):
            pos = off - back
            if pos < 0: break
            b0 = chunk[pos]
            b1 = chunk[pos+1] if pos+1 < len(chunk) else 0
            b2 = chunk[pos+2] if pos+2 < len(chunk) else 0
            
            if b0 == 0x48 and b1 == 0x85:  # test reg, reg
                modrm = b2
                if (modrm >> 6) & 3 == 3:
                    reg = (modrm >> 3) & 7
                    rm = modrm & 7
                    regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']
                    context = "test %s, %s" % (regs[reg], regs[rm])
                    break
            elif b0 == 0x48 and b1 == 0x83 and b2 == 0xF8:  # cmp rax, imm8
                imm = chunk[pos+3]
                context = "cmp rax, %d" % imm
                break
            elif b0 == 0x83 and b1 == 0x3D:  # cmp byte [rip+disp32], imm8
                context = "cmp byte [...], imm8"
                break
            elif b0 == 0x48 and b1 == 0x83 and b2 in (0xFB, 0xFF, 0xFE, 0xF9, 0xF7, 0xF6):
                regs_map = {0xFB:'rbx', 0xFF:'rdi', 0xFE:'rsi', 0xF9:'rcx', 0xF7:'rdx', 0xF6:'rsi'}
                imm = chunk[pos+3]
                context = "cmp %s, %d" % (regs_map.get(b2, '?'), imm)
                break
            elif b0 == 0x44 and b1 == 0x85:  # test r8d-r15d, ...
                context = "test r8d+"
                break
            elif b0 == 0x85:  # test reg, reg (32-bit)
                modrm = b1
                if (modrm >> 6) & 3 == 3:
                    reg = (modrm >> 3) & 7
                    rm = modrm & 7
                    regs = ['eax','ecx','edx','ebx','esp','ebp','esi','edi']
                    context = "test %s, %s" % (regs[reg], regs[rm])
                    break
        
        print("  +0x%04X (0x%X): %s 0x%X (+0x%04X) [%s] prev: %s" % (off, addr, cc, target_addr, target_off, fmt, context))

if __name__ == '__main__':
    main()
