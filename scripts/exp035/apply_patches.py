#!/usr/bin/env python3
"""EXP-035: Apply instrumentation patches to SharpEmuT24 source files.

Patches:
1. DirectExecutionBackend.Imports.cs:
   - InitIl2CppHeap: install vtable tracer stub (INT3) in all vtable slots
   - InitIl2CppHeap: install return-fake-object INT3 stub
   - GenerateIl2CppStub: emit INT3 (1 byte) instead of mov rax, imm64; ret
2. DirectExecutionBackend.Exceptions.cs:
   - VectoredHandler: route SIGTRAP (exception 2147483651) to Exp035TryHandleIl2CppInt3 first
   - TryRecoverNullExecuteFault: log caller RIP + last IL2CPP call via Exp035LogNullExecuteFault
"""
import re
import sys
from pathlib import Path

REPO = Path("/tmp/my-project/work/sharpemuT24")
IMPORTS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs"
EXCEPTIONS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Exceptions.cs"


def patch_imports():
    src = IMPORTS.read_text()
    original = src

    # Patch 1a: InitIl2CppHeap - install vtable tracer stub
    old_init = """        private unsafe bool InitIl2CppHeap()
        {
                var heap = VirtualAlloc(null, (nuint)Il2CppHeapSize, 0x3000u, 0x40u);
                if (heap == null) return false;
                _il2cppHeap = (ulong)heap;
                var ptr = (byte*)heap;
                var returnZeroStubAddr = _il2cppHeap + Il2CppReturnZeroStubOffset;
                ptr[Il2CppReturnZeroStubOffset + 0] = 0x31; // xor eax, eax
                ptr[Il2CppReturnZeroStubOffset + 1] = 0xC0;
                ptr[Il2CppReturnZeroStubOffset + 2] = 0xC3; // ret
                for (int i = 0; i < 512; i++)
                        Marshal.WriteInt64((nint)(ptr + Il2CppVtableBase + (ulong)i * 8), (long)returnZeroStubAddr);
                InstallFakeObject(Il2CppDomainOffset);
                InstallFakeObject(Il2CppThreadOffset);
                InstallFakeObject(Il2CppClassOffset);
                InstallFakeObject(Il2CppImageOffset);
                InstallFakeObject(Il2CppAssemblyOffset);
                InstallFakeObject(Il2CppObjectOffset);
                InstallFakeObject(Il2CppTypeOffset);
                Console.Error.WriteLine($"[IL2CPP][INFO] Fake runtime heap at 0x{_il2cppHeap:X16}");
                return true;
        }"""

    new_init = """        private unsafe bool InitIl2CppHeap()
        {
                var heap = VirtualAlloc(null, (nuint)Il2CppHeapSize, 0x3000u, 0x40u);
                if (heap == null) return false;
                _il2cppHeap = (ulong)heap;
                var ptr = (byte*)heap;
                var returnZeroStubAddr = _il2cppHeap + Il2CppReturnZeroStubOffset;
                ptr[Il2CppReturnZeroStubOffset + 0] = 0x31; // xor eax, eax
                ptr[Il2CppReturnZeroStubOffset + 1] = 0xC0;
                ptr[Il2CppReturnZeroStubOffset + 2] = 0xC3; // ret
                // EXP-035: Install vtable tracer stub (INT3) and point all vtable slots at it
                // so virtual method calls on fake objects are traced.
                var vtableTracerStubAddr = Exp035InstallVtableTracerStub();
                for (int i = 0; i < 512; i++)
                        Marshal.WriteInt64((nint)(ptr + Il2CppVtableBase + (ulong)i * 8), (long)vtableTracerStubAddr);
                InstallFakeObject(Il2CppDomainOffset);
                InstallFakeObject(Il2CppThreadOffset);
                InstallFakeObject(Il2CppClassOffset);
                InstallFakeObject(Il2CppImageOffset);
                InstallFakeObject(Il2CppAssemblyOffset);
                InstallFakeObject(Il2CppObjectOffset);
                InstallFakeObject(Il2CppTypeOffset);
                // EXP-035: Install INT3-based return-fake-object stub
                Exp035WriteReturnFakeObjectInt3Stub();
                Console.Error.WriteLine($"[IL2CPP][INFO] Fake runtime heap at 0x{_il2cppHeap:X16} (EXP-035 tracing enabled)");
                return true;
        }"""

    if old_init in src:
        src = src.replace(old_init, new_init)
        print("[OK] Patched InitIl2CppHeap")
    else:
        print("[FAIL] Could not find InitIl2CppHeap to patch")
        sys.exit(1)

    # Patch 1b: GenerateIl2CppStub - emit INT3 instead of mov rax, imm64; ret
    old_stub = """        private unsafe ulong GenerateIl2CppStub(string name)
        {
                ulong returnValue = DecideIl2CppReturnValue(name);
                var stubOffset = Il2CppStubsBase + (ulong)_il2cppStubCount * (ulong)Il2CppStubSize;
                if (stubOffset + Il2CppStubSize > Il2CppStubsBase + Il2CppStubsMax)
                        return _il2cppHeap + Il2CppReturnZeroStubOffset;
                _il2cppStubCount++;
                var ptr = (byte*)_il2cppHeap + stubOffset;
                ptr[0] = 0x48; ptr[1] = 0xB8; // mov rax, imm64
                Marshal.WriteInt64((nint)(ptr + 2), (long)returnValue);
                ptr[10] = 0xC3; // ret

                // Log IL2CPP stubs that return NULL (potential crash source)
                if (returnValue == 0 && Environment.GetEnvironmentVariable("SHARPEMU_LOG_IL2CPP_NULL") == "1")
                {
                        Console.Error.WriteLine(
                                $"[IL2CPP_NULL] name='{name}' stub=0x{_il2cppHeap + stubOffset:X16} returns=NULL");
                }
                else if (returnValue != 0 && returnValue != _il2cppHeap + Il2CppReturnZeroStubOffset && Environment.GetEnvironmentVariable("SHARPEMU_LOG_IL2CPP_STUBS") == "1")
                {
                        Console.Error.WriteLine(
                                $"[IL2CPP_STUB] name='{name}' returns=0x{returnValue:X16}");
                }

                return _il2cppHeap + stubOffset;
        }"""

    new_stub = """        private unsafe ulong GenerateIl2CppStub(string name)
        {
                ulong returnValue = DecideIl2CppReturnValue(name);
                var stubOffset = Il2CppStubsBase + (ulong)_il2cppStubCount * (ulong)Il2CppStubSize;
                if (stubOffset + Il2CppStubSize > Il2CppStubsBase + Il2CppStubsMax)
                        return _il2cppHeap + Il2CppReturnZeroStubOffset;
                _il2cppStubCount++;
                var stubAddr = _il2cppHeap + stubOffset;
                // EXP-035: Emit INT3-only stub. The SIGTRAP handler in
                // Exp035TryHandleIl2CppInt3 will log the call, set RAX=returnValue,
                // pop the return address, and resume at the caller.
                Exp035WriteInt3Stub(stubAddr, name, returnValue);

                // Log IL2CPP stubs that return NULL (potential crash source)
                if (returnValue == 0 && Environment.GetEnvironmentVariable("SHARPEMU_LOG_IL2CPP_NULL") == "1")
                {
                        Console.Error.WriteLine(
                                $"[IL2CPP_NULL] name='{name}' stub=0x{stubAddr:X16} returns=NULL");
                }
                else if (returnValue != 0 && returnValue != _il2cppHeap + Il2CppReturnZeroStubOffset && Environment.GetEnvironmentVariable("SHARPEMU_LOG_IL2CPP_STUBS") == "1")
                {
                        Console.Error.WriteLine(
                                $"[IL2CPP_STUB] name='{name}' returns=0x{returnValue:X16}");
                }

                return stubAddr;
        }"""

    if old_stub in src:
        src = src.replace(old_stub, new_stub)
        print("[OK] Patched GenerateIl2CppStub")
    else:
        print("[FAIL] Could not find GenerateIl2CppStub to patch")
        sys.exit(1)

    # Patch 1c: GetReturnFakeObjectStub - use INT3 stub instead of mov rax, imm64; ret
    # Find the GetReturnFakeObjectStub method and replace its body
    old_ret_fake = """        // Generic "return fake object" stub — returns Il2CppObject address
        // Used by il2cpp_resolve_icall so resolved icalls don't return NULL
        private unsafe ulong GetReturnFakeObjectStub()
        {
                const ulong ReturnFakeObjectStubOffset = 0x1800;
                var ptr = (byte*)_il2cppHeap;
                // Check if already installed
                if (ptr[ReturnFakeObjectStubOffset] == 0x48 && ptr[ReturnFakeObjectStubOffset + 1] == 0xB8)
                        return _il2cppHeap + ReturnFakeObjectStubOffset;
                // Install: mov rax, <Il2CppObjectOffset>; ret
                ptr[ReturnFakeObjectStubOffset] = 0x48;"""

    if old_ret_fake in src:
        # We need to replace the whole method. Let me find the full method body.
        # The method ends with "return _il2cppHeap + ReturnFakeObjectStubOffset; }"
        # Let's do a regex replacement.
        pattern = r"""        // Generic "return fake object" stub — returns Il2CppObject address
        // Used by il2cpp_resolve_icall so resolved icalls don't return NULL
        private unsafe ulong GetReturnFakeObjectStub\(\)
        \{
                const ulong ReturnFakeObjectStubOffset = 0x1800;
                var ptr = \(byte\*\)_il2cppHeap;
                // Check if already installed
                if \(ptr\[ReturnFakeObjectStubOffset\] == 0x48 && ptr\[ReturnFakeObjectStubOffset \+ 1\] == 0xB8\)
                        return _il2cppHeap \+ ReturnFakeObjectStubOffset;
                // Install: mov rax, <Il2CppObjectOffset>; ret
                ptr\[ReturnFakeObjectStubOffset\] = 0x48;
                ptr\[ReturnFakeObjectStubOffset \+ 1\] = 0xB8;
                Marshal\.WriteInt64\(\(nint\)\(ptr \+ ReturnFakeObjectStubOffset \+ 2\), \(long\)\(_il2cppHeap \+ Il2CppObjectOffset\)\);
                ptr\[ReturnFakeObjectStubOffset \+ 10\] = 0xC3;
                return _il2cppHeap \+ ReturnFakeObjectStubOffset;
        \}"""

        new_ret_fake = """        // Generic "return fake object" stub — returns Il2CppObject address
        // Used by il2cpp_resolve_icall so resolved icalls don't return NULL
        // EXP-035: Now uses INT3 stub (installed in InitIl2CppHeap via Exp035WriteReturnFakeObjectInt3Stub).
        private unsafe ulong GetReturnFakeObjectStub()
        {
                const ulong ReturnFakeObjectStubOffset = 0x1800;
                if (_il2cppHeap == 0) return 0;
                // INT3 stub is already installed by InitIl2CppHeap
                return _il2cppHeap + ReturnFakeObjectStubOffset;
        }"""

        src_new = re.sub(pattern, new_ret_fake, src)
        if src_new != src:
            src = src_new
            print("[OK] Patched GetReturnFakeObjectStub")
        else:
            print("[FAIL] Regex replacement for GetReturnFakeObjectStub failed")
            sys.exit(1)
    else:
        print("[INFO] GetReturnFakeObjectStub original not found (maybe already patched?)")

    if src != original:
        IMPORTS.write_text(src)
        print(f"[WRITE] {IMPORTS}")
    else:
        print("[WARN] No changes made to Imports file")


def patch_exceptions():
    src = EXCEPTIONS.read_text()
    original = src

    # Patch 2a: Add EXP-035 INT3 handler check at the start of VectoredHandler's recovery chain.
    # We insert it right after the rip/rsp reads and before TryRecoverGuestInt41.
    old_block = """                        ulong rip = ReadCtxU64(contextRecord, 248);
                        ulong rsp = ReadCtxU64(contextRecord, 152);
                        if (TryRecoverGuestInt41(exceptionCode, contextRecord, rip))
                        {
                                return -1;
                        }"""

    new_block = """                        ulong rip = ReadCtxU64(contextRecord, 248);
                        ulong rsp = ReadCtxU64(contextRecord, 152);
                        // EXP-035: Handle INT3 from IL2CPP fake heap stubs first.
                        // These are SIGTRAP (exceptionCode 2147483651) but on POSIX the
                        // signal bridge maps SIGTRAP -> 2147483651.
                        if (exceptionCode == 2147483651u && Exp035TryHandleIl2CppInt3(contextRecord, rip))
                        {
                                return -1;
                        }
                        if (TryRecoverGuestInt41(exceptionCode, contextRecord, rip))
                        {
                                return -1;
                        }"""

    if old_block in src:
        src = src.replace(old_block, new_block)
        print("[OK] Patched VectoredHandler (added EXP-035 INT3 check)")
    else:
        print("[FAIL] Could not find VectoredHandler insertion point")
        sys.exit(1)

    # Patch 2b: TryRecoverNullExecuteFault - add EXP-035 logging
    old_null = """        private unsafe bool TryRecoverNullExecuteFault(void* contextRecord)
        {
                var returnZeroStub = GetNullCallRecoveryStub();
                if (returnZeroStub == 0) return false;
                if (Interlocked.Increment(ref _nullExecuteRecoveries) > 100000) return false;
                WriteCtxU64(contextRecord, 248, returnZeroStub);
                WriteCtxU64(contextRecord, 120, 0);
                if (_nullExecuteRecoveries <= 5 || _nullExecuteRecoveries % 100 == 0)
                        Console.Error.WriteLine($"[LOADER][WARN] NULL execute fault recovered #{_nullExecuteRecoveries}");
                return true;
        }"""

    new_null = """        private unsafe bool TryRecoverNullExecuteFault(void* contextRecord)
        {
                var returnZeroStub = GetNullCallRecoveryStub();
                if (returnZeroStub == 0) return false;
                if (Interlocked.Increment(ref _nullExecuteRecoveries) > 100000) return false;
                WriteCtxU64(contextRecord, 248, returnZeroStub);
                WriteCtxU64(contextRecord, 120, 0);
                if (_nullExecuteRecoveries <= 5 || _nullExecuteRecoveries % 100 == 0)
                        Console.Error.WriteLine($"[LOADER][WARN] NULL execute fault recovered #{_nullExecuteRecoveries}");
                // EXP-035: Enhanced logging — caller RIP, last IL2CPP call, thread
                if (_nullExecuteRecoveries <= 20 || _nullExecuteRecoveries % 1000 == 0)
                        Exp035LogNullExecuteFault(contextRecord, _nullExecuteRecoveries);
                return true;
        }"""

    if old_null in src:
        src = src.replace(old_null, new_null)
        print("[OK] Patched TryRecoverNullExecuteFault (added EXP-035 logging)")
    else:
        print("[FAIL] Could not find TryRecoverNullExecuteFault to patch")
        sys.exit(1)

    if src != original:
        EXCEPTIONS.write_text(src)
        print(f"[WRITE] {EXCEPTIONS}")
    else:
        print("[WARN] No changes made to Exceptions file")


if __name__ == "__main__":
    # Check if Imports patches already applied
    src_imports = IMPORTS.read_text()
    if "Exp035InstallVtableTracerStub" in src_imports:
        print("[SKIP] Imports already patched (EXP-035 markers found)")
    else:
        patch_imports()
    print()
    # Check if Exceptions patches already applied
    src_exc = EXCEPTIONS.read_text()
    if "Exp035TryHandleIl2CppInt3" in src_exc:
        print("[SKIP] Exceptions already patched (EXP-035 markers found)")
    else:
        patch_exceptions()
    print()
    print("[DONE] EXP-035 patches applied")
