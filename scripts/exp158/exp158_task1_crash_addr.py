#!/usr/bin/env python3
"""
EXP-158 Task 1: Verify crash address 0x80135DE83 using ELF Program Header translation.
Do NOT just calculate RIP - Base. Use PT_LOAD segment mapping.
"""

import struct

EBOOT_PATH = "/tmp/exp158_games/eboot.bin"
PRX_PATH = "/tmp/exp158_games/Il2cppUserAssemblies.prx"

CRASH_RIP = 0x80135DE83
PS5_BASE = 0x800000000

def parse_elf64_segments(path):
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
        segments.append({
            'type': p_type, 'flags': p_flags, 'offset': p_offset,
            'vaddr': p_vaddr, 'filesz': p_filesz, 'memsz': p_memsz,
            'data': data
        })
    return data, segments

def find_segment_for_runtime_addr(segments, runtime_addr, load_base):
    """Find which PT_LOAD segment contains the runtime address."""
    vaddr = runtime_addr - load_base
    for seg in segments:
        if seg['type'] != 1:  # PT_LOAD
            continue
        seg_vaddr_end = seg['vaddr'] + seg['memsz']
        if seg['vaddr'] <= vaddr < seg_vaddr_end:
            return seg, vaddr
    return None, vaddr

def runtime_to_file_offset(seg, runtime_addr, load_base):
    """Convert runtime address to file offset using segment mapping."""
    vaddr = runtime_addr - load_base
    offset_in_seg = vaddr - seg['vaddr']
    file_offset = seg['offset'] + offset_in_seg
    return file_offset, offset_in_seg

def main():
    print("=" * 80)
    print("EXP-158 Task 1: Verify Crash Address 0x80135DE83")
    print("=" * 80)
    
    # Parse eboot segments
    eboot_data, eboot_segs = parse_elf64_segments(EBOOT_PATH)
    
    print(f"\nCrash RIP: 0x{CRASH_RIP:X}")
    print(f"PS5 Base: 0x{PS5_BASE:X}")
    print(f"Simple offset (RIP - Base): 0x{CRASH_RIP - PS5_BASE:X}")
    
    # Show eboot segments
    print(f"\nEboot PT_LOAD segments:")
    for i, seg in enumerate(eboot_segs):
        if seg['type'] == 1:
            flags = ''
            if seg['flags'] & 1: flags += 'X'
            if seg['flags'] & 2: flags += 'W'
            if seg['flags'] & 4: flags += 'R'
            runtime_start = PS5_BASE + seg['vaddr']
            runtime_end_file = PS5_BASE + seg['vaddr'] + seg['filesz']
            runtime_end_mem = PS5_BASE + seg['vaddr'] + seg['memsz']
            print(f"  [{i}] vaddr=0x{seg['vaddr']:X} filesz=0x{seg['filesz']:X} memsz=0x{seg['memsz']:X} flags={flags}")
            print(f"      runtime: 0x{runtime_start:X} - 0x{runtime_end_mem:X} (file-backed to 0x{runtime_end_file:X})")
            print(f"      file offset: 0x{seg['offset']:X}")
    
    # Find which segment contains the crash address
    seg, vaddr = find_segment_for_runtime_addr(eboot_segs, CRASH_RIP, PS5_BASE)
    
    if seg:
        file_offset, offset_in_seg = runtime_to_file_offset(seg, CRASH_RIP, PS5_BASE)
        flags = ''
        if seg['flags'] & 1: flags += 'X'
        if seg['flags'] & 2: flags += 'W'
        if seg['flags'] & 4: flags += 'R'
        
        print(f"\n*** CRASH ADDRESS FOUND IN EBOOT ***")
        print(f"  Segment: vaddr=0x{seg['vaddr']:X} flags={flags}")
        print(f"  Vaddr in segment: 0x{vaddr:X}")
        print(f"  Offset in segment: 0x{offset_in_seg:X}")
        print(f"  File offset: 0x{file_offset:X}")
        
        # Check if file-backed or BSS
        if offset_in_seg < seg['filesz']:
            print(f"  Location: FILE-BACKED (in file data)")
            # Read bytes at this offset
            if file_offset + 32 <= len(eboot_data):
                bytes_at = eboot_data[file_offset:file_offset + 32]
                print(f"  Bytes at crash address: {bytes_at.hex()}")
                
                # Check if it's code (X flag)
                if seg['flags'] & 1:
                    print(f"  This is a CODE segment (executable)")
                    
                    # Find function start by searching backward
                    func_start_offset = None
                    for back in range(0, 4096):
                        if file_offset - back < 0:
                            break
                        if file_offset - back + 4 <= len(eboot_data):
                            b = eboot_data[file_offset - back:file_offset - back + 4]
                            if b == b'\x55\x48\x89\xe5':  # push rbp; mov rbp, rsp
                                if file_offset - back - 1 >= 0:
                                    prev = eboot_data[file_offset - back - 1]
                                    if prev in (0xCC, 0xC3, 0xC9):
                                        func_start_offset = file_offset - back
                                        break
                    
                    if func_start_offset:
                        func_start_vaddr = seg['vaddr'] + (func_start_offset - seg['offset'])
                        func_start_runtime = PS5_BASE + func_start_vaddr
                        print(f"  Function start: 0x{func_start_runtime:X} (file: 0x{func_start_offset:X})")
                        print(f"  Crash is at offset +0x{file_offset - func_start_offset:X} from function start")
                        
                        # Show function prologue
                        func_bytes = eboot_data[func_start_offset:func_start_offset + 64]
                        print(f"  Function bytes: {func_bytes.hex()}")
                    else:
                        print(f"  Could not find function start (no prologue within 4096 bytes)")
                else:
                    print(f"  This is a DATA segment (not executable)")
            else:
                print(f"  File offset beyond file size!")
        else:
            print(f"  Location: BSS (beyond file-backed region)")
            print(f"  This address is in UNMAPPED/BSS memory — no code here!")
    else:
        print(f"\n*** CRASH ADDRESS NOT IN ANY EBOOT SEGMENT ***")
        print(f"  Vaddr 0x{vaddr:X} is not mapped in any PT_LOAD segment")
    
    # Also check PRX
    print(f"\n{'='*80}")
    print(f"Checking PRX (Il2cppUserAssemblies.prx)...")
    prx_data, prx_segs = parse_elf64_segments(PRX_PATH)
    PRX_BASE = 0x804CD5000
    
    # The crash RIP is 0x80135DE83 which is in eboot range (0x800000000+), not PRX range
    # But let's verify
    if CRASH_RIP >= PRX_BASE:
        seg, vaddr = find_segment_for_runtime_addr(prx_segs, CRASH_RIP, PRX_BASE)
        if seg:
            print(f"  Found in PRX!")
        else:
            print(f"  Not in PRX (vaddr 0x{vaddr:X} not mapped)")
    else:
        print(f"  Crash RIP 0x{CRASH_RIP:X} is in eboot range (0x{PS5_BASE:X}+), not PRX range (0x{PRX_BASE:X}+)")
    
    # Also check: is 0x80135DE83 in the runtime log?
    print(f"\n{'='*80}")
    print(f"Checking if 0x80135DE83 appears in any runtime log...")
    import os
    for log_path in ['/tmp/exp156_yatzi_run.log', '/tmp/exp157_rip_trace.log', '/tmp/exp157_step_trace.log']:
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                content = f.read()
            if '80135DE83' in content or '0x80135DE83' in content:
                print(f"  FOUND in {log_path}")
            else:
                print(f"  Not found in {log_path}")
        else:
            print(f"  Log not found: {log_path}")

if __name__ == '__main__':
    main()
