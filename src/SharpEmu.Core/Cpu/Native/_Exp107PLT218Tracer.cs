// EXP-107: Runtime tracer to verify whether PLT 218 (0x804FC3720),
// 0x804FA84E0 (trampoline), and 0x804F88AD0 (callback invoker) are ever reached.
//
// Purpose:
// Verify the reviewer's concern: if 0x804F88AD0 is never called at runtime,
// then PLT 218 never runs, and the real gap is upstream (nothing calls
// 0x804F88AD0), not "PLT 218 runs but does the wrong thing."
//
// Hypothesis A: PLT 218 IS reached but doesn't invoke the callback.
// Hypothesis B: PLT 218 is NEVER reached — the gap is upstream.
//
// This tracer patches:
//   1. 0x804F88AD0 (callback invoker) — does it ever execute?
//   2. 0x804FA84E0 (trampoline to PLT 218) — does it ever execute?
//   3. 0x804FC3720 (PLT 218 itself) — does it ever execute?
//
// If all three have 0 hits: Hypothesis B confirmed — the gap is upstream.
// If any has hits: trace args/return to determine what happens.
//
// Register offsets (verified against DirectExecutionBackend.cs:800):
//   CTX_RAX = 120, CTX_RBX = 128, CTX_RCX = 136, CTX_RDX = 144
//   CTX_RSI = 168, CTX_RDI = 176, CTX_RSP = 152
//   CTX_R12 = 216, CTX_R14 = 232, CTX_R15 = 240, CTX_RIP = 248
//
// EXP-107 introduced this tracer.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-107: PLT 218 reachability tracer =====

    // The 3 addresses to trace
    private static readonly ulong[] Exp107_Addresses = new ulong[]
    {
        0x804F88AD0,  // callback invoker
        0x804FA84E0,  // trampoline to PLT 218
        0x804FC3720,  // PLT 218 itself
    };

    private static readonly string[] Exp107_Labels = new string[]
    {
        "0x804F88AD0 (callback invoker)",
        "0x804FA84E0 (trampoline to PLT 218)",
        "0x804FC3720 (PLT 218)",
    };

    private byte[] _exp107OrigBytes = new byte[3];
    private bool[] _exp107Patched = new bool[3];

    // EXP-107: Patches all 3 addresses with INT3 to check reachability.
    // Hypothesis A: PLT 218 reached but doesn't invoke callback.
    // Hypothesis B: PLT 218 NEVER reached — gap is upstream.
    private unsafe void Exp107PatchPLT218Tracers()
    {
        for (int i = 0; i < Exp107_Addresses.Length; i++)
        {
            if (_exp107Patched[i]) continue;
            try
            {
                ulong addr = Exp107_Addresses[i];
                var ptr = (byte*)addr;
                uint fl = 0;
                if (VirtualProtect((void*)addr, 16u, 64u, &fl))
                {
                    _exp107OrigBytes[i] = ptr[0];
                    ptr[0] = 0xCC;
                    _exp107Patched[i] = true;
                    Console.Error.WriteLine(
                        $"[EXP107-PATCH] [{i}] {Exp107_Labels[i]} patched (byte=0x{_exp107OrigBytes[i]:X2})");
                    VirtualProtect((void*)addr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)addr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP107] [{i}] patch failed: {ex.Message}");
            }
        }
    }

    // EXP-107: Handles INT3 from any of the 3 addresses.
    // If hit: logs which address was reached, dumps args (rdi, rsi, rdx, rcx).
    // If NOT hit (0 hits at stall): confirms Hypothesis B — gap is upstream.
    private unsafe bool Exp107TryHandleInt3(void* contextRecord, ulong rip)
    {
        int idx = -1;
        for (int i = 0; i < Exp107_Addresses.Length; i++)
        {
            if (_exp107Patched[i] && rip - 1 == Exp107_Addresses[i])
            {
                idx = i;
                break;
            }
        }
        if (idx < 0) return false;

        // Correct register offsets (verified against DirectExecutionBackend.cs:800)
        ulong rdi = ReadCtxU64(contextRecord, 176); // CTX_RDI
        ulong rsi = ReadCtxU64(contextRecord, 168); // CTX_RSI
        ulong rdx = ReadCtxU64(contextRecord, 144); // CTX_RDX
        ulong rcx = ReadCtxU64(contextRecord, 136); // CTX_RCX
        ulong rsp = ReadCtxU64(contextRecord, 152); // CTX_RSP
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP107-HIT] *** {Exp107_Labels[idx]} REACHED! *** " +
            $"caller=0x{callerRip:X16} tid={Environment.CurrentManagedThreadId}");
        Console.Error.WriteLine(
            $"  rdi=0x{rdi:X16} rsi=0x{rsi:X16} rdx=0x{rdx:X16} rcx=0x{rcx:X16}");
        Console.Error.Flush();

        // Restore
        ulong addr = Exp107_Addresses[idx];
        var ptr = (byte*)addr;
        uint fl = 0;
        if (VirtualProtect((void*)addr, 16u, 64u, &fl))
        {
            ptr[0] = _exp107OrigBytes[idx];
            VirtualProtect((void*)addr, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)addr, 16u);
        }
        _exp107Patched[idx] = false;

        WriteCtxU64(contextRecord, 248, addr);
        return true;
    }
}
