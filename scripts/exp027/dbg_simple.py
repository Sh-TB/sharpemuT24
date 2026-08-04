#!/usr/bin/env python3
"""Debug: simplest possible test of mmap+ctypes function call."""
import ctypes, ctypes.util, struct

libc = ctypes.CDLL(ctypes.util.find_library('c'))
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

PROT_RWX = 1 | 2 | 4
MAP_PRIVATE_ANON = 0x22

# Simple function: takes (rdi=ptr, rsi=ptr), copies 24 bytes from rdi to rsi, returns 0x1234
SIMPLE = bytes([
    # mov rax, [rdi]
    0x48, 0x8B, 0x07,
    # mov [rsi], rax
    0x48, 0x89, 0x06,
    # mov rax, [rdi+8]
    0x48, 0x8B, 0x47, 0x08,
    # mov [rsi+8], rax
    0x48, 0x89, 0x46, 0x08,
    # mov rax, [rdi+16]
    0x48, 0x8B, 0x47, 0x10,
    # mov [rsi+16], rax
    0x48, 0x89, 0x46, 0x10,
    # mov eax, 0x1234
    0xB8, 0x34, 0x12, 0x00, 0x00,
    # ret
    0xC3,
])

addr = libc.mmap(None, 0x1000, PROT_RWX, MAP_PRIVATE_ANON, -1, 0)
print(f"mmap addr: 0x{addr:x}")
ctypes.memmove(addr, SIMPLE, len(SIMPLE))

INPUT = struct.Struct('<QQQ')  # 24 bytes
input_data = INPUT.pack(0xAAAA1111BBBB2222, 0xCCCC3333DDDD4444, 0xEEEE5555FFFF6666)
output_data = bytes(24)

in_buf = ctypes.create_string_buffer(input_data)
out_buf = ctypes.create_string_buffer(24)

FUNC_TYPE = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p)
func = FUNC_TYPE(addr)

ret = func(ctypes.addressof(in_buf), ctypes.addressof(out_buf))
print(f"ret: 0x{ret:x}")
print(f"out_buf raw: {out_buf.raw.hex()}")
got = INPUT.unpack(out_buf.raw)
print(f"unpacked: {['0x%x' % v for v in got]}")
print(f"expected: ['0xaaaa1111bbbb2222', '0xcccc3333dddd4444', '0xeeee5555ffff6666']")

libc.munmap(addr, 0x1000)
