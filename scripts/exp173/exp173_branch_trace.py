#!/usr/bin/env python3
"""EXP-173 TEST 2: Complete branch/call/jump analysis between +0x191F and +0x3969."""

import struct

EBOOT_PATH = "/tmp/exp173_games/eboot.bin"
EBOOT_BASE = 0x800000000
FUNC_START = 0x8013EB6B0
INIT_WRITE = 0x8013EF019  # +0x3969

data = open(EBOOT_PATH, 'rb').read()
e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]

for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    p_flags = struct.unpack_from('<I', data, off + 4)[0]
    p_offset = struct.unpack_from('<Q', data, off + 8)[0]
    p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
    if p_type == 1 and (p_flags & 1):
        seg_offset = p_offset
        seg_vaddr = p_vaddr
        break

func_vaddr = FUNC_START - EBOOT_BASE
foff = seg_offset + (func_vaddr - seg_vaddr)
init_offset = INIT_WRITE - FUNC_START

# Read function from +0x191F to +0x3969
chunk = data[foff + 0x191F:foff + init_offset + 16]

print("=" * 80)
print("TEST 2: All branches/calls/jumps between +0x191F and +0x3969")
print("=" * 80)

# Find all control flow instructions
entries = []
i = 0
while i < len(chunk) - 6:
    b0 = chunk[i]
    b1 = chunk[i+1] if i+1 < len(chunk) else 0
    real_offset = 0x191F + i
    addr = FUNC_START + real_offset
    
    # CALL (E8)
    if b0 == 0xE8 and i + 4 < len(chunk):
        rel = struct.unpack_from('<i', chunk, i+1)[0]
        target = addr + 5 + rel
        entries.append((real_offset, addr, "call", "0x%X" % target, target))
        i += 5
        continue
    
    # JMP rel32 (E9)
    if b0 == 0xE9 and i + 4 < len(chunk):
        rel = struct.unpack_from('<i', chunk, i+1)[0]
        target = addr + 5 + rel
        target_off = real_offset + 5 + rel
        entries.append((real_offset, addr, "jmp", "0x%X (+0x%X)" % (target, target_off), target))
        i += 5
        continue
    
    # JMP reg (FF /4)
    if b0 == 0xFF and i + 1 < len(chunk):
        modrm = chunk[i+1]
        reg = (modrm >> 3) & 7
        mod = (modrm >> 6) & 3
        rm = modrm & 7
        if reg == 4:  # JMP
            if mod == 3:
                regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']
                entries.append((real_offset, addr, "jmp_reg", regs[rm], 0))
                i += 2
                continue
            elif mod == 0 and rm == 5:  # RIP-relative
                disp = struct.unpack_from('<i', chunk, i+2)[0]
                target = addr + 6 + disp
                entries.append((real_offset, addr, "jmp_indirect", "[0x%X]" % target, target))
                i += 6
                continue
    
    # RET (C3)
    if b0 == 0xC3:
        entries.append((real_offset, addr, "ret", "", 0))
        i += 1
        continue
    
    # jcc rel32 (0F 8x)
    if b0 == 0x0F and 0x80 <= b1 <= 0x8F and i + 5 < len(chunk):
        rel = struct.unpack_from('<i', chunk, i+2)[0]
        target = addr + 6 + rel
        target_off = real_offset + 6 + rel
        cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b1 - 0x80]
        skips = target_off > init_offset
        entries.append((real_offset, addr, cc, "0x%X (+0x%X)%s" % (target, target_off, " *** SKIPS ***" if skips else ""), target))
        i += 6
        continue
    
    # jcc rel8 (7x)
    if 0x70 <= b0 <= 0x7F and i + 1 < len(chunk):
        rel = struct.unpack_from('<b', chunk, i+1)[0]
        target = addr + 2 + rel
        target_off = real_offset + 2 + rel
        cc = ['jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'][b0 - 0x70]
        skips = target_off > init_offset
        entries.append((real_offset, addr, cc, "0x%X (+0x%X)%s" % (target, target_off, " *** SKIPS ***" if skips else ""), target))
        i += 2
        continue
    
    i += 1

# Print all entries
print("\nAll control flow instructions:")
for off, addr, op, target_str, target_val in entries:
    print("  +0x%04X (0x%X): %s %s" % (off, addr, op, target_str))

# Identify skip branches
print("\n=== Branches that SKIP init write at +0x3969 ===")
skip_count = 0
for off, addr, op, target_str, target_val in entries:
    if op.startswith('j') and "SKIPS" in target_str:
        skip_count += 1
        print("  +0x%04X (0x%X): %s %s" % (off, addr, op, target_str))

print("\nTotal skip branches: %d" % skip_count)

# Identify unconditional jumps
print("\n=== Unconditional jumps ===")
for off, addr, op, target_str, target_val in entries:
    if op in ("jmp", "jmp_reg", "jmp_indirect"):
        print("  +0x%04X (0x%X): %s %s" % (off, addr, op, target_str))

# Identify returns
print("\n=== Returns ===")
for off, addr, op, target_str, target_val in entries:
    if op == "ret":
        print("  +0x%04X (0x%X): %s" % (off, addr, op))

# Identify calls that might not return
print("\n=== Calls (first 30) ===")
call_count = 0
for off, addr, op, target_str, target_val in entries:
    if op == "call":
        call_count += 1
        if call_count <= 30:
            print("  +0x%04X (0x%X): call %s" % (off, addr, target_str))
print("  ... total calls: %d" % call_count)

