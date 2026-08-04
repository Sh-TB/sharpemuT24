#!/usr/bin/env python3
"""Debug: test the flag-clear sequence."""
import ctypes, ctypes.util, struct

libc = ctypes.CDLL(ctypes.util.find_library('c'))
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

# Test the exact flag-clear sequence + test eax + capture
TEST = bytes([
    # mov eax, edi
    0x89, 0xF8,
    # === FLAG CLEAR SEQUENCE ===
    0x9C,                               # pushfq
    0x58,                               # pop rax
    0x48, 0x25, 0x2A, 0xF7, 0xFF, 0xFF, # and rax, 0xFFFFF72A (sign-ext)
    0x50,                               # push rax
    0x9D,                               # popfq
    # === test eax, eax ===
    0x85, 0xC0,
    # === Capture flags ===
    0x9C,
    0x58,
    0x48, 0x89, 0x06,                   # mov [rsi], rax
    0xC3,
])

addr = libc.mmap(None, 0x1000, 1|2|4, 0x22, -1, 0)
ctypes.memmove(addr, TEST, len(TEST))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)
print("Disassembly:")
for insn in md.disasm(TEST, 0x1000):
    print(f"  0x{insn.address:x}: {insn.bytes.hex():24s}  {insn.mnemonic} {insn.op_str}")
print()

FUNC_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_void_p)
func = FUNC_TYPE(addr)

for eax in [0x00000006, 0x00000000, 0xFFFFFFFF, 0x80000000]:
    out_buf = ctypes.create_string_buffer(8)
    func(eax, ctypes.addressof(out_buf))
    efl = struct.unpack('<Q', out_buf.raw)[0]
    sf = (efl >> 7) & 1
    zf = (efl >> 6) & 1
    print(f"eax=0x{eax:08X}: eflags=0x{efl:08x} SF={sf} ZF={zf}  (expected: SF={1 if eax & 0x80000000 else 0}, ZF={1 if eax==0 else 0})")

libc.munmap(addr, 0x1000)
