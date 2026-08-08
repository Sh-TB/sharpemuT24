#!/usr/bin/env python3
import struct
EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
EBOOT_BASE = 0x800000000
FUNC_START = 0x8013EB6B0
INIT_WRITE = 0x8013EF019

data = open(EBOOT_PATH, 'rb').read()
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
    if p_type == 1:
        segments.append({'flags': p_flags, 'offset': p_offset, 'vaddr': p_vaddr, 'filesz': p_filesz})

func_vaddr = FUNC_START - EBOOT_BASE
foff = None
for seg in segments:
    if seg['vaddr'] <= func_vaddr < seg['vaddr'] + seg['filesz']:
        foff = seg['offset'] + (func_vaddr - seg['vaddr'])
        break

init_offset = INIT_WRITE - FUNC_START
chunk = data[foff:foff + init_offset + 16]

print("Branches in consumer 0x%X between +0x72 and +0x%X that SKIP init:" % (FUNC_START, init_offset))
print("")

skip_branches = []
i = 0x72
while i < init_offset:
    b0 = chunk[i]
    b1 = chunk[i+1] if i+1 < len(chunk) else 0
    
    if b0 == 0x0F and 0x80 <= b1 <= 0x8F and i + 5 < len(chunk):
        rel = struct.unpack_from('<i', chunk, i+2)[0]
        target_off = i + 6 + rel
        cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b1 - 0x80]
        if target_off > init_offset:
            skip_branches.append((i, cc, target_off))
        i += 6
        continue
    
    if 0x70 <= b0 <= 0x7F and i + 1 < len(chunk):
        rel = struct.unpack_from('<b', chunk, i+1)[0]
        target_off = i + 2 + rel
        cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b0 - 0x70]
        if target_off > init_offset:
            skip_branches.append((i, cc, target_off))
        i += 2
        continue
    
    # Check for CMP byte [rip+disp32], imm8
    if b0 == 0x83 and b1 == 0x3D:
        disp = struct.unpack_from('<i', chunk, i+2)[0]
        target_addr = FUNC_START + i + 7 + disp
        imm = chunk[i+6]
        tvaddr = target_addr - EBOOT_BASE
        loc = "?"
        for seg in segments:
            if seg['vaddr'] <= tvaddr < seg['vaddr'] + seg['filesz']:
                loc = "FILE"
                break
            if seg['vaddr'] <= tvaddr < seg['vaddr'] + seg.get('filesz', 0) + 0x100000:
                loc = "BSS?"
                break
        print("  +0x%04X: cmp byte [0x%X], %d (%s)" % (i, target_addr, imm, loc))
        i += 7
        continue
    
    # CALL
    if b0 == 0xE8 and i + 4 < len(chunk):
        rel = struct.unpack_from('<i', chunk, i+1)[0]
        target = FUNC_START + i + 5 + rel
        if target in (0x804F6E510, 0x804F6E9E6):
            print("  +0x%04X: call 0x%X *** DISPATCH LOOP ***" % (i, target))
        i += 5
        continue
    
    i += 1

print("")
print("=== Branches that SKIP init write at +0x%X ===" % init_offset)
for off, cc, target_off in skip_branches:
    print("  +0x%04X: %s +0x%04X" % (off, cc, target_off))
print("")
print("Total skip branches: %d" % len(skip_branches))
