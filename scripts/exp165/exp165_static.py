#!/usr/bin/env python3
"""EXP-165 Tests 3+6: Static analysis of 0x801E518C8 producers + 0x801EF3050 dependency."""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
PRX_PATH = "/tmp/exp162_games/Il2cppUserAssemblies.prx"
EBOOT_BASE = 0x800000000
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

def runtime_to_file(segments, runtime, base):
    vaddr = runtime - base
    for seg in segments:
        if seg['type'] == 1 and seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
            return seg['offset'] + (vaddr - seg['vaddr'])
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
                    # Decode
                    foff = seg['offset'] + i
                    chunk = data[foff:foff + 16]
                    fb = find_func_start(data, foff)
                    func_str = " (in func 0x%X)" % (addr - fb) if fb is not None else ""
                    if oc == 0xC7:
                        imm = struct.unpack_from('<I', chunk, plen + 6)[0]
                        writes.append((addr, "mov qword [0x%X], 0x%X%s" % (comp, imm, func_str), "clear" if imm == 0 else "init"))
                    elif oc == 0x89:
                        reg = (mr >> 3) & 7
                        regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']
                        rex_r = (chunk[0] >> 2) & 1 if plen == 1 else 0
                        idx = reg + (rex_r * 8)
                        rn = regs[idx] if idx < 16 else 'r%d' % idx
                        writes.append((addr, "mov [0x%X], %s%s" % (comp, rn, func_str), "init"))
                    break
    return writes

def main():
    data, segments = parse_elf64(EBOOT_PATH)
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    
    print("=" * 80)
    print("TEST 6: Search ALL Producers of 0x801E518C8")
    print("=" * 80)
    
    target = 0x801E518C8
    
    # Eboot writes
    print("\nEboot writes to 0x%X:" % target)
    eboot_writes = search_writes(data, segments, target, EBOOT_BASE, "eboot")
    for addr, desc, wtype in eboot_writes:
        print("  0x%X: %s [%s]" % (addr, desc, wtype))
    
    # PRX writes
    print("\nPRX writes to 0x%X:" % target)
    prx_writes = search_writes(prx_data, prx_segs, target, PRX_BASE, "PRX")
    for addr, desc, wtype in prx_writes:
        print("  0x%X: %s [%s]" % (addr, desc, wtype))
    
    # Also search for 0x801E518C8 as 64-bit constant (indirect references)
    print("\n64-bit constant references:")
    target_bytes = struct.pack('<Q', target)
    for seg in segments:
        if seg['type'] != 1: continue
        sd = data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = sd.find(target_bytes, idx)
            if i == -1: break
            runtime = EBOOT_BASE + seg['vaddr'] + i
            stype = 'CODE' if seg['flags'] & 1 else 'DATA'
            print("  0x%X (%s)" % (runtime, stype))
            idx = i + 1
    
    # Classification
    print("\nClassification:")
    print("  Total producers: %d (eboot) + %d (PRX)" % (len(eboot_writes), len(prx_writes)))
    init_count = sum(1 for _, _, t in eboot_writes if t == "init")
    clear_count = sum(1 for _, _, t in eboot_writes if t == "clear")
    print("  Init writes: %d" % init_count)
    print("  Clear writes: %d" % clear_count)
    print("  From EXP-160/163: clear executes, ALL init writes NEVER execute")
    print("  Classification: B) Never executed (for init writes)")
    
    # ===== TEST 3: 0x801EF3050 dependency =====
    print("\n" + "=" * 80)
    print("TEST 3: Initializer 0x8007E8790 Dependency — [0x801EF3050]")
    print("=" * 80)
    
    dep_addr = 0x801EF3050
    print("\nAddress: 0x%X" % dep_addr)
    
    # Check mapping
    vaddr = dep_addr - EBOOT_BASE
    for seg in segments:
        if seg['type'] == 1:
            end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= vaddr < end:
                fb = seg['vaddr'] + seg['filesz']
                if vaddr < fb:
                    foff = seg['offset'] + (vaddr - seg['vaddr'])
                    val = struct.unpack_from('<Q', data, foff)[0]
                    print("  Location: FILE-BACKED, value=0x%X" % val)
                else:
                    print("  Location: BSS, value=0x0 at runtime")
                break
    else:
        print("  NOT MAPPED")
    
    # Search writes to 0x801EF3050
    print("\nWrites to 0x%X:" % dep_addr)
    dep_writes = search_writes(data, segments, dep_addr, EBOOT_BASE, "eboot")
    for addr, desc, wtype in dep_writes:
        print("  0x%X: %s [%s]" % (addr, desc, wtype))
    
    dep_prx_writes = search_writes(prx_data, prx_segs, dep_addr, PRX_BASE, "PRX")
    if dep_prx_writes:
        print("PRX writes:")
        for addr, desc, wtype in dep_prx_writes:
            print("  0x%X: %s [%s]" % (addr, desc, wtype))
    else:
        print("PRX writes: 0")
    
    # Search RELA for 0x801EF3050
    print("\nRELA search for 0x%X:" % dep_addr)
    e_shoff = struct.unpack_from('<Q', data, 0x28)[0]
    e_shentsize = struct.unpack_from('<H', data, 0x3A)[0]
    e_shnum = struct.unpack_from('<H', data, 0x3C)[0]
    e_shstrndx = struct.unpack_from('<H', data, 0x3E)[0]
    
    if e_shoff > 0 and e_shnum > 0:
        shstr_hdr_off = e_shoff + e_shstrndx * e_shentsize
        if shstr_hdr_off + e_shentsize <= len(data):
            shstr_offset = struct.unpack_from('<Q', data, shstr_hdr_off + 0x18)[0]
            for sec_idx in range(e_shnum):
                sh_off = e_shoff + sec_idx * e_shentsize
                if sh_off + e_shentsize > len(data): break
                sh_type = struct.unpack_from('<I', data, sh_off + 4)[0]
                sh_offset = struct.unpack_from('<Q', data, sh_off + 0x18)[0]
                sh_size = struct.unpack_from('<Q', data, sh_off + 0x20)[0]
                if sh_type != 4: continue  # SHT_RELA
                entry_count = sh_size // 24
                dep_vaddr = dep_addr - EBOOT_BASE
                for j in range(entry_count):
                    entry_off = sh_offset + j * 24
                    if entry_off + 24 > len(data): break
                    r_offset = struct.unpack_from('<Q', data, entry_off)[0]
                    if abs(r_offset - dep_vaddr) < 8:
                        r_info = struct.unpack_from('<Q', data, entry_off + 8)[0]
                        r_addend = struct.unpack_from('<q', data, entry_off + 16)[0]
                        r_type = r_info & 0xFFFFFFFF
                        print("  RELA: r_offset=0x%X addend=0x%X type=%d" % (r_offset, r_addend, r_type))
    
    # Also check function 0x8007E8790 first instruction more carefully
    print("\nFunction 0x8007E8790 first instructions:")
    foff = runtime_to_file(segments, 0x8007E8790, EBOOT_BASE)
    if foff:
        chunk = data[foff:foff + 64]
        for i in range(0, 64, 16):
            addr = 0x8007E8790 + i
            print("  0x%X: %s" % (addr, ' '.join('%02X' % b for b in chunk[i:i+16])))
        
        # The first instruction after prologue is: 48 8B 15 B3 A8 70 01
        # = mov rdx, [rip+0x0170A8B3]
        # Target = 0x8007E8790 + 6 + 7 + 0x0170A8B3 = 0x8007E879D + 0x0170A8B3
        # Wait, the prologue is: 55 48 89 E5 53 50 (6 bytes)
        # So instruction at +6: 48 8B 15 B3 A8 70 01
        # mov rdx, [rip+0x0170A8B3]
        # target = 0x8007E8790 + 6 + 7 + 0x0170A8B3 = 0x8007E8797 + 0x0170A8B3
        target_calc = 0x8007E8790 + 6 + 7 + 0x0170A8B3
        print("\n  First load: mov rdx, [0x%X]" % target_calc)
        if target_calc == dep_addr:
            print("  *** MATCHES 0x801EF3050 ***")
        else:
            print("  Does NOT match 0x801EF3050 (calculated: 0x%X)" % target_calc)
            # Let me recalculate
            # 48 8B 15 is at offset 6 in the function
            # disp32 = B3 A8 70 01 (little-endian) = 0x0170A8B3
            # instruction length = 7 (48 8B 15 + 4 bytes disp)
            # RIP at time of execution = 0x8007E8790 + 6 + 7 = 0x8007E879D
            # target = 0x8007E879D + 0x0170A8B3 = ?
            target2 = 0x8007E879D + 0x0170A8B3
            print("  Recalculated: 0x8007E879D + 0x0170A8B3 = 0x%X" % target2)

if __name__ == '__main__':
    main()
