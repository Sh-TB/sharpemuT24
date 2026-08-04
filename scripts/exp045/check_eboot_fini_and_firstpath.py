#!/usr/bin/env python3
"""EXP-045 Task 1+3: Check eboot fini_array + disassemble init first-time path.

Task 1: Check eboot.bin's fini_array (like we did for PRX in EXP-044)
Task 3: Disassemble init function first-time path (0x8013EB6E7-0x8013EBDFA)
Task 4: Check if first-time path writes to [0x801E9DF28] or [0x801E51240]
"""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000

data = EBOOT.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

print("=" * 70)
print("Task 1: Check eboot.bin fini_array")
print("=" * 70)

# eboot DT_INIT at 0x800000010
# From EXP-043 analysis:
# 0x800000045: lea rbx, [rip + 0x1d1c384]  -> fini_array start
# 0x800000050: add rbx, -8  (iterate backwards)
# 
# 0x800000045: lea rbx, [rip + 0x1d1c384]
# Instruction is 7 bytes: 48 8D 1D 84 C3 D1 01
# RIP after = 0x80000004C
# Target = 0x80000004C + 0x1D1C384 = 0x801D1C3D0

fini_array_end = 0x80000004C + 0x1D1C384
print(f"eboot fini_array end: 0x{fini_array_end:X}")
fini_vaddr = fini_array_end - IMAGE_BASE  # 0x1D1C3D0

# Find file offset
e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

fini_foff = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type != 1: continue
    p_offset = struct.unpack_from('<Q', data, off + 8)[0]
    p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
    p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
    if p_vaddr <= fini_vaddr < p_vaddr + p_filesz:
        fini_foff = p_offset + (fini_vaddr - p_vaddr)
        break

# Also find all relocations
dyn_foff = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type == 2:
        dyn_foff = struct.unpack_from('<Q', data, off + 8)[0]
        dyn_size = struct.unpack_from('<Q', data, off + 32)[0]
        break

rela_addr = rela_size = 0
i = 0
while i < dyn_size:
    d_tag, d_val = struct.unpack_from('<qQ', data, dyn_foff + i)
    if d_tag == 0: break
    if d_tag == 7: rela_addr = d_val
    elif d_tag == 8: rela_size = d_val
    i += 16

def vaddr_to_foff(vaddr):
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type != 1: continue
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        if p_vaddr <= vaddr < p_vaddr + p_filesz:
            return p_offset + (vaddr - p_vaddr)
    return None

rela_foff = vaddr_to_foff(rela_addr)

# Check fini_array entries (backwards from fini_array_end)
print(f"\nChecking eboot fini_array entries (backwards from 0x{fini_array_end:X}):")
fini_count = 0
for j in range(1, 21):
    entry_vaddr = fini_vaddr - j * 8
    # Check file value
    entry_foff = vaddr_to_foff(entry_vaddr)
    file_val = 0
    if entry_foff and entry_foff + 8 <= len(data):
        file_val = struct.unpack_from('<Q', data, entry_foff)[0]
    
    # Check relocation
    reloc_val = None
    for i in range(0, rela_size, 24):
        r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, rela_foff + i)
        if r_offset == entry_vaddr:
            rel_type = r_info & 0xFFFFFFFF
            if rel_type == 8:  # RELATIVE
                reloc_val = IMAGE_BASE + r_addend
            break
    
    runtime_val = reloc_val if reloc_val else file_val
    if runtime_val != 0:
        fini_count += 1
        print(f"  [{j:2d}] [0x{IMAGE_BASE + entry_vaddr:X}] = 0x{runtime_val:X} *** NON-ZERO ***")
    else:
        print(f"  [{j:2d}] [0x{IMAGE_BASE + entry_vaddr:X}] = 0x0 (NULL, stop)")
        break

print(f"\neboot fini_array entries: {fini_count}")

# Now Task 3: Disassemble init function first-time path
print("\n" + "=" * 70)
print("Task 3: Disassemble init first-time path (0x8013EB6E7 - 0x8013EBDFA)")
print("=" * 70)

# The init function at 0x8013EB6B0:
# 0x8013EB6DA: cmp byte [0x801E9A224], 0  (done flag)
# 0x8013EB6E1: jne 0x8013EBDFA  (if done, skip to common path)
# 0x8013EB6E7: call 0x801937500  (first-time init starts)
# ... first-time code ...
# 0x8013EBDFA: common path starts

# Disassemble from 0x8013EB6E7 to 0x8013EBDFA
addr = 0x8013EB6E7
offset = addr - IMAGE_BASE + 0x4000
chunk = data[offset:offset + (0x8013EBDFA - 0x8013EB6E7) + 256]

# Target globals to check
TARGETS = {0x801E9DF28: "LIST_HEAD", 0x801E51240: "GLOBAL_PTR", 0x801EF7610: "HASH_TABLE"}

print(f"\nScanning first-time path for writes to key globals...")
print(f"Range: 0x8013EB6E7 to 0x8013EBDFA ({0x8013EBDFA - 0x8013EB6E7} bytes)")
print()

calls_in_path = []
writes_to_targets = []

for insn in md.disasm(chunk, addr):
    if insn.address > 0x8013EBDFA:
        break
    
    # Check for writes to target globals
    for op in insn.operands:
        if op.type == 3 and op.mem.base == 41:  # RIP-relative
            target = insn.address + insn.size + op.mem.disp
            if target in TARGETS:
                is_write = (insn.mnemonic == "mov" and 
                           "," in insn.op_str and 
                           "[" in insn.op_str.split(",")[0])
                if is_write:
                    writes_to_targets.append((insn.address, insn.mnemonic, insn.op_str, TARGETS[target]))
    
    # Track calls
    if insn.mnemonic == "call":
        calls_in_path.append((insn.address, insn.op_str))

print(f"Calls in first-time path: {len(calls_in_path)}")
for addr, target in calls_in_path:
    print(f"  0x{addr:X}: call {target}")

print(f"\nWrites to target globals in first-time path: {len(writes_to_targets)}")
for addr, mnemonic, op_str, name in writes_to_targets:
    print(f"  0x{addr:X}: {mnemonic} {op_str}  [{name}]")
