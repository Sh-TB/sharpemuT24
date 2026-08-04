#!/usr/bin/env python3
"""Debug T4: isolate the bug — is it the flag-clearing or the cmovns?"""
import ctypes, ctypes.util, struct

libc = ctypes.CDLL(ctypes.util.find_library('c'))
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

# Test A: just load inputs, run test eax,eax, capture flags. No lea/cmovns.
TEST_A = bytes([
    0x53, 0x41, 0x54,                   # push rbx; push r12
    0x8B, 0x47, 0x00,                   # mov eax, [rdi+0]
    0x48, 0x8B, 0x5F, 0x08,             # mov rbx, [rdi+8]
    0x4C, 0x8B, 0x67, 0x10,             # mov r12, [rdi+16]
    # Clear flags: pushfq; pop rax; and rax,0xFFFFF72A; push rax; popfq
    0x9C,                               # pushfq
    0x58,                               # pop rax
    0x48, 0x25, 0x2A, 0xF7, 0xFF, 0xFF, # and rax, 0xFFFFF72A (sign-ext to 0xFFFFFFFFFFFFF72A)
    0x50,                               # push rax
    0x9D,                               # popfq
    # Run test eax, eax
    0x85, 0xC0,                         # test eax, eax
    # Capture flags
    0x9C,                               # pushfq
    0x48, 0x8B, 0x04, 0x24,             # mov rax, [rsp]
    0x48, 0x83, 0xC4, 0x08,             # add rsp, 8
    # Write outputs: [rsi+0]=rbx, [rsi+8]=r12, [rsi+16]=rax(flags)
    0x48, 0x89, 0x1E,                   # mov [rsi], rbx
    0x4C, 0x89, 0x66, 0x08,             # mov [rsi+8], r12
    0x48, 0x89, 0x46, 0x10,             # mov [rsi+16], rax
    0x41, 0x5C, 0x5B, 0xC3,             # pop r12; pop rbx; ret
])

# Test B: same as A, but add lea + cmovns after test
TEST_B = bytes([
    0x53, 0x41, 0x54,                   # push rbx; push r12
    0x8B, 0x47, 0x00,                   # mov eax, [rdi+0]
    0x48, 0x8B, 0x5F, 0x08,             # mov rbx, [rdi+8]
    0x4C, 0x8B, 0x67, 0x10,             # mov r12, [rdi+16]
    0x9C, 0x58,                         # pushfq; pop rax
    0x48, 0x25, 0x2A, 0xF7, 0xFF, 0xFF, # and rax, 0xFFFFF72A
    0x50, 0x9D,                         # push rax; popfq
    0x85, 0xC0,                         # test eax, eax
    0x48, 0x8D, 0x4B, 0x10,             # lea rcx, [rbx+0x10]
    0x48, 0x0F, 0x49, 0xCB,             # cmovns rcx, rbx
    0x4C, 0x0F, 0x49, 0xE3,             # cmovns r12, rbx
    0x9C,                               # pushfq
    0x48, 0x8B, 0x04, 0x24,             # mov rax, [rsp]
    0x48, 0x83, 0xC4, 0x08,             # add rsp, 8
    0x48, 0x89, 0x0E,                   # mov [rsi], rcx        <-- now write rcx (not rbx)
    0x4C, 0x89, 0x66, 0x08,             # mov [rsi+8], r12
    0x48, 0x89, 0x46, 0x10,             # mov [rsi+16], rax
    0x41, 0x5C, 0x5B, 0xC3,
])

INPUT = struct.Struct('<IxxxxQQ')
OUTPUT = struct.Struct('<QQQ')

def run(code, eax, rbx, r12):
    addr = libc.mmap(None, 0x1000, 1|2|4, 0x22, -1, 0)
    ctypes.memmove(addr, code, len(code))
    in_buf = ctypes.create_string_buffer(INPUT.pack(eax, rbx, r12))
    out_buf = ctypes.create_string_buffer(24)
    FUNC_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
    func = FUNC_TYPE(addr)
    func(ctypes.addressof(in_buf), ctypes.addressof(out_buf))
    libc.munmap(addr, 0x1000)
    return OUTPUT.unpack(out_buf.raw)

# Test case: eax=+6 (positive, SF should be 0, cmovns should take)
eax = 0x00000006
rbx = 0x2000025600
r12_in = 0x2000003F20

print(f"Input: eax=0x{eax:08x} (+6, positive) rbx=0x{rbx:016x} r12=0x{r12_in:016x}")
print()

# Expected: SF=0 after test(+6), cmovns TAKEN → rcx=rbx, r12=rbx
print("Test A (just test eax,eax, no cmovns):")
rcx, r12_out, efl = run(TEST_A, eax, rbx, r12_in)
print(f"  rbx=0x{rcx:016x} (unchanged), r12=0x{r12_out:016x} (unchanged), eflags=0x{efl:08x}")
print(f"  eflags bits: CF={(efl>>0)&1} PF={(efl>>2)&1} AF={(efl>>4)&1} ZF={(efl>>6)&1} SF={(efl>>7)&1} OF={(efl>>11)&1}")
print(f"  Expected: SF=0 ZF=0 (eax=+6 is positive and nonzero)")
print()

print("Test B (full: test + lea + cmovns + cmovns):")
rcx, r12_out, efl = run(TEST_B, eax, rbx, r12_in)
print(f"  rcx=0x{rcx:016x}, r12=0x{r12_out:016x}, eflags=0x{efl:08x}")
print(f"  eflags bits: CF={(efl>>0)&1} PF={(efl>>2)&1} AF={(efl>>4)&1} ZF={(efl>>6)&1} SF={(efl>>7)&1} OF={(efl>>11)&1}")
print(f"  Expected: rcx=0x{rbx:016x} (cmovns taken), r12=0x{rbx:016x} (cmovns taken), SF=0")
print()

# Test case: eax=-1 (negative, SF should be 1, cmovns should NOT take)
eax = 0xFFFFFFFF
print(f"Input: eax=0x{eax:08x} (-1, negative) rbx=0x{rbx:016x} r12=0x{r12_in:016x}")
print()
print("Test A (just test eax,eax):")
rcx, r12_out, efl = run(TEST_A, eax, rbx, r12_in)
print(f"  rbx=0x{rcx:016x}, r12=0x{r12_out:016x}, eflags=0x{efl:08x}")
print(f"  eflags bits: CF={(efl>>0)&1} PF={(efl>>2)&1} AF={(efl>>4)&1} ZF={(efl>>6)&1} SF={(efl>>7)&1} OF={(efl>>11)&1}")
print(f"  Expected: SF=1 ZF=0 (eax=-1 is negative and nonzero)")
print()
print("Test B (full):")
rcx, r12_out, efl = run(TEST_B, eax, rbx, r12_in)
print(f"  rcx=0x{rcx:016x}, r12=0x{r12_out:016x}, eflags=0x{efl:08x}")
print(f"  eflags bits: CF={(efl>>0)&1} PF={(efl>>2)&1} AF={(efl>>4)&1} ZF={(efl>>6)&1} SF={(efl>>7)&1} OF={(efl>>11)&1}")
print(f"  Expected: rcx=0x{rbx+0x10:016x} (cmovns NOT taken, lea result), r12=0x{r12_in:016x} (cmovns NOT taken, unchanged), SF=1")
