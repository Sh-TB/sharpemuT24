#!/usr/bin/env python3
"""EXP-035: Disassemble the NULL execute call site to understand the loop.

The NULL execute recovery logs show:
  [EXP035-NULL] #N caller=0x0000000800AA01D4 ... (same caller every time)

This script:
  1. Reads eboot.bin from /tmp/games/yatzi/eboot.bin
  2. Finds the offset of 0x800AA01D4 (image base 0x800000000)
  3. Dumps 128 bytes before and 32 bytes after the caller RIP
  4. Disassembles using Capstone (or simple decode if Capstone unavailable)
  5. Also disassembles the AssetGarbageCollectorHelper entry at 0x800BB06A0
"""
import struct
import sys
from pathlib import Path

EBOOT = Path("/tmp/games/yatzi/eboot.bin")
IMAGE_BASE = 0x800000000
CALLER_RIP = 0x800AA01D4
THREAD_ENTRY = 0x800BB06A0

# The LOAD segment 0 has file offset 0x4000, vaddr 0x0.
# So file_offset = vaddr + 0x4000.
FILE_OFFSET_DELTA = 0x4000

def main():
    if not EBOOT.exists():
        print(f"FAIL: {EBOOT} not found")
        sys.exit(1)

    data = EBOOT.read_bytes()
    print(f"eboot.bin size: {len(data)} bytes (0x{len(data):X})")
    print(f"Image base: 0x{IMAGE_BASE:X}")
    print(f"File offset delta: 0x{FILE_OFFSET_DELTA:X} (vaddr + delta = file_offset)")
    print()

    # Try to use Capstone for disassembly
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
        have_capstone = True
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
    except ImportError:
        have_capstone = False
        print("[WARN] Capstone not installed — will dump hex only")
        print("       Install with: pip install capstone")
        print()

    # Dump region around CALLER_RIP
    for label, addr in [("CALLER_RIP (return address)", CALLER_RIP),
                         ("THREAD_ENTRY", THREAD_ENTRY)]:
        vaddr = addr - IMAGE_BASE
        offset = vaddr + FILE_OFFSET_DELTA
        print(f"=== {label} = 0x{addr:X} (vaddr 0x{vaddr:X}, file offset 0x{offset:X}) ===")
        if offset >= len(data):
            print(f"  OUT OF RANGE (file is only 0x{len(data):X} bytes)")
            print()
            continue

        # Dump 128 bytes before, 32 bytes after
        start = max(0, offset - 128)
        end = min(len(data), offset + 32)
        chunk = data[start:end]
        print(f"  Bytes 0x{start:X}..0x{end:X} ({end-start} bytes):")
        for i in range(0, len(chunk), 16):
            row = chunk[i:i+16]
            hex_part = " ".join(f"{b:02X}" for b in row)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            print(f"    {start+i:08X}: {hex_part:<48} |{ascii_part}|")
        print()

        if have_capstone:
            # Disassemble starting 64 bytes before, so we can see the call instruction
            dis_start = max(0, offset - 64)
            dis_chunk = data[dis_start:end]
            print(f"  Disassembly (from 0x{IMAGE_BASE + (dis_start - FILE_OFFSET_DELTA):X}):")
            for insn in md.disasm(dis_chunk, IMAGE_BASE + (dis_start - FILE_OFFSET_DELTA)):
                marker = " <<<" if insn.address == addr else ""
                # Trim to a reasonable window
                if insn.address > addr + 16:
                    break
                print(f"    {insn.address:X}: {insn.mnemonic} {insn.op_str}{marker}")
            print()

    # Also check what's at the entry point of AssetGarbageCollectorHelper
    # The ABI trace shows: rip=0x800BB06A0 rdi=0x00000006006D0FF0 rsi=0 ...
    # So the thread is started with rdi = some pointer. Let's see what the
    # entry function does.
    print("=== Analysis ===")
    print(f"The NULL execute caller RIP is 0x{CALLER_RIP:X}.")
    print(f"This is the RETURN ADDRESS on the stack — the instruction AFTER")
    print(f"the `call` that called NULL.")
    print()
    print(f"The `call NULL` instruction is at 0x{CALLER_RIP - 2:X} to 0x{CALLER_RIP - 6:X}")
    print(f"(call instructions are 2-6 bytes depending on encoding).")
    print()
    print(f"Look for the call instruction in the disassembly above. It's the one")
    print(f"whose address + length == 0x{CALLER_RIP:X}.")

if __name__ == "__main__":
    main()
