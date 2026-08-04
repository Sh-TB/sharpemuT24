#!/usr/bin/env python3
"""
EXP-112 step 2 — investigate the 4 PLT stubs called from real_init and
the tail calls (#157-#164) that share targets with the registered
callback 0x804FA1FE0.

Specifically:
1. Disassemble each PLT stub to find what HLE function it resolves to
   (PS5 PRX PLT stubs typically do: jmp [GOT entry]; the GOT entry
   points to either the dynamic linker resolver or the resolved HLE
   function).
2. Look at the disassembly of real_init's tail (calls #147-#164) to
   understand what state is being set up at the end.
3. Look at what 0x804F68D90 (call #4) does — it's in the
   0x804F68xxx-0x804F6Fxxx range where the WaitSema(0xA6) stall lives
   (0x804F6E510).
"""
import os
from io import BytesIO
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

PRX_PATH = "/tmp/games/yatzi/Il2cppUserAssemblies.prx"
PRX_RUNTIME_BASE = 0x804CD5000


def load_prx_text():
    with open(PRX_PATH, "rb") as f:
        data = f.read()
    elf = ELFFile(BytesIO(data))
    for i in range(elf["e_phnum"]):
        hdr = elf._get_segment_header(i)
        seg = Segment(hdr, elf.stream)
        if seg["p_type"] == "PT_LOAD" and (seg["p_flags"] & 1):
            return seg["p_vaddr"], seg.data(), elf
    raise RuntimeError("no exec segment")


def find_rw_segment(elf):
    """Find the read-write PT_LOAD segment — contains GOT."""
    for i in range(elf["e_phnum"]):
        hdr = elf._get_segment_header(i)
        seg = Segment(hdr, elf.stream)
        if seg["p_type"] == "PT_LOAD" and (seg["p_flags"] & 2) and not (seg["p_flags"] & 1):
            return seg["p_vaddr"], seg["p_filesz"], seg.data()
    return None, None, None


def disasm_at(text_data, text_base, elf_va, size=0x40, label=""):
    off = elf_va - text_base
    if off < 0 or off >= len(text_data):
        print(f"  [!] {label} elf_va=0x{elf_va:x} out of range")
        return
    chunk = text_data[off:off+size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n--- {label}  elf_va=0x{elf_va:x}  runtime=0x{elf_va+PRX_RUNTIME_BASE:x}  ---")
    for ins in md.disasm(chunk, elf_va):
        print(f"  0x{ins.address:x}: {ins.bytes.hex():24s}  {ins.mnemonic:8s} {ins.op_str}")


def main():
    text_base, text_data, elf = load_prx_text()
    print(f"[+] exec segment: elf_va=0x{text_base:x}  size=0x{len(text_data):x}")

    # Find RW segment (where GOT lives)
    rw_base, rw_size, rw_data = find_rw_segment(elf)
    if rw_base is not None:
        print(f"[+] RW segment: elf_va=0x{rw_base:x}  size=0x{rw_size:x}")
    else:
        print("[!] no RW segment found")

    # ----- PLT stubs -----
    # 0x230 and 0x280 are the PLT stub targets called from real_init
    plt_targets = [0x230, 0x280]
    for plt_elf in plt_targets:
        disasm_at(text_data, text_base, plt_elf, size=0x20, label=f"PLT stub @ 0x{plt_elf:x}")

    # ----- PLT stub usually does: jmp [rip+disp32] or jmp qword ptr [abs]
    # ----- where the GOT entry holds the resolved function pointer.
    # ----- The GOT entry for an unresolved PLT stub points back to a
    # ----- resolver stub (typically immediately after the PLT jmp, a few
    # ----- bytes that push the reloc index and jmp to the dynamic linker).
    # ----- We want to know: what is the GOT entry's runtime VA?
    # ----- Then we can check if SharpEmu's HLE table has that address
    # ----- registered with a name.

    # For each PLT stub, parse its first instruction to get the GOT address
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    for plt_elf in plt_targets:
        off = plt_elf - text_base
        chunk = text_data[off:off+0x10]
        insns = list(md.disasm(chunk, plt_elf))
        if not insns:
            continue
        first = insns[0]
        print(f"\n[PLT analysis] stub @ elf_va=0x{plt_elf:x}:")
        print(f"  first insn: {first.mnemonic} {first.op_str}  ({first.bytes.hex()})")
        if first.mnemonic == "jmp" and len(first.operands) == 1:
            op = first.operands[0]
            if op.type == CS_OP_MEM:
                mem = op.mem
                if mem.base != 0:  # rip-relative
                    base_name = first.reg_name(mem.base)
                    if base_name == "rip":
                        got_elf_va = first.address + first.size + mem.disp
                        print(f"  base=rip, disp=0x{mem.disp:x} -> GOT entry at elf_va=0x{got_elf_va:x} (runtime 0x{got_elf_va+PRX_RUNTIME_BASE:x})")
                        # Read 8 bytes at that GOT offset
                        # The GOT lives in the RW segment; but it might also be in the exec segment
                        # for the .got.plt section.
                        if text_base <= got_elf_va < text_base + len(text_data):
                            got_off = got_elf_va - text_base
                            got_val = int.from_bytes(text_data[got_off:got_off+8], "little")
                            print(f"  GOT current value: 0x{got_val:x} (file bytes)")
                            # In a stripped PRX before relocation, this is usually 0 or
                            # points to the resolver stub (plt_elf + 6)
                        elif rw_base is not None and rw_base <= got_elf_va < rw_base + rw_size:
                            got_off = got_elf_va - rw_base
                            got_val = int.from_bytes(rw_data[got_off:got_off+8], "little")
                            print(f"  GOT current value: 0x{got_val:x} (in RW segment, file bytes)")
                        else:
                            print(f"  GOT elf_va=0x{got_elf_va:x} not in exec or RW segment")
                elif mem.base == 0 and mem.index == 0:
                    # Absolute address (rare in PIE)
                    print(f"  absolute jmp to 0x{mem.disp:x}")

    # ----- Look at calls #4 (0x804F68D90) and #150 (0x804F05D70) -----
    # #4 is interesting because it's in the 0x804F68xxx range (near WaitSema stall at 0x804F6E510)
    # #150 is interesting because it's at 0x804F05D70 — that's exactly the END of real_init
    # (real_init size 4560 = 0x11d0; start 0x804F04BA0 + 0x11d0 = 0x804F05D70)
    # Wait — that means call #150 is the call instruction whose target is REAL_INIT_END.
    # Actually re-reading: "call 0x230d70" means the call site is at 0x804F05B71 and the
    # target is 0x804F05D70 (elf 0x230d70). So target 0x804F05D70 is a function that starts
    # IMMEDIATELY after real_init ends! That's a separate function.
    print("\n" + "=" * 78)
    print("Call #4 target 0x804F68D90 — possibly near WaitSema stall area")
    disasm_at(text_data, text_base, 0x293d90, size=0x80, label="0x804F68D90 (call #4 target)")
    print("\n" + "=" * 78)
    print("Call #150 target 0x804F05D70 — function immediately after real_init")
    disasm_at(text_data, text_base, 0x230d70, size=0x60, label="0x804F05D70 (call #150 target)")

    # ----- Tail calls #157-#164 -----
    # These are at the end of real_init. Let's see what they look like in context.
    # Tail starts around call #147 (site 0x804F05B55)
    print("\n" + "=" * 78)
    print("Disassembly of real_init's tail (from call #147 onward, site 0x804F05B55):")
    tail_start_elf = 0x804F05B55 - PRX_RUNTIME_BASE
    disasm_at(text_data, text_base, tail_start_elf, size=0x220, label="real_init tail")


if __name__ == "__main__":
    main()
