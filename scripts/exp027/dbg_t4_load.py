#!/usr/bin/env python3
"""Debug T4: test the exact T4 function step by step."""
import ctypes, ctypes.util, struct

libc = ctypes.CDLL(ctypes.util.find_library('c'))
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

# Test 1: just load inputs and write them back unchanged
TEST_LOAD = bytes([
    0x53,                               # push rbx
    0x41, 0x54,                         # push r12
    0x8B, 0x47, 0x00,                   # mov eax, [rdi+0]
    0x48, 0x8B, 0x5F, 0x08,             # mov rbx, [rdi+8]
    0x4C, 0x8B, 0x67, 0x10,             # mov r12, [rdi+16]
    # Write outputs
    0x48, 0x89, 0x0E,                   # mov [rsi+0], rcx   <-- rcx is uninitialized!
    0x4C, 0x89, 0x66, 0x08,             # mov [rsi+8], r12
    0x48, 0x89, 0x46, 0x10,             # mov [rsi+16], rax
    0x41, 0x5C,                         # pop r12
    0x5B,                               # pop rbx
    0xC3,                               # ret
])

# Wait — the bug is that I'm writing rcx (uninitialized) to [rsi+0].
# Let me write rbx instead, to verify rbx was loaded correctly.
TEST_LOAD = bytes([
    0x53,                               # push rbx
    0x41, 0x54,                         # push r12
    0x8B, 0x47, 0x00,                   # mov eax, [rdi+0]
    0x48, 0x8B, 0x5F, 0x08,             # mov rbx, [rdi+8]
    0x4C, 0x8B, 0x67, 0x10,             # mov r12, [rdi+16]
    # Write rbx to [rsi+0], r12 to [rsi+8], eax(zext to rax) to [rsi+16]
    0x48, 0x89, 0x1E,                   # mov [rsi+0], rbx
    0x4C, 0x89, 0x66, 0x08,             # mov [rsi+8], r12
    0x48, 0x89, 0x46, 0x10,             # mov [rsi+16], rax    (rax = zext(eax))
    0x41, 0x5C,                         # pop r12
    0x5B,                               # pop rbx
    0xC3,                               # ret
])

addr = libc.mmap(None, 0x1000, 1|2|4, 0x22, -1, 0)
ctypes.memmove(addr, TEST_LOAD, len(TEST_LOAD))

INPUT = struct.Struct('<IxxxxQQ')
OUTPUT = struct.Struct('<QQQ')

eax_in = 0x00000006
rbx_in = 0x2000025600
r12_in = 0x2000003F20

in_buf = ctypes.create_string_buffer(INPUT.pack(eax_in, rbx_in, r12_in))
out_buf = ctypes.create_string_buffer(24)

FUNC_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
func = FUNC_TYPE(addr)
func(ctypes.addressof(in_buf), ctypes.addressof(out_buf))

rcx_out, r12_out, rax_out = OUTPUT.unpack(out_buf.raw)
print(f"Input:  eax=0x{eax_in:08x} rbx=0x{rbx_in:016x} r12=0x{r12_in:016x}")
print(f"Output: rbx=0x{rcx_out:016x} r12=0x{r12_out:016x} rax=0x{rax_out:016x}")
print(f"Expected: rbx=0x{rbx_in:016x} r12=0x{r12_in:016x} rax=0x{eax_in:016x}")
print(f"Match: rbx={rcx_out==rbx_in}, r12={r12_out==r12_in}, rax={rax_out==eax_in}")

libc.munmap(addr, 0x1000)
