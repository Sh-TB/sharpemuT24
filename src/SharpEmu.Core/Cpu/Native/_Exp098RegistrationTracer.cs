// EXP-098: Trace the registration function 0x804FA20E0 and the once-init 0x804F51020.
//
// 0x804F51020 is the WORKING once-init (registers 7 callbacks, called from real_init @ 0x804F04C70)
// 0x804FA20E0 is the DEAD registration function (registers 0x804FA1FE0 via 0x804F889D0)
//   - 3 callers, one at 0x804F0590B (inside real_init, offset +0xD6B)
//
// This tracer patches BOTH with INT3 to determine:
//   1. Is 0x804F51020 reached? (expected: YES — the 7 working globals are populated)
//   2. Is 0x804FA20E0 reached? (expected: NO — the dead-code functions are never registered)

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-098: Registration path tracer =====

    private const ulong Exp098_WorkingInitAddr = 0x804F51020;
    private const ulong Exp098_DeadRegAddr = 0x804FA20E0;

    private byte _exp098WorkingInitOriginalByte;
    private bool _exp098WorkingInitPatched;
    private byte _exp098DeadRegOriginalByte;
    private bool _exp098DeadRegPatched;

    private unsafe void Exp098PatchRegistrationTracers()
    {
        // Patch 0x804F51020 (working once-init)
        if (!_exp098WorkingInitPatched)
        {
            try
            {
                var ptr = (byte*)Exp098_WorkingInitAddr;
                uint fl = 0;
                if (VirtualProtect((void*)Exp098_WorkingInitAddr, 16u, 64u, &fl))
                {
                    _exp098WorkingInitOriginalByte = ptr[0];
                    ptr[0] = 0xCC;
                    _exp098WorkingInitPatched = true;
                    Console.Error.WriteLine(
                        $"[EXP098-PATCH] working_init at 0x{Exp098_WorkingInitAddr:X16} patched (byte=0x{_exp098WorkingInitOriginalByte:X2})");
                    VirtualProtect((void*)Exp098_WorkingInitAddr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp098_WorkingInitAddr, 16u);
                }
            }
            catch (Exception ex) { Console.Error.WriteLine($"[EXP098] working_init patch failed: {ex.Message}"); }
        }

        // Patch 0x804FA20E0 (dead registration function)
        if (!_exp098DeadRegPatched)
        {
            try
            {
                var ptr = (byte*)Exp098_DeadRegAddr;
                uint fl = 0;
                if (VirtualProtect((void*)Exp098_DeadRegAddr, 16u, 64u, &fl))
                {
                    _exp098DeadRegOriginalByte = ptr[0];
                    ptr[0] = 0xCC;
                    _exp098DeadRegPatched = true;
                    Console.Error.WriteLine(
                        $"[EXP098-PATCH] dead_reg at 0x{Exp098_DeadRegAddr:X16} patched (byte=0x{_exp098DeadRegOriginalByte:X2})");
                    VirtualProtect((void*)Exp098_DeadRegAddr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp098_DeadRegAddr, 16u);
                }
            }
            catch (Exception ex) { Console.Error.WriteLine($"[EXP098] dead_reg patch failed: {ex.Message}"); }
        }
    }

    private unsafe bool Exp098TryHandleWorkingInitInt3(void* contextRecord, ulong rip)
    {
        if (!_exp098WorkingInitPatched) return false;
        if (rip - 1 != Exp098_WorkingInitAddr) return false;

        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP098-WORKING-INIT-ENTER] caller=0x{callerRip:X16} tid={Environment.CurrentManagedThreadId}");
        Console.Error.Flush();

        // Restore
        var ptr = (byte*)Exp098_WorkingInitAddr;
        uint fl = 0;
        if (VirtualProtect((void*)Exp098_WorkingInitAddr, 16u, 64u, &fl))
        {
            ptr[0] = _exp098WorkingInitOriginalByte;
            VirtualProtect((void*)Exp098_WorkingInitAddr, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp098_WorkingInitAddr, 16u);
        }
        _exp098WorkingInitPatched = false;
        WriteCtxU64(contextRecord, 248, Exp098_WorkingInitAddr);
        return true;
    }

    private unsafe bool Exp098TryHandleDeadRegInt3(void* contextRecord, ulong rip)
    {
        if (!_exp098DeadRegPatched) return false;
        if (rip - 1 != Exp098_DeadRegAddr) return false;

        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }
        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong rsi = ReadCtxU64(contextRecord, 168);
        ulong rdx = ReadCtxU64(contextRecord, 144);

        Console.Error.WriteLine(
            $"[EXP098-DEAD-REG-ENTER] *** 0x804FA20E0 REACHED! *** caller=0x{callerRip:X16} tid={Environment.CurrentManagedThreadId}");
        Console.Error.WriteLine(
            $"  rdi=0x{rdi:X16} rsi=0x{rsi:X16} rdx=0x{rdx:X16}");
        Console.Error.Flush();

        // Restore
        var ptr = (byte*)Exp098_DeadRegAddr;
        uint fl = 0;
        if (VirtualProtect((void*)Exp098_DeadRegAddr, 16u, 64u, &fl))
        {
            ptr[0] = _exp098DeadRegOriginalByte;
            VirtualProtect((void*)Exp098_DeadRegAddr, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp098_DeadRegAddr, 16u);
        }
        _exp098DeadRegPatched = false;
        WriteCtxU64(contextRecord, 248, Exp098_DeadRegAddr);
        return true;
    }
}
