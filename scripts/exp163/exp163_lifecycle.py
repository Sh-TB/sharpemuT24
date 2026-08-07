#!/usr/bin/env python3
"""EXP-163 Tasks 1+2: Lifecycle of 0x801E518C8 + reverse analysis of 0x8013EB6B0."""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
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
    
    target = 0x801E518C8
    func_addr = 0x8013EB6B0
    
    print("=" * 80)
    print("TASK 1: Lifecycle of 0x%08X" % target)
    print("=" * 80)
    
    # Check mapping
    tvaddr = target - EBOOT_BASE
    for seg in segments:
        if seg['type'] == 1:
            end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= tvaddr < end:
                fb = seg['vaddr'] + seg['filesz']
                if tvaddr < fb:
                    foff = seg['offset'] + (tvaddr - seg['vaddr'])
                    val = struct.unpack_from('<Q', data, foff)[0]
                    print("  Location: FILE-BACKED, value=0x%X" % val)
                else:
                    print("  Location: BSS, value=0x0 at runtime")
                break
    
    # Find all RIP-relative refs
    writes = []
    reads = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1): continue
        sd = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(sd) - 11):
            for plen in range(2):
                if plen == 1 and sd[i] not in (0xF0, 0x48, 0x4C, 0x66): continue
                oc = sd[i + plen] if i + plen < len(sd) else 0
                if oc not in (0x8B, 0x89, 0x88, 0xC6, 0xC7, 0x80, 0x81, 0x83): continue
                mr = sd[i + plen + 1] if i + plen + 1 < len(sd) else 0
                if (mr >> 6) & 3 != 0 or (mr & 7) != 5: continue
                doff = plen + 2
                if i + doff + 4 > len(sd): continue
                disp = struct.unpack_from('<i', sd, i + doff)[0]
                reg = (mr >> 3) & 7
                blen = doff + 4
                ilen = 0
                if oc in (0xC6, 0x80, 0x83): ilen = 1
                elif oc in (0xC7, 0x81): ilen = 4
                total = blen + ilen
                addr = EBOOT_BASE + seg['vaddr'] + i
                comp = addr + total + disp
                if comp == target:
                    is_cmp = (oc in (0x80, 0x81, 0x83) and reg == 7)
                    if is_cmp:
                        reads.append(addr)
                    elif oc in (0xC6, 0xC7, 0x89, 0x88):
                        writes.append(addr)
                    elif oc == 0x8B:
                        reads.append(addr)
                    break
    
    print("  Writes: %d" % len(writes))
    print("  Reads: %d" % len(reads))
    
    # Decode writes
    print("\n  WRITES (decoded):")
    for w in writes:
        foff = runtime_to_file(segments, w, EBOOT_BASE)
        if not foff: continue
        chunk = data[foff:foff + 16]
        fb = find_func_start(data, foff)
        fs = " (in func 0x%X)" % (w - fb) if fb is not None else ""
        if chunk[0] == 0x48 and chunk[1] == 0xC7:
            disp = struct.unpack_from('<i', chunk, 3)[0]
            imm = struct.unpack_from('<I', chunk, 7)[0]
            print("    0x%X: mov qword [0x%X], 0x%X%s" % (w, w+11+disp, imm, fs))
        elif chunk[0] in (0x48, 0x4C) and chunk[1] == 0x89:
            modrm = chunk[2]
            disp = struct.unpack_from('<i', chunk, 3)[0]
            reg = (modrm >> 3) & 7
            regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']
            rex_r = (chunk[0] >> 2) & 1
            idx = reg + (rex_r * 8)
            rn = regs[idx] if idx < 16 else 'r%d' % idx
            print("    0x%X: mov [0x%X], %s%s" % (w, w+7+disp, rn, fs))
    
    # Show first reads
    print("\n  FIRST 5 READS:")
    for r in reads[:5]:
        foff = runtime_to_file(segments, r, EBOOT_BASE)
        if foff:
            fb = find_func_start(data, foff)
            if fb is not None:
                print("    0x%X: read (in func 0x%X)" % (r, r - fb))
    
    print("\n" + "=" * 80)
    print("TASK 2: Reverse Analysis of 0x%X" % func_addr)
    print("=" * 80)
    
    # Decode globals in first 128 bytes
    foff = runtime_to_file(segments, func_addr, EBOOT_BASE)
    chunk = data[foff:foff + 128]
    
    print("\n  First 128 bytes disassembly:")
    for i in range(0, 128, 16):
        addr = func_addr + i
        hex_str = ' '.join('%02X' % b for b in chunk[i:i+16])
        print("    0x%X: %s" % (addr, hex_str))
    
    # Find global accesses and branches
    print("\n  Global accesses and branches in first 128 bytes:")
    for i in range(len(chunk) - 7):
        b0 = chunk[i]
        b1 = chunk[i+1] if i+1 < len(chunk) else 0
        addr = func_addr + i
        off = i
        
        # MOV reg, [rip+disp32]
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
                # Check if target is BSS
                tvaddr = target - EBOOT_BASE
                loc = "UNKNOWN"
                for seg in segments:
                    if seg['type'] == 1:
                        end = seg['vaddr'] + seg['memsz']
                        if seg['vaddr'] <= tvaddr < end:
                            fb2 = seg['vaddr'] + seg['filesz']
                            loc = "BSS(0)" if tvaddr >= fb2 else "FILE"
                            break
                print("    +0x%02X: mov %s, [0x%X] (%s)" % (off, rn, target, loc))
        
        # CMP byte [rip+disp32], imm8
        if b0 == 0x83 and b1 == 0x3D:
            disp = struct.unpack_from('<i', chunk, i+2)[0]
            target = addr + 7 + disp
            imm = chunk[i+6]
            tvaddr = target - EBOOT_BASE
            loc = "UNKNOWN"
            for seg in segments:
                if seg['type'] == 1:
                    end = seg['vaddr'] + seg['memsz']
                    if seg['vaddr'] <= tvaddr < end:
                        fb2 = seg['vaddr'] + seg['filesz']
                        loc = "BSS(0)" if tvaddr >= fb2 else "FILE"
                        break
            print("    +0x%02X: cmp byte [0x%X], %d (%s)" % (off, target, imm, loc))
        
        # Conditional jumps
        if b0 == 0x0F and 0x80 <= b1 <= 0x8F and i + 5 < len(chunk):
            rel = struct.unpack_from('<i', chunk, i+2)[0]
            target = addr + 6 + rel
            cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b1 - 0x80]
            print("    +0x%02X: %s 0x%X (offset +0x%X)" % (off, cc, target, target - func_addr))
        elif 0x70 <= b0 <= 0x7F and i + 1 < len(chunk):
            rel = struct.unpack_from('<b', chunk, i+1)[0]
            target = addr + 2 + rel
            cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b0 - 0x70]
            print("    +0x%02X: %s 0x%X (offset +0x%X)" % (off, cc, target, target - func_addr))
        
        # CALL
        if b0 == 0xE8 and i + 4 < len(chunk):
            rel = struct.unpack_from('<i', chunk, i+1)[0]
            target = addr + 5 + rel
            print("    +0x%02X: call 0x%X" % (off, target))

if __name__ == '__main__':
    main()
