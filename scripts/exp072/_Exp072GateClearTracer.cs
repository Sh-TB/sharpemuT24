// EXP-072: Diagnostic test — clear [rbx+0x108] at the gate check.
//
// EXP-070 found the gate: cmp byte [rbx+0x108], 0 + jne at 0x800AA0207.
// EXP-071 found [rbx+0x108] is a tagged pointer to an unresolved dependency.
//
// This tracer installs INT3 at 0x800AA0207. When hit, it:
//   1. Reads rbx from context
//   2. Writes 0x00 to [rbx+0x108] (clears the dependency pointer)
//   3. Logs the action
//   4. Restores original byte and lets execution continue
//
// Purpose: test if clearing the dependency allows SignalSema to fire.
// This is a DIAGNOSTIC patch, not a permanent fix.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    private const ulong Exp072_GateAddr = 0x800AA0207;
    private byte _exp072GateOriginalByte;
    private bool _exp072GatePatched;
    private int _exp072GateHitCount;

    private unsafe void Exp072PatchGateClear()
    {
        if (_exp072GatePatched) return;
        try
        {
            var ptr = (byte*)Exp072_GateAddr;
            uint fl = 0;
            if (VirtualProtect((void*)Exp072_GateAddr, 16u, 64u, &fl))
            {
                _exp072GateOriginalByte = ptr[0];
                ptr[0] = 0xCC; // INT3
                _exp072GatePatched = true;
                Console.Error.WriteLine(
                    $"[EXP072-PATCH] Gate at 0x{Exp072_GateAddr:X16} patched with INT3 " +
                    $"(original byte=0x{_exp072GateOriginalByte:X2})");
                VirtualProtect((void*)Exp072_GateAddr, 16u, fl, &fl);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp072_GateAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP072] Failed to patch gate: {ex.Message}");
        }
    }

    private unsafe bool Exp072TryHandleGateClearInt3(void* contextRecord, ulong rip)
    {
        if (!_exp072GatePatched) return false;
        if (rip - 1 != Exp072_GateAddr) return false;

        int hitNum = Interlocked.Increment(ref _exp072GateHitCount);
        int tid = Environment.CurrentManagedThreadId;

        // Read rbx
        ulong rbx = ReadCtxU64(contextRecord, 128); // CTX_RBX

        // Read current value at [rbx+0x108]
        ulong oldVal = 0;
        try { oldVal = *(ulong*)(rbx + 0x108); } catch { }

        // Clear [rbx+0x108] to 0 (remove dependency pointer)
        try { *(ulong*)(rbx + 0x108) = 0; } catch { }

        Console.Error.WriteLine(
            $"[EXP072-GATE-CLEAR] hit#{hitNum} tid={tid} rbx=0x{rbx:X16} " +
            $"[rbx+0x108] was=0x{oldVal:X16} → CLEARED to 0x0000000000000000");

        // Only patch once (restore original byte after first hit)
        if (hitNum == 1)
        {
            var ptr = (byte*)Exp072_GateAddr;
            uint flNP = 0;
            if (VirtualProtect((void*)Exp072_GateAddr, 16u, 64u, &flNP))
            {
                ptr[0] = _exp072GateOriginalByte;
                VirtualProtect((void*)Exp072_GateAddr, 16u, flNP, &flNP);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp072_GateAddr, 16u);
            }
            _exp072GatePatched = false;
            Console.Error.WriteLine("[EXP072-GATE-CLEAR] Original byte restored, continuing execution");
        }

        Console.Error.Flush();

        // Set RIP back to the gate instruction (now restored)
        WriteCtxU64(contextRecord, 248, Exp072_GateAddr);
        return true;
    }
}
