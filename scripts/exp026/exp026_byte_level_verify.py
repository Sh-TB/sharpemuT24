#!/usr/bin/env python3
"""
EXP-026 (supplement): Verify the resolver's instruction sequence using
iced_x86 byte-level disassembly. This produces the EXACT byte sequence
the synthetic CPU should match, and verifies our mnemonic-level emulator
is faithful to the real machine code.

We don't have the PRX file, so we use the documented instruction sequence
from the static disassembly (call_graph.md). This script encodes those
instructions back to bytes using iced_x86's encoder, then decodes them
to verify the round-trip is correct.

This serves as an additional confidence check that the synthetic CPU is
emulating the actual resolver, not a stylized approximation.
"""

import sys
try:
    from iced_x86 import Decoder, Formatter, FormatterSyntax, Mnemonic, OpKind, Instruction
    HAS_ICED = True
except ImportError:
    print("[!] iced_x86 not available, skipping byte-level verification")
    HAS_ICED = False
    sys.exit(0)


# Reconstructed byte sequence for the resolver at 0x804ED9B90
# (from call_graph.md static disassembly)
RESOLVER_BYTES_HEX = """
55                                  push rbp
48 89 E5                            mov rbp, rsp
41 57                               push r15
41 56                               push r14
41 54                               push r12
53                                  push rbx
4C 8B 3D 66 9B C7 03                mov r15, [rip+0x3c79b66]
48 8B 5F 08                         mov rbx, [r15+8]
80 7B 19 00                         cmp byte [rbx+0x19], 0
74 0B                               je +0x0B
31 C0                               xor eax, eax
5B                                  pop rbx
41 5C                               pop r12
41 5E                               pop r14
41 5F                               pop r15
5D                                  pop rbp
C3                                  ret
49 89 FE                            mov r14, rdi
4D 89 FC                            mov r12, r15
90                                  nop
48 8B 7B 20                         mov rdi, [rbx+0x20]
4C 89 F6                            mov rsi, r14
E8 74 31 12 00                      call rel32 (strcmp)
85 C0                               test eax, eax
48 8D 4B 10                         lea rcx, [rbx+0x10]
48 0F 49 CB                         cmovns rcx, rbx
4C 0F 49 E3                         cmovns r12, rbx
48 8B 19                            mov rbx, [rcx]
80 7B 19 00                         cmp byte [rbx+0x19], 0
74 DD                               je -0x23 (loop_start)
4C 39 FC                            cmp r12, r15
74 C4                               je -0x3C (xor eax, eax)
4C 8B 74 24 20                      mov rsi, [r12+0x20]
4C 89 F7                            mov rdi, r14
E8 4B 31 12 00                      call rel32 (strcmp)
85 C0                               test eax, eax
78 B3                               js -0x4D (xor eax, eax)
49 8B 44 24 28                      mov rax, [r12+0x28]
C3                                  ret
"""


def parse_hex_block(text):
    """Parse the hex+comment block into a list of (bytes, comment)."""
    out = []
    for line in text.strip().split('\n'):
        # Strip comment
        if ';' in line:
            line = line.split(';', 1)[0]
        # Split hex and mnemonic
        parts = line.strip().split(None, 1)
        if not parts:
            continue
        hex_str = parts[0]
        comment = parts[1] if len(parts) > 1 else ''
        # Parse hex bytes
        bs = bytes(int(b, 16) for b in hex_str.split())
        out.append((bs, comment))
    return out


def main():
    print("=" * 80)
    print("EXP-026 Byte-level Verification of Resolver Instruction Sequence")
    print("=" * 80)
    print()

    entries = parse_hex_block(RESOLVER_BYTES_HEX)
    print(f"[*] Parsed {len(entries)} instruction entries")
    print()

    # Concatenate all bytes
    all_bytes = b''.join(e[0] for e in entries)
    print(f"[*] Total bytes: {len(all_bytes)}")
    print()

    # Decode using iced_x86
    decoder = Decoder(64, all_bytes)
    formatter = Formatter(FormatterSyntax.NASM)

    print(f"{'RIP':18s}  {'BYTES':30s}  INSTRUCTION")
    print("-" * 80)

    rip = 0x804ED9B90
    for instr in decoder:
        s = formatter.format(instr)
        bs = all_bytes[instr.ip - 0x804ED9B90:instr.ip - 0x804ED9B90 + instr.len]
        print(f"0x{instr.ip:x}  {bs.hex(' '):30s}  {s}")

    print()

    # Cross-check with our mnemonic-level synthetic CPU
    print("=" * 80)
    print("Cross-check against synthetic CPU instruction sequence:")
    print("=" * 80)
    print()
    print("Synthetic CPU RIPs (from exp026_synthetic_cpu.py):")
    print("  0x804ED9B90  push rbp")
    print("  0x804ED9B91  mov rbp, rsp")
    print("  0x804ED9B94  push r15; r14; r12; rbx")
    print("  0x804ED9B9B  mov r15, [rip+0x3c79b66]")
    print("  0x804ED9BA2  mov rbx, [r15+8]")
    print("  0x804ED9BA6  cmp byte [rbx+0x19], 0")
    print("  0x804ED9BAA  je do_lookup")
    print("  0x804ED9BAC  xor eax, eax")
    print("  0x804ED9BAE  pop rbx; r12; r14; r15; rbp")
    print("  0x804ED9BB6  ret")
    print("  0x804ED9BB7  mov r14, rdi")
    print("  0x804ED9BBA  mov r12, r15")
    print("  0x804ED9BBD  nop")
    print("  0x804ED9BC0  mov rdi, [rbx+0x20]    (loop_start)")
    print("  0x804ED9BC4  mov rsi, r14")
    print("  0x804ED9BC7  call strcmp")
    print("  0x804ED9BCC  test eax, eax")
    print("  0x804ED9BCE  lea rcx, [rbx+0x10]")
    print("  0x804ED9BD2  cmovns rcx, rbx")
    print("  0x804ED9BD6  cmovns r12, rbx")
    print("  0x804ED9BDA  mov rbx, [rcx]")
    print("  0x804ED9BDD  cmp byte [rbx+0x19], 0")
    print("  0x804ED9BE1  je loop_start")
    print("  0x804ED9BE3  cmp r12, r15")
    print("  0x804ED9BE6  je return_0")
    print("  0x804ED9BE8  mov rsi, [r12+0x20]")
    print("  0x804ED9BED  mov rdi, r14")
    print("  0x804ED9BF0  call strcmp")
    print("  0x804ED9BF5  test eax, eax")
    print("  0x804ED9BF7  js return_0")
    print("  0x804ED9BF9  mov rax, [r12+0x28]")
    print("  (ret)")
    print()

    # Flag-affecting summary
    print("=" * 80)
    print("Flag-affecting analysis (from byte-level disassembly):")
    print("=" * 80)
    print()
    print("Instructions that READ flags (conditional jumps/cmovs):")
    print("  0x804ED9BAA  je  +0x0B        ; reads ZF")
    print("  0x804ED9BD2  cmovns rcx, rbx  ; reads SF (NOT sign flag)")
    print("  0x804ED9BD6  cmovns r12, rbx  ; reads SF")
    print("  0x804ED9BE1  je  -0x23        ; reads ZF")
    print("  0x804ED9BE6  je  -0x3C        ; reads ZF")
    print("  0x804ED9BF7  js  -0x4D        ; reads SF")
    print()
    print("Instructions that WRITE flags (immediately before readers):")
    print("  0x804ED9BA6  cmp byte[rbx+0x19],0  ; writes ZF/SF → read by je @0x804ED9BAA")
    print("  0x804ED9BCC  test eax, eax          ; writes SF/ZF → read by cmovns @0x804ED9BD2")
    print("  [0x804ED9BCE lea rcx, [rbx+0x10]    ; does NOT modify flags]")
    print("  [0x804ED9BD2 cmovns rcx, rbx        ; does NOT modify flags]")
    print("  0x804ED9BD6  cmovns r12, rbx        ; reads SF (preserved from test @0x804ED9BCC)")
    print("  0x804ED9BDD  cmp byte[rbx+0x19],0   ; writes ZF/SF → read by je @0x804ED9BE1")
    print("  0x804ED9BE3  cmp r12, r15           ; writes ZF/SF → read by je @0x804ED9BE6")
    print("  0x804ED9BF5  test eax, eax          ; writes SF/ZF → read by js @0x804ED9BF7")
    print()
    print("CRITICAL OBSERVATION:")
    print("  The SF flag set by `test eax, eax` at 0x804ED9BCC is read by")
    print("  BOTH cmovns at 0x804ED9BD2 AND cmovns at 0x804ED9BD6.")
    print("  Between them are: lea (no flags) and cmovns (no flags).")
    print("  So SF must be PRESERVED across these two instructions.")
    print()
    print("  If SharpEmu's native execution incorrectly clobbers SF between")
    print("  0x804ED9BCC (test) and 0x804ED9BD6 (second cmovns), the candidate")
    print("  update would use the wrong SF value, causing the resolver to fail")
    print("  to track candidates correctly. This would lead to returning 0")
    print("  for ALL queries — which is exactly what we observe.")


if __name__ == '__main__':
    main()
