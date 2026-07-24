#!/usr/bin/env python3
"""
Disassemble bytes around a guest RIP in eboot.bin.

PS5 eboot.bin is mapped at GUEST_IMAGE_BASE = 0x0000000800000000 in guest memory.
We use pyelftools to parse the SELF/ELF and capstone to decode the instructions.
"""
import sys
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

GUEST_IMAGE_BASE = 0x0000000800000000

def main():
    if len(sys.argv) < 3:
        print("Usage: disasm_around_rip.py <eboot.bin> <rip_hex> [before=80] [after=80]")
        sys.exit(1)

    eboot_path = sys.argv[1]
    rip = int(sys.argv[2], 16)
    before = int(sys.argv[3]) if len(sys.argv) > 3 else 80
    after = int(sys.argv[4]) if len(sys.argv) > 4 else 80

    target_offset = rip - GUEST_IMAGE_BASE  # vaddr in ELF

    # Find the PT_LOAD segment containing the target_offset
    with open(eboot_path, 'rb') as f:
        elf = ELFFile(f)
        target_segment = None
        for p in elf.iter_segments():
            if p['p_type'] == 'PT_LOAD':
                vaddr = p['p_vaddr']
                memsz = p['p_memsz']
                if vaddr <= target_offset < vaddr + memsz:
                    target_segment = p
                    break

        if target_segment is None:
            print(f"!! No PT_LOAD contains target_offset 0x{target_offset:X}")
            sys.exit(1)

        seg_vaddr = target_segment['p_vaddr']
        seg_offset = target_segment['p_offset']
        seg_filesz = target_segment['p_filesz']
        print(f"=== Segment: vaddr=0x{seg_vaddr:X} offset=0x{seg_offset:X} filesz=0x{seg_filesz:X}")
        print(f"=== Target RIP: 0x{rip:X} (guest), vaddr=0x{target_offset:X} (ELF)")
        print(f"=== Offset within segment: 0x{target_offset - seg_vaddr:X}")
        print()

        # Read segment content from file
        f.seek(seg_offset)
        seg_data = f.read(seg_filesz)

    rip_offset_in_seg = target_offset - seg_vaddr
    if rip_offset_in_seg >= len(seg_data):
        print(f"!! RIP offset 0x{rip_offset_in_seg:X} exceeds segment filesz 0x{len(seg_data):X}")
        sys.exit(1)

    # Decode instructions in a window around the RIP.
    # We need to start decoding before RIP to capture instructions that
    # lead up to it. ELF code is variable-length, so we start 256 bytes
    # before and decode forward, then pick the instructions we want.
    pre_window_bytes = min(512, rip_offset_in_seg)
    start_offset_in_seg = max(0, rip_offset_in_seg - pre_window_bytes)
    end_offset_in_seg = min(len(seg_data), rip_offset_in_seg + 256)

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    code = seg_data[start_offset_in_seg:end_offset_in_seg]
    instructions = list(md.disasm(code, GUEST_IMAGE_BASE + seg_vaddr + start_offset_in_seg))

    # Filter to instructions ending at or just before the RIP
    pre_insts = []
    for inst in instructions:
        if inst.address + inst.size > rip:
            break
        pre_insts.append(inst)

    pre_insts = pre_insts[-before:]

    # Find the instruction at RIP
    rip_inst = None
    for inst in instructions:
        if inst.address == rip:
            rip_inst = inst
            break

    rip_idx = instructions.index(rip_inst) if rip_inst else -1
    post_insts = instructions[rip_idx+1:rip_idx+1+after] if rip_idx >= 0 else []

    branch_mnemonics = {"call", "jmp", "je", "jne", "jz", "jnz", "ja", "jae", "jb",
                       "jbe", "jg", "jl", "jge", "jle", "js", "jns", "jo", "jno",
                       "jp", "jnp", "jc", "jnc", "jcxz", "jecxz", "jrcxz", "ret",
                       "retn", "syscall", "sysret", "int"}

    print(f"=== Disassembly: {len(pre_insts)} before, 1 at RIP, {len(post_insts)} after")
    print()
    print(f"--- Pre-rip ({len(pre_insts)} insts) ---")
    for inst in pre_insts:
        marker = ">>" if inst.mnemonic in branch_mnemonics else "  "
        # Show r12 references explicitly
        if "r12" in inst.op_str.lower() or "r12" == inst.mnemonic.lower():
            marker = "R12"
        print(f"{marker} 0x{inst.address:X}:  {inst.mnemonic:8s} {inst.op_str}")

    if rip_inst:
        print()
        print(f"--- AT RIP (fault site) ---")
        print(f"!! 0x{rip_inst.address:X}:  {rip_inst.mnemonic:8s} {rip_inst.op_str}  <-- FAULT HERE")
        print(f"   bytes: {' '.join(f'{b:02X}' for b in rip_inst.bytes)}")
        print()

    print(f"--- Post-rip ({len(post_insts)} insts) ---")
    for inst in post_insts:
        marker = ">>" if inst.mnemonic in branch_mnemonics else "  "
        if "r12" in inst.op_str.lower():
            marker = "R12"
        print(f"{marker} 0x{inst.address:X}:  {inst.mnemonic:8s} {inst.op_str}")

if __name__ == "__main__":
    main()
