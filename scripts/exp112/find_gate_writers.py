#!/usr/bin/env python3
"""
EXP-112 step 4 — find all writers to the gate global at 0x808BF43A0
(the flag read by call #151 / 0x804F3E700), and disassemble the
full context around the gate check in real_init.

Also: look at what 0x804F3DF90 (call #152 target) actually does —
specifically whether it's the callback registration trigger.
"""
import os
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

PRX_PATH = "/tmp/games/yatzi/Il2cppUserAssemblies.prx"
PRX_RUNTIME_BASE = 0x804CD5000

GATE_FUNC_RUNTIME = 0x804F3E700
GATE_FUNC_ELF = GATE_FUNC_RUNTIME - PRX_RUNTIME_BASE  # 0x269700

# The gate function is: mov eax, [rip + 0x3c15c9a]; ret
# rip at the mov instruction = 0x269700 (start of function)
# rip after the mov instruction = 0x269706 (mov is 6 bytes)
# global elf_va = 0x269706 + 0x3c15c9a = 0x3e7f3a0... wait let me recompute
# Actually: rip-relative addressing in x86_64 uses rip = address of NEXT instruction
# mov eax, [rip + disp32] is encoded as 8B 05 [4-byte disp]
# Total instruction size = 6 bytes
# rip after mov = 0x269700 + 6 = 0x269706
# global elf_va = 0x269706 + 0x3c15c9a = 0x3e7f3a0 ... wait that doesn't look right
# Let me recompute: 0x269706 + 0x3c15c9a
# 0x269706 = 2,526,470
# 0x3c15c9a = 63,097,242
# Sum = 65,623,712 = 0x3E7F3A0
# Hmm, but the exec segment is 0x2b9722a (45,602,858) bytes, so 0x3E7F3A0 is outside.
# That means the global is in another segment.
# Runtime VA = elf_va + PRX_RUNTIME_BASE = 0x3E7F3A0 + 0x804CD5000 = 0x808BF43A0
# So runtime VA 0x808BF43A0 — this is in the RW segment range we identified earlier:
#   RW segment: elf_va=0x3a14000 size=0x23b818  → 0x3a14000..0x3c4f818
# But 0x3E7F3A0 is OUTSIDE the RW segment we found!
# Let me check: 0x3E7F3A0 vs 0x3a14000..0x3c4f818
# 0x3a14000 < 0x3E7F3A0 < 0x3c4f818? No, 0x3E7F3A0 > 0x3c4f818
# So the global is in a different segment. Let me check the RW segments we listed:
#   p_vaddr=0x3a14000  size=0x23b818  [RW-]
#   p_vaddr=0x3c50000  size=0x21cbc8  [RW-]  (p_memsz=0x444778 — has BSS)
#   p_vaddr=0x4094780  size=0x8cf0a8  [---]  (note: no R/W/X flags — probably NOTE?)
# 
# 0x3E7F3A0 is in range 0x3a14000..0x3a14000+0x23b818 = 0x3a14000..0x3c4f818. 
# Let me recompute: 0x3a14000 + 0x23b818 = 0x3c4f818. And 0x3E7F3A0 > 0x3c4f818.
# So actually 0x3E7F3A0 is NOT in the first RW segment.
# What about the second RW segment: 0x3c50000..0x3c50000+0x21cbc8 = 0x3c50000..0x3e71bc8
# 0x3E7F3A0 vs 0x3c50000..0x3e71bc8: 0x3E7F3A0 > 0x3e71bc8 — JUST barely outside!
# Wait, 0x3E7F3A0 - 0x3e71bc8 = 0xD7D8. So it's 55K bytes past the end of the second RW segment's FILE size.
# But the second RW segment has p_memsz=0x444778 (larger than p_filesz=0x21cbc8), so the BSS extends further.
# 0x3c50000 + 0x444778 = 0x4094778. So 0x3E7F3A0 IS within the BSS of the second RW segment!
# That means the gate global is in BSS (zero-initialized).
# At program start, BSS is zero. So the gate starts as 0, and #152 should be CALLED (not skipped).
# UNLESS something writes to it.

GATE_GLOBAL_RUNTIME = 0x808B543A0   # corrected: was 0x808BF43A0 (I misread '5' as 'F')
GATE_GLOBAL_ELF = GATE_GLOBAL_RUNTIME - PRX_RUNTIME_BASE  # 0x3E7F3A0


def load_prx_text():
    with open(PRX_PATH, "rb") as f:
        data = f.read()
    elf = ELFFile(BytesIO(data))
    for i in range(elf["e_phnum"]):
        hdr = elf._get_segment_header(i)
        seg = Segment(hdr, elf.stream)
        if seg["p_type"] == "PT_LOAD" and (seg["p_flags"] & 1):
            return seg["p_vaddr"], seg.data()
    raise RuntimeError("no exec segment")


def find_writers_to_global(text_data, text_base, target_elf_va):
    """
    Find all RIP-relative writes to target_elf_va in the text segment.
    We're looking for instructions like:
      mov [rip + disp32], rax   (48 89 05 [disp32])
      mov [rip + disp32], eax   (89 05 [disp32])
      mov [rip + disp32], r64   (48 89 0X 05 [disp32], where X encodes the source reg)
      mov dword ptr [rip + disp32], imm32  (C7 05 [disp32] [imm32])
    
    For each candidate instruction, compute the effective address and check if it matches target_elf_va.
    """
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    
    # We can't do a full linear sweep over 45MB. Instead, scan function-by-function
    # using our heuristic function starts.
    n = len(text_data)
    align = 16
    func_starts = []
    for off in range(0, n, align):
        if off >= 16 and text_data[off-1] != 0xCC:
            tail = text_data[max(0, off-8):off]
            if 0xCC not in tail:
                continue
        if off + 4 <= n:
            sig = text_data[off:off+4]
            if (sig == b"\xF3\x0F\x1E\xFA" or
                sig[0] == 0x55 or
                (sig[0] == 0x41 and sig[1] in (0x54,0x55,0x56,0x57)) or
                (sig[0] == 0x48 and sig[1] == 0x83 and sig[2] == 0xEC) or
                (sig[0] == 0x48 and sig[1] == 0x81 and sig[2] == 0xEC)):
                func_starts.append(off)
    
    print(f"[+] scanning {len(func_starts)} functions for writes to 0x{target_elf_va:x} (runtime 0x{target_elf_va+PRX_RUNTIME_BASE:x})")
    
    writers = []
    for i, start_off in enumerate(func_starts):
        end_off = func_starts[i+1] if i+1 < len(func_starts) else n
        if end_off - start_off > 0x100000:
            continue
        chunk = text_data[start_off:end_off]
        try:
            for ins in md.disasm(chunk, text_base + start_off):
                # Check if this instruction writes to memory via RIP-relative addressing
                # Look for mov [rip+disp], src instructions
                if ins.mnemonic not in ("mov", "movabs", "and", "or", "xor", "add", "sub"):
                    continue
                # Skip pure register-register moves
                ops = ins.operands
                if len(ops) < 2:
                    continue
                dst = ops[0]
                if dst.type != CS_OP_MEM:
                    continue
                mem = dst.mem
                if mem.base == 0:  # need RIP-relative or absolute addressing
                    continue
                base_name = ins.reg_name(mem.base)
                if base_name != "rip":
                    continue
                # Compute effective address
                eff_elf = ins.address + ins.size + mem.disp
                if eff_elf == target_elf_va:
                    writers.append({
                        "site_runtime_va": ins.address + PRX_RUNTIME_BASE,
                        "site_elf_va": ins.address,
                        "containing_func_elf_va": text_base + start_off,
                        "containing_func_runtime_va": text_base + start_off + PRX_RUNTIME_BASE,
                        "insn": f"{ins.mnemonic} {ins.op_str}",
                        "bytes": ins.bytes.hex(),
                    })
        except Exception:
            continue
    return writers


def main():
    text_base, text_data = load_prx_text()
    print(f"[+] text_base=0x{text_base:x}  size=0x{len(text_data):x}")
    print(f"[+] gate global: elf_va=0x{GATE_GLOBAL_ELF:x}  runtime=0x{GATE_GLOBAL_RUNTIME:x}")

    writers = find_writers_to_global(text_data, text_base, GATE_GLOBAL_ELF)
    print(f"\n[+] found {len(writers)} writers to gate global")
    for w in writers:
        print(f"  site=0x{w['site_runtime_va']:x}  in func 0x{w['containing_func_runtime_va']:x}  insn: {w['insn']}")
    
    # === Look at full context of gate check in real_init ===
    # The gate check is at site 0x804F05C76 (call #151 = 0x804F3E700)
    # Let me disasm from 0x804F05C40 (a bit before) to 0x804F05D70 (end of real_init)
    print("\n" + "=" * 78)
    print("Full context around gate check in real_init (0x804F05C40..0x804F05D70):")
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    start_elf = 0x230C40
    end_elf = 0x230D70
    chunk = text_data[start_elf:end_elf]
    for ins in md.disasm(chunk, start_elf):
        rt = ins.address + PRX_RUNTIME_BASE
        marker = ""
        if rt == 0x804F05C76:
            marker = "  <-- call #151 (GATE)"
        elif rt == 0x804F05C82:
            marker = "  <-- call #156"
        elif rt == 0x804F05C9D:
            marker = "  <-- call #157 (helper_1)"
        elif rt == 0x804F05CA4:
            marker = "  <-- call #158"
        elif rt == 0x804F05CAE:
            marker = "  <-- call #159 (PLT/abort stub)"
        print(f"  0x{rt:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}{marker}")


if __name__ == "__main__":
    main()
