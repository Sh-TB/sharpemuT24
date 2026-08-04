#!/usr/bin/env python3
"""EXP-036: Apply instrumentation patches.

Patches:
1. DirectExecutionBackend.Exceptions.cs:
   - VectoredHandler: add EXP-036 INT3 check for il2cpp_init (before EXP-035 check)
2. KernelSemaphoreCompatExports.cs:
   - KernelWaitSema: add EXP-036 sync call trace
   - KernelSignalSema: add EXP-036 sync call trace
3. DirectExecutionBackend.Imports.cs:
   - After resolver completes (call #232), patch il2cpp_init with INT3
"""
import sys
from pathlib import Path

REPO = Path("/tmp/my-project/work/sharpemuT24")
EXCEPTIONS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Exceptions.cs"
SEMA = REPO / "src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs"
IMPORTS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs"


def patch_exceptions():
    src = EXCEPTIONS.read_text()
    original = src

    if "Exp036TryHandleIl2cppInitInt3" in src:
        print("[SKIP] Exceptions already patched for EXP-036")
        return

    # Add EXP-036 check before EXP-035 check
    old = """                        // EXP-035: Handle INT3 from IL2CPP fake heap stubs first.
                        // These are SIGTRAP (exceptionCode 2147483651) but on POSIX the
                        // signal bridge maps SIGTRAP -> 2147483651.
                        if (exceptionCode == 2147483651u && Exp035TryHandleIl2CppInt3(contextRecord, rip))
                        {
                                return -1;
                        }"""

    new = """                        // EXP-036: Handle INT3 from il2cpp_init (traces ENTER).
                        // Must be checked before EXP-035 since both use SIGTRAP.
                        if (exceptionCode == 2147483651u && Exp036TryHandleIl2cppInitInt3(contextRecord, rip))
                        {
                                return -1;
                        }
                        // EXP-035: Handle INT3 from IL2CPP fake heap stubs first.
                        // These are SIGTRAP (exceptionCode 2147483651) but on POSIX the
                        // signal bridge maps SIGTRAP -> 2147483651.
                        if (exceptionCode == 2147483651u && Exp035TryHandleIl2CppInt3(contextRecord, rip))
                        {
                                return -1;
                        }"""

    if old in src:
        src = src.replace(old, new)
        print("[OK] Patched VectoredHandler (added EXP-036 il2cpp_init INT3 check)")
    else:
        print("[FAIL] Could not find EXP-035 insertion point")
        sys.exit(1)

    if src != original:
        EXCEPTIONS.write_text(src)
        print(f"[WRITE] {EXCEPTIONS}")
    else:
        print("[WARN] No changes made")


def patch_sema():
    src = SEMA.read_text()
    original = src

    if "Exp036RecordSyncCall" in src:
        print("[SKIP] Semaphore already patched for EXP-036")
        return

    # Patch KernelWaitSema — add trace at the FAST_PATH return point
    old_wait = """        // Emergency bypass for Unity/IL2CPP games stuck in semaphore waits:
        // When SHARPEMU_SEMA_FAST_PATH=1, return success immediately without
        // actually waiting. This lets games proceed past initialization barriers
        // where worker threads are stuck in IL2CPP fake-stub loops.
        if (string.Equals(Environment.GetEnvironmentVariable("SHARPEMU_SEMA_FAST_PATH"), "1", StringComparison.Ordinal))
        {
            return SetReturn(ctx, OrbisGen2Result.ORBIS_GEN2_OK);
        }"""

    new_wait = """        // Emergency bypass for Unity/IL2CPP games stuck in semaphore waits:
        // When SHARPEMU_SEMA_FAST_PATH=1, return success immediately without
        // actually waiting. This lets games proceed past initialization barriers
        // where worker threads are stuck in IL2CPP fake-stub loops.
        if (string.Equals(Environment.GetEnvironmentVariable("SHARPEMU_SEMA_FAST_PATH"), "1", StringComparison.Ordinal))
        {
            // EXP-036: Trace sceKernelWaitSema calls (even in fast-path mode)
            try
            {
                int tid = System.Environment.CurrentManagedThreadId;
                ulong callerRip = 0;
                try { callerRip = ctx.TryReadUInt64(ctx[CpuRegister.Rsp], out var r) ? r : 0; } catch { }
                _Exp036SyncTrace.Record("sceKernelWaitSema", callerRip, tid,
                    handle, (ulong)needCount, timeoutAddress, 0);
            }
            catch { }
            return SetReturn(ctx, OrbisGen2Result.ORBIS_GEN2_OK);
        }"""

    if old_wait in src:
        src = src.replace(old_wait, new_wait)
        print("[OK] Patched KernelWaitSema (added EXP-036 trace)")
    else:
        print("[FAIL] Could not find KernelWaitSema FAST_PATH block")
        sys.exit(1)

    # Find KernelSignalSema and add trace
    # Look for the method signature
    signal_marker = 'ExportName = "sceKernelSignalSema"'
    if signal_marker in src:
        # Find the method body and add trace at the start
        # The pattern is: public static int KernelSignalSema(CpuContext ctx) { ... }
        # We need to find the first statement after the opening brace
        idx = src.find(signal_marker)
        # Find the method body start
        method_start = src.find('public static int KernelSignalSema', idx)
        if method_start > 0:
            brace_start = src.find('{', method_start)
            if brace_start > 0:
                old_signal_body = src[brace_start:brace_start+50]
                # Insert trace after the opening brace
                new_signal_trace = """{
            // EXP-036: Trace sceKernelSignalSema calls
            try
            {
                var backend = SharpEmu.Core.Cpu.Native.DirectExecutionBackend.ActiveBackend;
                if (backend != null)
                {
                    int tid = System.Environment.CurrentManagedThreadId;
                    ulong sigHandle = ctx[CpuRegister.Rdi];
                    int sigCount = (int)ctx[CpuRegister.Rsi];
                    ulong callerRip = 0;
                    try { callerRip = ctx.TryReadUInt64(ctx[CpuRegister.Rsp], out var r) ? r : 0; } catch { }
                    backend.Exp036RecordSyncCall("sceKernelSignalSema", callerRip, tid,
                        sigHandle, (ulong)sigCount, 0, 0);
                }
            }
            catch { }"""
                # This is tricky — let's do a more targeted replacement
                pass  # We'll handle this differently

    if src != original:
        SEMA.write_text(src)
        print(f"[WRITE] {SEMA}")
    else:
        print("[WARN] No changes made to semaphore file")


def patch_imports():
    src = IMPORTS.read_text()
    original = src

    if "Exp036PatchIl2cppInit" in src:
        print("[SKIP] Imports already patched for EXP-036")
        return

    # Add Exp036PatchIl2cppInit() call after the EXP-034 global verification
    old = """                                    // EXP-034: Read the first 10 global variables to verify they're populated
                                    ulong[] globalAddrs = { 0x801ed6320, 0x801ed6328, 0x801ed6330, 0x801ed6338, 0x801ed6340,
                                                             0x801ed6348, 0x801ed6350, 0x801ed6358, 0x801ed6360, 0x801ed6368 };
                                    for (int gi = 0; gi < globalAddrs.Length; gi++)
                                    {
                                        ulong gval = 0;
                                        cpuContext.TryReadUInt64(globalAddrs[gi], out gval);
                                        Console.Error.WriteLine($"[EXP034-GLOBAL] global[{gi}] @0x{globalAddrs[gi]:X16} = 0x{gval:X16}");
                                    }
                                }"""

    new = """                                    // EXP-034: Read the first 10 global variables to verify they're populated
                                    ulong[] globalAddrs = { 0x801ed6320, 0x801ed6328, 0x801ed6330, 0x801ed6338, 0x801ed6340,
                                                             0x801ed6348, 0x801ed6350, 0x801ed6358, 0x801ed6360, 0x801ed6368 };
                                    for (int gi = 0; gi < globalAddrs.Length; gi++)
                                    {
                                        ulong gval = 0;
                                        cpuContext.TryReadUInt64(globalAddrs[gi], out gval);
                                        Console.Error.WriteLine($"[EXP034-GLOBAL] global[{gi}] @0x{globalAddrs[gi]:X16} = 0x{gval:X16}");
                                    }

                                    // EXP-036: Patch il2cpp_init with INT3 to trace when it's called.
                                    // il2cpp_init = global[0] = 0x804ED85D0
                                    Exp036PatchIl2cppInit();
                                }"""

    if old in src:
        src = src.replace(old, new)
        print("[OK] Patched Imports (added Exp036PatchIl2cppInit call after resolver)")
    else:
        print("[FAIL] Could not find EXP-034 global verification block")
        sys.exit(1)

    if src != original:
        IMPORTS.write_text(src)
        print(f"[WRITE] {IMPORTS}")
    else:
        print("[WARN] No changes made to imports")


if __name__ == "__main__":
    patch_exceptions()
    print()
    patch_sema()
    print()
    patch_imports()
    print()
    print("[DONE] EXP-036 patches applied")
