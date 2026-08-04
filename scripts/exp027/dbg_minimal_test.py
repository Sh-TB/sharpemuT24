#!/usr/bin/env python3
"""Minimal test: does 'test eax, eax' set SF correctly?"""
import ctypes, ctypes.util, struct

libc = ctypes.CDLL(ctypes.util.find_library('c'))
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

# Minimal: load eax from rdi, test eax,eax, pushfq, write flags to [rsi]
MIN = bytes([
    # mov eax, edi   (eax = first int arg)
    0x89, 0xF8,
    # Clear flags first: push 0; popfq
    0x6A, 0x00,             # push 0
    0x9D,                   # popfq
    # test eax, eax
    0x85, 0xC0,
    # pushfq
    0x9C,
    # pop rax  (rax = eflags)
    0x58,
    # mov [rsi], rax
    0x48, 0x89, 0x06,
    # ret
    0xC3,
])

addr = libc.mmap(None, 0x1000, 1|2|4, 0x22, -1, 0)
ctypes.memmove(addr, MIN, len(MIN))

# Verify disassembly
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)
print("Disassembly:")
for insn in md.disasm(MIN, 0x1000):
    print(f"  0x{insn.address:x}: {insn.bytes.hex():20s}  {insn.mnemonic} {insn.op_str}")
print()

FUNC_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_void_p)
func = FUNC_TYPE(addr)

for eax in [0x00000006, 0x00000000, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF]:
    out_buf = ctypes.create_string_buffer(8)
    func(eax, ctypes.addressof(out_buf))
    efl = struct.unpack('<Q', out_buf.raw)[0]
    sf = (efl >> 7) & 1
    zf = (efl >> 6) & 1
    pf = (efl >> 2) & 1
    cf = (efl >> 0) & 1
    of = (efl >> 11) & 1
    print(f"eax=0x{eax:08X}: eflags=0x{efl:08x} CF={cf} PF={pf} ZF={zf} SF={sf} OF={of}")

libc.munmap(addr, 0x1000)
