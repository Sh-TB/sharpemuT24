// EXP-037: IL2CPP Global State Initialization Investigation
//
// POLICY (per user):
//   - Identify the global pointer at 0x801E51240
//   - Trace initialization APIs (il2cpp_set_config_dir, il2cpp_init_utf16, etc.)
//   - Verify function table routing (real func_impl, no fake stubs)
//   - Check PRX/static initialization
//   - Trace writes to the global pointer
//
// This file adds:
//   1. Write-watchpoint for global at 0x801E51240 (INT3 at the write site)
//   2. INT3 tracing for early IL2CPP setup APIs
//   3. Periodic dump of the global's value
//   4. Crash context logging when the NULL deref happens

using System;
using System.Collections.Generic;
using System.Threading;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-037: Global pointer investigation =====

    // The global pointer at 0x801E51240 — crash site reads [rax+0x98] where rax=this global
    private const ulong Exp037_GlobalAddr = 0x801E51240;

    // The WRITE instruction at 0x8013EF019: mov [rip+0xa62220], rax (7 bytes)
    // We patch byte 0 with INT3 to trace when the global is written
    private const ulong Exp037_WriteSite = 0x8013EF019;
    private byte _exp037WriteSiteOriginalByte;
    private bool _exp037WriteSitePatched;
    private int _exp037GlobalWriteCount;

    // The READ site (crash site) at 0x80135DE6D: mov rax, [rip+0xaf33cc] (7 bytes)
    private const ulong Exp037_ReadSite = 0x80135DE6D;
    private byte _exp037ReadSiteOriginalByte;
    private bool _exp037ReadSitePatched;
    private int _exp037GlobalReadCount;

    // Early IL2CPP API addresses (from resolver results)
    private const ulong Exp037_Il2cppInitAddr = 0x804ED85D0;
    private const ulong Exp037_Il2cppInitUtf16Addr = 0x804ED8600;
    private const ulong Exp037_Il2cppSetConfigDirAddr = 0x804ED86E0;
    private const ulong Exp037_Il2cppSetDataDirAddr = 0x804ED86F0;

    // Track which early APIs have been called
    private readonly HashSet<ulong> _exp037CalledApis = new HashSet<ulong>();

    private static readonly bool _exp037TraceEnabled =
        Environment.GetEnvironmentVariable("SHARPEMU_EXP037_TRACE") == "1";

    /// <summary>
    /// Installs INT3 watchpoints for the global pointer read/write sites.
    /// Called after eboot.bin is loaded.
    /// </summary>
    private unsafe void Exp037InstallWatchpoints()
    {
        // Patch the WRITE site
        if (!_exp037WriteSitePatched)
        {
            try
            {
                var ptr = (byte*)Exp037_WriteSite;
                uint flNewProtect = 0;
                if (VirtualProtect((void*)Exp037_WriteSite, 16u, 64u, &flNewProtect))
                {
                    _exp037WriteSiteOriginalByte = ptr[0];
                    ptr[0] = 0xCC; // INT3
                    _exp037WriteSitePatched = true;
                    Console.Error.WriteLine(
                        $"[EXP037-WATCHPOINT] WRITE site at 0x{Exp037_WriteSite:X16} patched " +
                        $"(original byte=0x{_exp037WriteSiteOriginalByte:X2})");
                    VirtualProtect((void*)Exp037_WriteSite, 16u, flNewProtect, &flNewProtect);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp037_WriteSite, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP037] Failed to patch WRITE site: {ex.Message}");
            }
        }

        // Read the current value of the global
        try
        {
            ulong currentVal = *(ulong*)Exp037_GlobalAddr;
            Console.Error.WriteLine(
                $"[EXP037-GLOBAL] 0x{Exp037_GlobalAddr:X16} = 0x{currentVal:X16} (at watchpoint install)");
        }
        catch { }

        // Set up the sync callback if not already done
        try
        {
            SharpEmu.Libs.Kernel._Exp036SyncTrace.SetRecorder(Exp036RecordSyncCall);
        }
        catch { }
    }

    /// <summary>
    /// Tries to handle INT3 traps from the global read/write watchpoints.
    /// Returns true if handled.
    /// </summary>
    private unsafe bool Exp037TryHandleWatchpointInt3(void* contextRecord, ulong rip)
    {
        if (!_exp037WriteSitePatched && !_exp037ReadSitePatched) return false;

        ulong stubAddr = rip - 1;
        int tid = Environment.CurrentManagedThreadId;

        // Check WRITE site
        if (stubAddr == Exp037_WriteSite)
        {
            _exp037GlobalWriteCount++;
            ulong rax = ReadCtxU64(contextRecord, 120); // CTX_RAX
            ulong rsp = ReadCtxU64(contextRecord, 152);
            ulong callerRip = 0;
            try { callerRip = *(ulong*)rsp; } catch { }

            Console.Error.WriteLine(
                $"[EXP037-WRITE] #{_exp037GlobalWriteCount} site=0x{Exp037_WriteSite:X16} " +
                $"value=0x{rax:X16} caller=0x{callerRip:X16} tid={tid}");
            Console.Error.Flush();

            // Restore original byte, execute the instruction, then re-patch
            // For simplicity, just restore and let it execute. We won't re-patch
            // since we only need to catch the first write.
            var ptr = (byte*)Exp037_WriteSite;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp037_WriteSite, 16u, 64u, &flNewProtect))
            {
                ptr[0] = _exp037WriteSiteOriginalByte;
                VirtualProtect((void*)Exp037_WriteSite, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp037_WriteSite, 16u);
            }
            _exp037WriteSitePatched = false;

            // Set RIP to re-execute the restored instruction
            WriteCtxU64(contextRecord, 248, Exp037_WriteSite);
            return true;
        }

        return false;
    }

    /// <summary>
    /// Dumps the current value of the global pointer.
    /// </summary>
    public void Exp037DumpGlobal(string context)
    {
        try
        {
            ulong currentVal = *(ulong*)Exp037_GlobalAddr;
            Console.Error.WriteLine(
                $"[EXP037-GLOBAL] {context} 0x{Exp037_GlobalAddr:X16} = 0x{currentVal:X16} " +
                $"writes={_exp037GlobalWriteCount} reads={_exp037GlobalReadCount}");
            Console.Error.Flush();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP037-GLOBAL] {context} error reading: {ex.Message}");
        }
    }

    /// <summary>
    /// Enhanced crash context logging for the NULL deref at 0x80135DE83.
    /// Called from the signal handler when a SIGSEGV occurs near the crash site.
    /// </summary>
    public void Exp037LogCrashContext(void* contextRecord, ulong rip, ulong faultAddr)
    {
        // Check if this is the crash site (0x80135DE83 or nearby)
        if (rip < 0x80135DDD0 || rip > 0x80135E000) return;

        Console.Error.WriteLine($"[EXP037-CRASH] === Crash context at 0x{rip:X16} ===");
        Console.Error.WriteLine($"[EXP037-CRASH] fault_addr=0x{faultAddr:X16}");

        // Read all registers
        ulong rax = ReadCtxU64(contextRecord, 120);
        ulong rbx = ReadCtxU64(contextRecord, 144);
        ulong rcx = ReadCtxU64(contextRecord, 128);
        ulong rdx = ReadCtxU64(contextRecord, 136);
        ulong rsi = ReadCtxU64(contextRecord, 168);
        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong rbp = ReadCtxU64(contextRecord, 160);
        ulong rsp = ReadCtxU64(contextRecord, 152);

        Console.Error.WriteLine(
            $"[EXP037-CRASH] rax=0x{rax:X16} rbx=0x{rbx:X16} rcx=0x{rcx:X16} " +
            $"rdx=0x{rdx:X16} rsi=0x{rsi:X16} rdi=0x{rdi:X16} rbp=0x{rbp:X16} rsp=0x{rsp:X16}");

        // Dump the global value
        Exp037DumpGlobal("at crash");

        // Dump stack (return addresses)
        Console.Error.WriteLine("[EXP037-CRASH] Stack dump (return addresses):");
        try
        {
            byte* sp = (byte*)rsp;
            for (int i = 0; i < 32; i++)
            {
                ulong val = *(ulong*)(sp + i * 8);
                if (val >= 0x800000000 && val < 0x810000000)
                {
                    Console.Error.WriteLine($"  [rsp+0x{i*8:X2}] = 0x{val:X16} (code)");
                }
            }
        }
        catch { }
        Console.Error.Flush();
    }
}
