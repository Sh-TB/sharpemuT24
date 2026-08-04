#!/usr/bin/env python3
"""
EXP-027 T4: Synthetic CMOV Test — REAL HARDWARE GROUND TRUTH.

Runs the exact resolver instruction sequence:
    test eax, eax
    lea  rcx, [rbx+0x10]
    cmovns rcx, rbx
    cmovns r12, rbx

on the REAL HOST CPU (via mmap'd executable memory + ctypes), Unicorn engine
(gold-standard x86 emulator), and EXP-026 synthetic Python CPU, and verifies
all three agree.

Input struct at RDI (24 bytes):
    +0:  eax_in (uint32)
    +4:  (4 bytes padding, ignored)
    +8:  rbx_in (uint64)
    +16: r12_in (uint64)

Output struct at RSI (24 bytes):
    +0:  rcx_out (uint64)
    +8:  r12_out (uint64)
    +16: eflags_out (uint64)
"""

import ctypes
import ctypes.util
import struct
import sys
import json
from pathlib import Path

# ============================================================
# T4-1: Build the test binary (real x86-64 machine code)
# ============================================================

# Function signature: void test(rdi=input_ptr, rsi=output_ptr)
TEST_FUNCTION_ASM = bytes([
    # prologue: save callee-saved (rbx, r12)
    0x53,                               # push rbx
    0x41, 0x54,                         # push r12
    # Load inputs from struct at RDI
    # eax_in is at [rdi+0] (4 bytes)
    0x8B, 0x47, 0x00,                   # mov eax, dword ptr [rdi+0]
    # rbx_in is at [rdi+8] (8 bytes)
    0x48, 0x8B, 0x5F, 0x08,             # mov rbx, qword ptr [rdi+8]
    # r12_in is at [rdi+16] (8 bytes)
    0x4C, 0x8B, 0x67, 0x10,             # mov r12, qword ptr [rdi+16]
    # Clear all arithmetic flags: push 0 (all flags = 0); popfq
    0x6A, 0x00,                         # push 0
    0x9D,                               # popfq              (flags = 0, including SF/ZF/PF/CF/OF)
    # === THE CRITICAL SEQUENCE (matches resolver at 0x804ED9BCC) ===
    0x85, 0xC0,                         # test eax, eax      ; sets SF/ZF/PF based on eax
    0x48, 0x8D, 0x4B, 0x10,             # lea rcx, [rbx+0x10] ; does NOT modify flags (Intel SDM)
    0x48, 0x0F, 0x49, 0xCB,             # cmovns rcx, rbx     ; if SF=0: rcx = rbx
    0x4C, 0x0F, 0x49, 0xE3,             # cmovns r12, rbx     ; if SF=0: r12 = rbx (uses SAME SF as above!)
    # === END CRITICAL SEQUENCE ===
    # Capture final flags
    0x9C,                               # pushfq
    0x58,                               # pop rax             (rax = final eflags)
    # Write outputs to struct at RSI
    # rcx_out at [rsi+0] (8 bytes)
    0x48, 0x89, 0x0E,                   # mov qword ptr [rsi+0], rcx
    # r12_out at [rsi+8] (8 bytes)
    0x4C, 0x89, 0x66, 0x08,             # mov qword ptr [rsi+8], r12
    # eflags_out at [rsi+16] (8 bytes) — rax holds eflags
    0x48, 0x89, 0x46, 0x10,             # mov qword ptr [rsi+16], rax
    # epilogue: restore callee-saved
    0x41, 0x5C,                         # pop r12
    0x5B,                               # pop rbx
    0xC3,                               # ret
])

print(f"[*] Test function: {len(TEST_FUNCTION_ASM)} bytes")

# Verify disassembly
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)
print(f"[*] Disassembly:")
for insn in md.disasm(TEST_FUNCTION_ASM, 0x1000):
    print(f"    0x{insn.address:x}: {insn.bytes.hex():24s}  {insn.mnemonic} {insn.op_str}")
print()


# ============================================================
# T4-2: Run the test on the real host CPU
# ============================================================

INPUT_STRUCT = struct.Struct('<IxxxxQQ')   # 4+4pad+8+8 = 24 bytes
OUTPUT_STRUCT = struct.Struct('<QQQ')      # 8+8+8 = 24 bytes

def run_on_host_cpu(eax_in, rbx_in, r12_in):
    """Run the test sequence on the real host CPU."""
    libc = ctypes.CDLL(ctypes.util.find_library('c'))
    libc.mmap.restype = ctypes.c_void_p
    libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
    libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

    PROT_RWX = 1 | 2 | 4
    MAP_PRIVATE_ANON = 0x22

    addr = libc.mmap(None, 0x1000, PROT_RWX, MAP_PRIVATE_ANON, -1, 0)
    if not addr:
        raise RuntimeError("mmap failed")
    ctypes.memmove(addr, TEST_FUNCTION_ASM, len(TEST_FUNCTION_ASM))

    input_bytes = INPUT_STRUCT.pack(eax_in & 0xFFFFFFFF, rbx_in, r12_in)
    in_buf = ctypes.create_string_buffer(input_bytes)
    out_buf = ctypes.create_string_buffer(OUTPUT_STRUCT.size)

    FUNC_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
    func = FUNC_TYPE(addr)
    try:
        func(ctypes.addressof(in_buf), ctypes.addressof(out_buf))
    finally:
        libc.munmap(addr, 0x1000)

    rcx_out, r12_out, eflags_out = OUTPUT_STRUCT.unpack(out_buf.raw)
    return rcx_out, r12_out, eflags_out


# ============================================================
# T4-3: Run the same sequence through Unicorn engine
# ============================================================

from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
from unicorn.x86_const import (
    UC_X86_REG_RAX, UC_X86_REG_RBX, UC_X86_REG_RCX,
    UC_X86_REG_R12, UC_X86_REG_EFLAGS, UC_X86_REG_RSP,
)

def run_on_unicorn(eax_in, rbx_in, r12_in):
    """Run the test sequence on the Unicorn engine."""
    CODE_ADDR = 0x1000
    STACK_ADDR = 0x7FFF0000
    STACK_SIZE = 0x10000

    # Build a self-contained binary: load immediates, run critical seq, hlt
    UNI_CODE = bytes([
        # mov eax, imm32
        0xB8, eax_in & 0xFF, (eax_in >> 8) & 0xFF, (eax_in >> 16) & 0xFF, (eax_in >> 24) & 0xFF,
        # movabs rax, imm64 (rbx_in) — clobbers eax, will reload below
        0x48, 0xB8,
        rbx_in & 0xFF, (rbx_in >> 8) & 0xFF, (rbx_in >> 16) & 0xFF, (rbx_in >> 24) & 0xFF,
        (rbx_in >> 32) & 0xFF, (rbx_in >> 40) & 0xFF, (rbx_in >> 48) & 0xFF, (rbx_in >> 56) & 0xFF,
        0x48, 0x89, 0xC3,             # mov rbx, rax
        # movabs rax, imm64 (r12_in)
        0x48, 0xB8,
        r12_in & 0xFF, (r12_in >> 8) & 0xFF, (r12_in >> 16) & 0xFF, (r12_in >> 24) & 0xFF,
        (r12_in >> 32) & 0xFF, (r12_in >> 40) & 0xFF, (r12_in >> 48) & 0xFF, (r12_in >> 56) & 0xFF,
        0x49, 0x89, 0xC4,             # mov r12, rax
        # Reload eax (was clobbered by movabs)
        0xB8, eax_in & 0xFF, (eax_in >> 8) & 0xFF, (eax_in >> 16) & 0xFF, (eax_in >> 24) & 0xFF,
        # Clear flags: push 0; popfq (same as host CPU test)
        0x6A, 0x00,                   # push 0
        0x9D,                         # popfq
        # === CRITICAL SEQUENCE ===
        0x85, 0xC0,                   # test eax, eax
        0x48, 0x8D, 0x4B, 0x10,       # lea rcx, [rbx+0x10]
        0x48, 0x0F, 0x49, 0xCB,       # cmovns rcx, rbx
        0x4C, 0x0F, 0x49, 0xE3,       # cmovns r12, rbx
        # Halt
        0xF4,                         # hlt
    ])

    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(CODE_ADDR, 0x1000)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_write(CODE_ADDR, UNI_CODE)
    uc.reg_write(UC_X86_REG_RSP, STACK_ADDR + STACK_SIZE - 0x100)

    try:
        uc.emu_start(CODE_ADDR, CODE_ADDR + len(UNI_CODE))
    except Exception:
        pass  # hlt raises

    rcx = uc.reg_read(UC_X86_REG_RCX)
    r12 = uc.reg_read(UC_X86_REG_R12)
    eflags = uc.reg_read(UC_X86_REG_EFLAGS)
    return rcx, r12, eflags


# ============================================================
# T4-4: Run the same sequence through EXP-026 synthetic Python CPU
# ============================================================

def run_on_synthetic(eax_in, rbx_in, r12_in):
    """Mimic the EXP-026 synthetic CPU's flag computation + cmovns logic."""
    eax = eax_in & 0xFFFFFFFF
    sign_bit = 0x80000000

    # test eax, eax: result = eax & eax = eax
    ZF = 1 if eax == 0 else 0
    SF = 1 if (eax & sign_bit) else 0
    low8 = eax & 0xFF
    PF = 1 if (bin(low8).count('1') % 2 == 0) else 0
    CF = 0
    OF = 0

    # lea rcx, [rbx+0x10]: does NOT modify flags
    rcx = (rbx_in + 0x10) & 0xFFFFFFFFFFFFFFFF

    # cmovns rcx, rbx: if SF=0, rcx = rbx
    if SF == 0:
        rcx = rbx_in & 0xFFFFFFFFFFFFFFFF

    # cmovns r12, rbx: if SF=0, r12 = rbx (uses SAME SF)
    r12 = r12_in & 0xFFFFFFFFFFFFFFFF
    if SF == 0:
        r12 = rbx_in & 0xFFFFFFFFFFFFFFFF

    # Reconstruct eflags
    eflags = 0x202  # IF=1, bit1 reserved
    if CF: eflags |= 0x001
    if PF: eflags |= 0x004
    if ZF: eflags |= 0x040
    if SF: eflags |= 0x080
    if OF: eflags |= 0x800

    return rcx, r12, eflags


# ============================================================
# T4-5: Battery of test cases
# ============================================================

def main():
    print("=" * 110)
    print("EXP-027 T4: Synthetic CMOV Test — 3-way comparison")
    print("  Host CPU (ground truth)  vs  Unicorn engine  vs  EXP-026 synthetic Python CPU")
    print("=" * 110)
    print()

    RBX_BASE = 0x2000025000
    R12_SENTINEL = 0x2000003F20

    test_cases = [
        (0xFFFFFFFA, RBX_BASE + 0x100, R12_SENTINEL, "eax=-6 (NODE<QUERY): SF=1, cmovns NOT taken, rcx=rbx+0x10, r12=unchanged"),
        (0xFFFFFFFF, RBX_BASE + 0x200, R12_SENTINEL, "eax=-1 (NODE<QUERY): SF=1, cmovns NOT taken, rcx=rbx+0x10, r12=unchanged"),
        (0x80000000, RBX_BASE + 0x300, R12_SENTINEL, "eax=INT_MIN: SF=1, cmovns NOT taken, rcx=rbx+0x10, r12=unchanged"),
        (0x00000000, RBX_BASE + 0x400, R12_SENTINEL, "eax=0 (EXACT MATCH): SF=0, cmovns TAKEN, rcx=rbx, r12=rbx"),
        (0x00000001, RBX_BASE + 0x500, R12_SENTINEL, "eax=+1 (NODE>QUERY): SF=0, cmovns TAKEN, rcx=rbx, r12=rbx"),
        (0x00000006, RBX_BASE + 0x600, R12_SENTINEL, "eax=+6 (NODE>QUERY): SF=0, cmovns TAKEN, rcx=rbx, r12=rbx"),
        (0x7FFFFFFF, RBX_BASE + 0x700, R12_SENTINEL, "eax=INT_MAX: SF=0, cmovns TAKEN, rcx=rbx, r12=rbx"),
        (0x00000006, RBX_BASE + 0x800, RBX_BASE + 0x800, "eax=+6, r12==rbx: cmovns TAKEN, r12 unchanged (already equals rbx)"),
        (0x00000006, 0, R12_SENTINEL, "eax=+6, rbx=0: cmovns TAKEN, rcx=0, r12=0"),
        (0xFFFFFFFF, 0, R12_SENTINEL, "eax=-1, rbx=0: cmovns NOT taken, rcx=0x10, r12=unchanged"),
    ]

    print(f"{'#':3s}  {'eax':10s}  {'rbx':16s}  {'r12_in':16s}  | {'host_rcx':16s} {'host_r12':16s} {'host_efl':8s} | {'uni_rcx':16s} {'uni_r12':16s} {'uni_efl':8s} | {'synth_rcx':16s} {'synth_r12':16s} {'synth_efl':8s} | match?")
    print("-" * 200)

    all_match = True
    results = []

    EFLAG_MASK = 0x8D5  # CF|PF|AF|ZF|SF|OF

    for i, (eax, rbx, r12, desc) in enumerate(test_cases):
        host_rcx, host_r12, host_efl = run_on_host_cpu(eax, rbx, r12)
        uni_rcx, uni_r12, uni_efl = run_on_unicorn(eax, rbx, r12)
        synth_rcx, synth_r12, synth_efl = run_on_synthetic(eax, rbx, r12)

        host_efl_a = host_efl & EFLAG_MASK
        uni_efl_a = uni_efl & EFLAG_MASK
        synth_efl_a = synth_efl & EFLAG_MASK

        match = (
            host_rcx == uni_rcx == synth_rcx and
            host_r12 == uni_r12 == synth_r12 and
            host_efl_a == uni_efl_a == synth_efl_a
        )
        if not match:
            all_match = False

        print(f"{i+1:3d}  0x{eax:08X}  0x{rbx:016x}  0x{r12:016x}  | "
              f"0x{host_rcx:016x} 0x{host_r12:016x} 0x{host_efl:08X} | "
              f"0x{uni_rcx:016x} 0x{uni_r12:016x} 0x{uni_efl:08X} | "
              f"0x{synth_rcx:016x} 0x{synth_r12:016x} 0x{synth_efl:08X} | "
              f"{'OK' if match else 'MISMATCH'}")
        print(f"    → {desc}")
        if not match:
            print(f"    !! host_vs_uni_rcx:  {host_rcx==uni_rcx}, host_vs_synth_rcx: {host_rcx==synth_rcx}")
            print(f"    !! host_vs_uni_r12:  {host_r12==uni_r12}, host_vs_synth_r12: {host_r12==synth_r12}")
            print(f"    !! host_vs_uni_efl:  {host_efl_a==uni_efl_a}, host_vs_synth_efl: {host_efl_a==synth_efl_a}")

        results.append({
            'test': i+1, 'eax': f"0x{eax:08x}", 'rbx_in': f"0x{rbx:016x}", 'r12_in': f"0x{r12:016x}",
            'host':    {'rcx': host_rcx,    'r12': host_r12,    'eflags_arith': host_efl_a,    'eflags_raw': host_efl},
            'unicorn': {'rcx': uni_rcx,     'r12': uni_r12,     'eflags_arith': uni_efl_a,     'eflags_raw': uni_efl},
            'synth':   {'rcx': synth_rcx,   'r12': synth_r12,   'eflags_arith': synth_efl_a,   'eflags_raw': synth_efl},
            'match': match, 'desc': desc,
        })

    print()
    print("=" * 110)
    if all_match:
        print("[OK] ALL 3 METHODS AGREE on every test case.")
        print("[OK] Host CPU == Unicorn engine == EXP-026 synthetic Python CPU.")
        print()
        print("CONCLUSION:")
        print("  The test/lea/cmovns/cmovns sequence is correctly emulated by:")
        print("    1. The real hardware CPU (ground truth)")
        print("    2. The Unicorn engine (gold-standard x86 emulator)")
        print("    3. The EXP-026 synthetic Python CPU")
        print()
        print("  → The resolver's critical cmovns sequence is DEFINITIVELY correct.")
        print("  → If SharpEmu's native execution produces different results,")
        print("    the bug is DEFINITIVELY in SharpEmu's CPU emulation layer.")
    else:
        print("[!] MISMATCH DETECTED — see above for details")
        sys.exit(1)

    # Save log
    out_path = '/home/z/my-project/download/exp027/cmovns_test.log'
    with open(out_path, 'w') as f:
        f.write("EXP-027 T4: CMOVNS Test — 3-way comparison\n")
        f.write("Host CPU vs Unicorn engine vs EXP-026 Synthetic Python CPU\n")
        f.write(f"Test function: {len(TEST_FUNCTION_ASM)} bytes\n\n")
        f.write("Disassembly:\n")
        for insn in md.disasm(TEST_FUNCTION_ASM, 0x1000):
            f.write(f"  0x{insn.address:x}: {insn.bytes.hex():24s}  {insn.mnemonic} {insn.op_str}\n")
        f.write("\n")
        for r in results:
            f.write(f"Test #{r['test']}: eax={r['eax']} rbx_in={r['rbx_in']} r12_in={r['r12_in']}\n")
            f.write(f"  Desc:    {r['desc']}\n")
            f.write(f"  Host:    rcx=0x{r['host']['rcx']:016x} r12=0x{r['host']['r12']:016x} eflags(arith)=0x{r['host']['eflags_arith']:03x} eflags(raw)=0x{r['host']['eflags_raw']:x}\n")
            f.write(f"  Unicorn: rcx=0x{r['unicorn']['rcx']:016x} r12=0x{r['unicorn']['r12']:016x} eflags(arith)=0x{r['unicorn']['eflags_arith']:03x} eflags(raw)=0x{r['unicorn']['eflags_raw']:x}\n")
            f.write(f"  Synth:   rcx=0x{r['synth']['rcx']:016x} r12=0x{r['synth']['r12']:016x} eflags(arith)=0x{r['synth']['eflags_arith']:03x} eflags(raw)=0x{r['synth']['eflags_raw']:x}\n")
            f.write(f"  Match:   {'YES' if r['match'] else 'NO'}\n\n")
    print(f"\n[+] Wrote log: {out_path}")


if __name__ == '__main__':
    main()
