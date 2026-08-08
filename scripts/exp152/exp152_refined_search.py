#!/usr/bin/env python3
"""
EXP-152 Step 2b: Refined writer search — distinguish reads from writes.
The previous search found 56 "writes" but they're actually CMP instructions (reads).
This script properly identifies actual WRITE instructions.
"""

import struct
import json

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000
TARGET_BYTE_ADDR = 0x808D67B98

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

def main():
    print("=" * 80)
    print("EXP-152 Step 2b: Refined Writer Search (Reads vs Writes)")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    # The 56 "writes" found were opcode 0x83 with ModRM reg field = 7 (CMP)
    # 0x83 /7 = cmp [mem], imm8  (READ, not write)
    # 0x83 /0 = add [mem], imm8  (READ+WRITE)
    # 0x83 /1 = or  [mem], imm8  (READ+WRITE)
    # 0x83 /4 = and [mem], imm8  (READ+WRITE)
    # 0x83 /6 = xor [mem], imm8  (READ+WRITE)
    # 0x83 /5 = sub [mem], imm8  (READ+WRITE)
    
    # TRUE write opcodes (where the memory operand is the DESTINATION):
    # C6 /0 = mov byte [mem], imm8     (WRITE ONLY)
    # C7 /0 = mov dword [mem], imm32   (WRITE ONLY)
    # 88 /r = mov byte [mem], reg8     (WRITE ONLY)
    # 89 /r = mov [mem], reg           (WRITE ONLY)
    # 80 /1 = or  byte [mem], imm8     (READ+WRITE)
    # 80 /4 = and byte [mem], imm8     (READ+WRITE)
    # 80 /6 = xor byte [mem], imm8     (READ+WRITE)
    # 81 /1 = or  [mem], imm32         (READ+WRITE)
    # 09 /r = or  [mem], reg           (READ+WRITE)
    # 01 /r = add [mem], reg           (READ+WRITE)
    # FE /0 = inc byte [mem]           (READ+WRITE)
    # FE /1 = dec byte [mem]           (READ+WRITE)
    # F0 ... = lock prefix (atomic)
    
    # READ-ONLY opcodes (where memory is the SOURCE):
    # 80 /7 = cmp byte [mem], imm8     (READ ONLY)
    # 80 /0 = test byte [mem], imm8    (READ ONLY) — actually 0xF6 /0 is test
    # 83 /7 = cmp [mem], imm8          (READ ONLY)
    # 83 /0..6 = add/or/adc/sbb/and/sub/xor [mem], imm8 (READ+WRITE)
    # 3B /r = cmp reg, [mem]           (READ ONLY)
    # 8B /r = mov reg, [mem]           (READ ONLY)
    # 0F B6 = movzx reg, byte [mem]    (READ ONLY)
    # 0F BE = movsx reg, byte [mem]    (READ ONLY)
    
    # For the flag byte, we need to find instructions that WRITE to it.
    # The CMP instruction (83 3D) is a READ — it only compares, doesn't write.
    
    readers = []
    writers = []
    
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        
        for i in range(len(seg_data) - 11):
            # Check for RIP-relative addressing (mod=0, rm=5)
            # The displacement can be at various offsets depending on prefixes and opcode
            
            for prefix_len in range(0, 3):
                if i + prefix_len >= len(seg_data):
                    break
                
                # Validate prefix
                if prefix_len >= 1:
                    p = seg_data[i]
                    if p not in (0xF0, 0x48, 0x4C, 0x66, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47):
                        continue
                if prefix_len >= 2:
                    p2 = seg_data[i + 1]
                    if p2 not in (0xF0, 0x48, 0x4C, 0x66):
                        continue
                
                opcode_offset = prefix_len
                if i + opcode_offset >= len(seg_data):
                    continue
                opcode = seg_data[i + opcode_offset]
                
                # Determine if this opcode has a ModRM byte and what operation it does
                modrm_offset = opcode_offset + 1
                if i + modrm_offset >= len(seg_data):
                    continue
                
                modrm = seg_data[i + modrm_offset]
                mod = (modrm >> 6) & 3
                reg = (modrm >> 3) & 7
                rm = modrm & 7
                
                if mod != 0 or rm != 5:  # Not RIP-relative
                    continue
                
                # Check if this is RIP-relative
                disp_offset = modrm_offset + 1
                if i + disp_offset + 4 > len(seg_data):
                    continue
                
                disp = struct.unpack_from('<i', seg_data, i + disp_offset)[0]
                
                # Calculate instruction length and immediates
                base_len = disp_offset + 4
                imm_len = 0
                is_write = False
                is_read = False
                op_name = ''
                
                if opcode == 0xC6 and reg == 0:  # mov byte [mem], imm8
                    imm_len = 1; is_write = True; op_name = 'mov byte'
                elif opcode == 0xC7 and reg == 0:  # mov dword [mem], imm32
                    imm_len = 4; is_write = True; op_name = 'mov dword'
                elif opcode == 0x88:  # mov byte [mem], reg8
                    is_write = True; op_name = 'mov byte'
                elif opcode == 0x89:  # mov [mem], reg
                    is_write = True; op_name = 'mov'
                elif opcode == 0x80:  # group 1, byte
                    imm_len = 1
                    if reg in (0, 1, 2, 3, 4, 5, 6):  # add, or, adc, sbb, and, sub, xor
                        is_write = True; is_read = True
                        ops = ['add','or','adc','sbb','and','sub','xor']
                        op_name = f'{ops[reg]} byte'
                    elif reg == 7:  # cmp
                        is_read = True; op_name = 'cmp byte'
                elif opcode == 0x81:  # group 1, dword imm32
                    imm_len = 4
                    if reg in (0, 1, 2, 3, 4, 5, 6):
                        is_write = True; is_read = True
                        ops = ['add','or','adc','sbb','and','sub','xor']
                        op_name = f'{ops[reg]} dword'
                    elif reg == 7:
                        is_read = True; op_name = 'cmp dword'
                elif opcode == 0x83:  # group 1, dword imm8
                    imm_len = 1
                    if reg in (0, 1, 2, 3, 4, 5, 6):
                        is_write = True; is_read = True
                        ops = ['add','or','adc','sbb','and','sub','xor']
                        op_name = f'{ops[reg]}'
                    elif reg == 7:
                        is_read = True; op_name = 'cmp'
                elif opcode == 0x09:  # or [mem], reg
                    is_write = True; is_read = True; op_name = 'or'
                elif opcode == 0x01:  # add [mem], reg
                    is_write = True; is_read = True; op_name = 'add'
                elif opcode == 0x08:  # or byte [mem], reg8
                    is_write = True; is_read = True; op_name = 'or byte'
                elif opcode == 0x21:  # and [mem], reg
                    is_write = True; is_read = True; op_name = 'and'
                elif opcode == 0x31:  # xor [mem], reg
                    is_write = True; is_read = True; op_name = 'xor'
                elif opcode == 0xFE:  # group 4 (inc/dec byte)
                    if reg == 0:
                        is_write = True; is_read = True; op_name = 'inc byte'
                    elif reg == 1:
                        is_write = True; is_read = True; op_name = 'dec byte'
                elif opcode == 0xF6:  # group 3 (test/not/neg/mul/imul/div/idiv)
                    imm_len = 1 if reg in (0, 1) else 0  # test has imm8
                    if reg in (2, 3):  # not, neg
                        is_write = True; is_read = True
                        ops = ['test','test','not','neg','mul','imul','div','idiv']
                        op_name = f'{ops[reg]} byte'
                    elif reg in (0, 1):
                        is_read = True; op_name = 'test byte'
                    elif reg in (4, 5, 6, 7):
                        is_read = True
                        ops = ['test','test','not','neg','mul','imul','div','idiv']
                        op_name = f'{ops[reg]} byte'
                else:
                    continue
                
                instr_len = base_len + imm_len
                instr_addr = PRX_BASE + seg['vaddr'] + i
                computed = instr_addr + instr_len + disp
                
                if computed == TARGET_BYTE_ADDR:
                    prefix_str = ''
                    if prefix_len >= 1:
                        p = seg_data[i]
                        if p == 0xF0: prefix_str = 'lock '
                        elif p in (0x48, 0x4C): prefix_str = 'rex.W '
                    if prefix_len >= 2:
                        p2 = seg_data[i + 1]
                        if p2 == 0xF0: prefix_str += 'lock '
                    
                    entry = {
                        'address': f'0x{instr_addr:X}',
                        'instruction': f'{prefix_str}{op_name} [rip+0x{disp:X}] -> 0x{computed:X}',
                        'raw_bytes': seg_data[i:i+instr_len].hex(),
                        'is_write': is_write,
                        'is_read': is_read,
                        'reg_field': reg,
                    }
                    if is_write:
                        writers.append(entry)
                    else:
                        readers.append(entry)
                    break  # Found match for this position, move to next
    
    print(f"\nResults:")
    print(f"  Total READ-ONLY instructions (cmp, test, mov reg,[mem]): {len(readers)}")
    print(f"  Total WRITE instructions (mov [mem], or [mem], etc.): {len(writers)}")
    
    print(f"\n  READERS (first 10):")
    for r in readers[:10]:
        print(f"    {r['address']}: {r['instruction']}")
        print(f"      bytes: {r['raw_bytes']}")
    
    print(f"\n  WRITERS (ALL):")
    for w in writers:
        print(f"    {w['address']}: {w['instruction']}")
        print(f"      bytes: {w['raw_bytes']}")
    
    if len(writers) == 0:
        print(f"\n  *** NO WRITE INSTRUCTIONS FOUND ***")
        print(f"  The flag at 0x{TARGET_BYTE_ADDR:X} is ONLY READ, NEVER WRITTEN by code!")
        print(f"  This means the flag is set by a mechanism OTHER than direct code:")
        print(f"    1. IL2CPP metadata processing (runtime initialization)")
        print(f"    2. Indirect addressing (register-based write)")
        print(f"    3. The flag is never supposed to be set (the gate always returns early)")
        print(f"    4. Missing HLE implementation")
    else:
        print(f"\n  *** FOUND {len(writers)} WRITE INSTRUCTIONS ***")
        for w in writers:
            print(f"    {w['address']}: {w['instruction']}")
    
    # Save results
    with open('/home/z/my-project/scripts/exp152/FLAG_WRITER_RESULTS.json', 'w') as f:
        json.dump({'readers': readers, 'writers': writers}, f, indent=2)
    
    print(f"\n  Results saved to FLAG_WRITER_RESULTS.json")

if __name__ == '__main__':
    main()
