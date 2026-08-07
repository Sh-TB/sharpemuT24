#!/usr/bin/env python3
"""EXP-168 TEST 2+3: Find direct caller of 0x8013FCE40 and trace RBX lifecycle."""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
EBOOT_BASE = 0x800000000
TARGET_FUNC = 0x8013FCE40

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

def main():
    data, segments = parse_elf64(EBOOT_PATH)
    
    print("=" * 80)
    print("TEST 2: Find Direct Caller of 0x%X" % TARGET_FUNC)
    print("=" * 80)
    
    callers = find_callers(data, segments, TARGET_FUNC, EBOOT_BASE)
    print("\nDirect CALL references: %d" % len(callers))
    
    for c in callers:
        foff = runtime_to_file(segments, c, EBOOT_BASE)
        if not foff: continue
        fb = find_func_start(data, foff)
        func_addr = c - fb if fb is not None else 0
        
        print("\n  CALL at 0x%X (in function 0x%X)" % (c, func_addr))
        
        # Show 32 bytes before the CALL to see what sets RBX
        start = max(0, foff - 32)
        chunk = data[start:foff + 5]
        print("  32 bytes before CALL:")
        for i in range(0, len(chunk), 16):
            addr = c - 32 + i
            hex_str = ' '.join('%02X' % b for b in chunk[i:i+16])
            print("    0x%X: %s" % (addr, hex_str))
        
        # Decode instructions before CALL to find RBX writes
        print("\n  RBX-related instructions before CALL:")
        # Search backward from CALL for RBX writes
        for back in range(1, 64):
            pos = foff - back
            if pos < 0: break
            b0 = data[pos]
            b1 = data[pos + 1] if pos + 1 < len(data) else 0
            b2 = data[pos + 2] if pos + 2 < len(data) else 0
            addr = c - back
            
            # 48 89 C3 = mov rbx, rax
            # 48 89 D3 = mov rbx, rdx
            # 48 89 F3 = mov rbx, rsi
            # 48 89 FB = mov rbx, rdi
            # 89 C3 = mov ebx, eax
            # 31 DB = xor ebx, ebx
            # BB xx = mov ebx, imm32
            # 48 BB xx = mov rbx, imm64
            # 48 8D 1D = lea rbx, [rip+disp32]
            
            if b0 == 0x48 and b1 == 0x89 and b2 in (0xC3, 0xD3, 0xF3, 0xFB, 0xCB, 0xDB, 0xE3, 0xEB):
                regs = {0xC3:'rax',0xD3:'rdx',0xF3:'rsi',0xFB:'rdi',0xCB:'rcx',0xDB:'rbx',0xE3:'rsp',0xEB:'rbp'}
                src = regs.get(b2, '?')
                print("    0x%X: mov rbx, %s (offset -0x%X)" % (addr, src, back))
                break
            elif b0 == 0x89 and b1 == 0xC3:
                print("    0x%X: mov ebx, eax (offset -0x%X)" % (addr, back))
                break
            elif b0 == 0x89 and b1 == 0xD3:
                print("    0x%X: mov ebx, edx (offset -0x%X)" % (addr, back))
                break
            elif b0 == 0x31 and b1 == 0xDB:
                print("    0x%X: xor ebx, ebx (offset -0x%X)" % (addr, back))
                break
            elif b0 == 0xBB:
                imm = struct.unpack_from('<I', data, pos + 1)[0]
                print("    0x%X: mov ebx, 0x%X (offset -0x%X)" % (addr, imm, back))
                break
            elif b0 == 0x48 and b1 == 0xBB:
                imm = struct.unpack_from('<Q', data, pos + 2)[0]
                print("    0x%X: mov rbx, 0x%X (offset -0x%X)" % (addr, imm, back))
                break
            elif b0 == 0x48 and b1 == 0x8D and b2 == 0x1D:
                disp = struct.unpack_from('<i', data, pos + 3)[0]
                target = addr + 7 + disp
                print("    0x%X: lea rbx, [0x%X] (offset -0x%X)" % (addr, target, back))
                break
            elif b0 == 0x48 and b1 == 0x8B and b2 == 0x1D:
                disp = struct.unpack_from('<i', data, pos + 3)[0]
                target = addr + 7 + disp
                print("    0x%X: mov rbx, [0x%X] (offset -0x%X)" % (addr, target, back))
                break
            elif b0 == 0x41 and b1 == 0x89 and b2 == 0xDD:
                print("    0x%X: mov r13d, ebx (offset -0x%X)" % (addr, back))
                # Don't break — keep looking for RBX source
        else:
            print("    No direct RBX write found within 64 bytes before CALL")
            print("    RBX may be set by a function call or inherited from caller")

if __name__ == '__main__':
    main()
