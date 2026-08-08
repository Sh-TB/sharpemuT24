#!/usr/bin/env python3
"""Disassemble eboot starting at an exact address (no offset back)."""
import sys
try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "capstone"])
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <eboot> <guest-vaddr> [<count>]")
        return 1
    eboot_path = sys.argv[1]
    guest_vaddr = int(sys.argv[2], 16) if "x" in sys.argv[2].lower() else int(sys.argv[2])
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    image_base = 0x0000000800000000

    with open(eboot_path, "rb") as f:
        data = f.read()

    file_offset = guest_vaddr - image_base

    # Show 32 bytes of hex first
    print(f"=== Raw hex at file offset 0x{file_offset:x} (guest vaddr 0x{guest_vaddr:x}) ===")
    start = max(0, file_offset - 16)
    end = min(len(data), file_offset + 96)
    chunk = data[start:end]
    for i in range(0, len(chunk), 16):
        addr = image_base + start + i
        hex_str = " ".join(f"{b:02x}" for b in chunk[i:i+16])
        marker = " <<<" if start + i <= file_offset < start + i + 16 else ""
        print(f"0x{addr:x}: {hex_str}{marker}")
    print()

    # Disassemble
    print(f"=== Disassembly starting AT 0x{guest_vaddr:x} ===")
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    chunk = data[file_offset:file_offset + 256]
    for insn in md.disasm(chunk, guest_vaddr):
        print(f"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}")
        count -= 1
        if count <= 0:
            break

    return 0

if __name__ == "__main__":
    sys.exit(main())
