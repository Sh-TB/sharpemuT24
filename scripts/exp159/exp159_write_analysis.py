#!/usr/bin/env python3
"""EXP-159: Analyze the write instructions to 0x801E51240."""

import struct

EBOOT_PATH = "/tmp/exp158_games/eboot.bin"
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

def runtime_to_file(segments, runtime, base):
    vaddr = runtime - base
    for seg in segments:
        if seg['type'] == 1 and seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
            return seg['offset'] + (vaddr - seg['vaddr'])
    return None

def main():
    data, segments = parse_elf64(EBOOT_PATH)
    
    # The 2 unique write addresses (the other 2 are the same without REX prefix)
    writes = [
        (0x8007FD8F9, 0x8007FD320, "48 C7 05 3C 39 65 01 00 00 00 00", "mov qword [0x801E51240], 0"),
        (0x8013EF019, 0x8013EB6B0, "48 89 05 20 22 A6 00", "mov [0x801E51240], rax"),
    ]
    
    for write_addr, func_addr, bytes_hex, desc in writes:
        print(f"\n{'='*80}")
        print(f"Write at 0x{write_addr:X} in function 0x{func_addr:X}")
        print(f"Instruction: {desc}")
        print(f"Bytes: {bytes_hex}")
        
        foff = runtime_to_file(segments, write_addr, EBOOT_BASE)
        func_foff = runtime_to_file(segments, func_addr, EBOOT_BASE)
        
        if foff and func_foff:
            # Show context around the write (32 bytes before, 32 after)
            context_start = max(0, foff - 32)
            context = data[context_start:foff + 32]
            print(f"\nContext (32 bytes before, 32 after):")
            for i in range(0, len(context), 16):
                addr = write_addr - 32 + i
                hex_str = ' '.join(f'{b:02X}' for b in context[i:i+16])
                marker = ' <-- WRITE HERE' if write_addr - 32 + i <= write_addr < write_addr - 32 + i + 16 else ''
                print(f"  0x{addr:X}: {hex_str}{marker}")
            
            # Show function prologue
            func_bytes = data[func_foff:func_foff + 64]
            print(f"\nFunction prologue (first 64 bytes): {func_bytes.hex()}")
            
            # Find CALLs in the function before the write
            write_offset = foff - func_foff
            chunk = data[func_foff:func_foff + write_offset + 16]
            print(f"\nCALL instructions before the write:")
            for i in range(min(write_offset, len(chunk) - 5)):
                if chunk[i] == 0xE8:
                    rel = struct.unpack_from('<i', chunk, i + 1)[0]
                    call_addr = func_addr + i
                    target = call_addr + 5 + rel
                    if 0x800000000 <= target < 0x810000000:
                        print(f"  0x{call_addr:X}: call 0x{target:X}")
    
    # Check the decoder's call chain: DT_INIT → 0x13FCE40 → 0x13EB6B0
    print(f"\n{'='*80}")
    print(f"Decoder call chain verification:")
    print(f"{'='*80}")
    
    # Check if 0x13FCE40 calls 0x13EB6B0
    func_addr = 0x8013FCE40
    foff = runtime_to_file(segments, func_addr, EBOOT_BASE)
    if foff:
        chunk = data[foff:foff + 2048]
        print(f"\nFunction 0x{func_addr:X} — searching for call to 0x8013EB6B0:")
        target = 0x8013EB6B0
        found = False
        for i in range(len(chunk) - 5):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = func_addr + i
                call_target = call_addr + 5 + rel
                if call_target == target:
                    print(f"  FOUND: call at 0x{call_addr:X} → 0x{call_target:X}")
                    found = True
        if not found:
            print(f"  NOT FOUND — 0x{func_addr:X} does NOT directly call 0x{target:X}")
            # Search for indirect calls or other references
            print(f"  Searching for LEA/MOV referencing 0x{target:X}...")
            target_bytes = struct.pack('<Q', target)
            for i in range(len(chunk) - 8):
                if chunk[i:i+8] == target_bytes:
                    print(f"  Found address constant at offset +0x{i:X}")
    
    # Check the DT_INIT value
    print(f"\n{'='*80}")
    print(f"DT_INIT verification:")
    print(f"{'='*80}")
    
    # DT_INIT is at vaddr 0x10 (from previous analysis)
    dt_init_vaddr = 0x10
    dt_init_runtime = EBOOT_BASE + dt_init_vaddr
    dt_init_foff = runtime_to_file(segments, dt_init_runtime, EBOOT_BASE)
    if dt_init_foff:
        # Read the first instruction at DT_INIT
        chunk = data[dt_init_foff:dt_init_foff + 32]
        print(f"DT_INIT at 0x{dt_init_runtime:X} (file 0x{dt_init_foff:X}):")
        print(f"  First 32 bytes: {chunk.hex()}")
        if chunk[0] == 0x55:
            print(f"  Starts with push rbp (function prologue)")
        elif chunk[0] == 0xE9:
            rel = struct.unpack_from('<i', chunk, 1)[0]
            target = dt_init_runtime + 5 + rel
            print(f"  JMP to 0x{target:X}")
        elif chunk[0] == 0xEB:
            rel = struct.unpack_from('<b', chunk, 1)[0]
            target = dt_init_runtime + 2 + rel
            print(f"  JMP short to 0x{target:X}")

if __name__ == '__main__':
    main()
