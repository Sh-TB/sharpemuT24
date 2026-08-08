#!/usr/bin/env python3
"""EXP-153 Step 1b: Verify the first guard check address in writer function 1."""

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

def main():
    data, segments = parse_elf64(PRX_PATH)
    
    # Writer function 1 at 0x804FB1B90
    func_addr = 0x804FB1B90
    foff = runtime_to_file(segments, func_addr, PRX_BASE)
    chunk = data[foff:foff + 32]
    
    print("Writer function 1 (0x804FB1B90) first 32 bytes:")
    print(f"  {chunk.hex()}")
    
    # Decode manually:
    # 55               push rbp
    # 48 89 E5         mov rbp, rsp
    # 83 3D 1D 60 DB 03 00   cmp byte [rip+0x3DB601D], 0
    # 74 02            je +2
    # 5D               pop rbp
    # C3               ret
    
    # The cmp is at offset 3 (after 55 48 89 E5)
    cmp_addr = func_addr + 3
    disp = struct.unpack_from('<i', chunk, 5)[0]  # disp at offset 5 (3 + 2 for opcode)
    target = cmp_addr + 7 + disp
    print(f"\nFirst guard check:")
    print(f"  Instruction at 0x{cmp_addr:X}")
    print(f"  cmp byte [rip+0x{disp:X}], 0")
    print(f"  Target address: 0x{cmp_addr:X} + 7 + 0x{disp:X} = 0x{target:X}")
    
    # This is 0x808D67BB8, NOT 0x808D67B98!
    # 0x808D67BB8 is 0x20 bytes after 0x808D67B98
    print(f"\n  *** THIS IS A DIFFERENT FLAG! ***")
    print(f"  0x{target:X} vs target flag 0x808D67B98")
    print(f"  Difference: 0x{target - 0x808D67B98:X} ({target - 0x808D67B98} bytes)")
    
    # The first guard checks 0x808D67BB8, not 0x808D67B98!
    # This means the function returns early if flag at 0x808D67BB8 is 0
    # NOT if the target flag (0x808D67B98) is 0!
    
    # Let's check what 0x808D67BB8 is
    flag2_addr = target  # 0x808D67BB8
    flag2_vaddr = flag2_addr - PRX_BASE
    print(f"\n  Flag 2 address: 0x{flag2_addr:X} (vaddr 0x{flag2_vaddr:X})")
    
    for seg in segments:
        if seg['type'] == 1:
            end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= flag2_vaddr < end:
                file_backed = seg['vaddr'] + seg['filesz']
                if flag2_vaddr < file_backed:
                    byte_foff = seg['offset'] + (flag2_vaddr - seg['vaddr'])
                    byte_val = data[byte_foff]
                    print(f"  In file-backed data: value = 0x{byte_val:X}")
                else:
                    print(f"  In BSS (value = 0 at runtime)")
                break
    
    # Now let's check the SECOND guard (the one that checks 0x808D67B98)
    # It's at 0x804FB1C05
    cmp2_addr = 0x804FB1C05
    cmp2_foff = runtime_to_file(segments, cmp2_addr, PRX_BASE)
    cmp2_chunk = data[cmp2_foff:cmp2_foff + 10]
    print(f"\nSecond guard check at 0x{cmp2_addr:X}:")
    print(f"  Bytes: {cmp2_chunk[:7].hex()}")
    disp2 = struct.unpack_from('<i', cmp2_chunk, 2)[0]
    target2 = cmp2_addr + 7 + disp2
    print(f"  cmp byte [rip+0x{disp2:X}], 0")
    print(f"  Target: 0x{cmp2_addr:X} + 7 + 0x{disp2:X} = 0x{target2:X}")
    
    # Third guard at 0x804FB1C0E
    cmp3_addr = 0x804FB1C0E
    cmp3_foff = runtime_to_file(segments, cmp3_addr, PRX_BASE)
    cmp3_chunk = data[cmp3_foff:cmp3_foff + 10]
    print(f"\nThird guard check at 0x{cmp3_addr:X}:")
    print(f"  Bytes: {cmp3_chunk[:7].hex()}")
    disp3 = struct.unpack_from('<i', cmp3_chunk, 2)[0]
    target3 = cmp3_addr + 7 + disp3
    imm3 = cmp3_chunk[6]
    print(f"  cmp byte [rip+0x{disp3:X}], {imm3}")
    print(f"  Target: 0x{cmp3_addr:X} + 7 + 0x{disp3:X} = 0x{target3:X}")
    
    # So the full logic is:
    # 1. if byte[0x808D67BB8] == 0: return early (FIRST guard)
    # 2. ... lots of initialization code ...
    # 3. if byte[0x808D67B98] == 0: skip flag write (SECOND guard)
    # 4. if byte[0x808B55690] == 2: skip flag write (THIRD guard)
    # 5. mov dword [0x808D67B98], 1  (WRITE)
    
    print(f"\n{'='*80}")
    print(f"FULL LOGIC OF WRITER FUNCTION 1 (0x804FB1B90):")
    print(f"{'='*80}")
    print(f"""
  1. if byte[0x{target:X}] == 0: return early  ← FIRST GUARD (different flag!)
  2. ... initialization code ...
  3. if byte[0x{target2:X}] == 0: skip write    ← SECOND GUARD (target flag)
  4. if byte[0x{target3:X}] == 2: skip write    ← THIRD GUARD (another flag)
  5. mov dword [0x{target2:X}], 1               ← WRITE FLAG

KEY INSIGHT:
  The FIRST guard checks 0x{target:X}, NOT 0x808D67B98!
  If 0x{target:X} is non-zero, the function continues.
  If 0x{target:X} is zero, the function returns early.
  
  0x{target:X} is 0x{target - 0x808D67B98} bytes after the target flag.
  This is a DIFFERENT flag — likely a "module initialized" or "runtime ready" flag.
  
  The target flag (0x808D67B98) is only checked at the SECOND guard.
  The SECOND guard skips the WRITE, not the entire function.
  
  So the question is: does 0x{target:X} get set to non-zero?
  If yes, the function continues and eventually writes 0x808D67B98.
  If no, the function returns early and never writes anything.
""")

if __name__ == '__main__':
    main()
