// EXP-096: Trace all 3 callers of the ThreadPool work-submission function (0x804F6EC20).
//
// The work-submission function at 0x804F6EC20 is the ONLY path to SignalSema(0xA6).
// It has exactly 3 callers in the PRX:
//   0x804F4571A  (gated by cmp [rbx+0x6c], 0 — skips if 0)
//   0x804F9FAAA  (context unknown)
//   0x804FA14C8  (gated by preceding logic)
//
// This tracer patches all 3 call sites with INT3. On each hit, it logs:
//   - Which call site was reached
//   - The caller RIP (return address on stack)
//   - Register state (rdi, rsi, rdx, rbx)
//   - Whether the call is skipped (conditional jump before it)
//
// Classification:
//   Case A: NONE of the 3 call sites are reached → work submission never happens
//   Case B: A call site is reached but the conditional gate skips it
//   Case C: The call is made but SignalSema still doesn't fire

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-096: Work submission tracer =====

    // The 3 call sites that call 0x804F6EC20 (work submission function)
    private static readonly ulong[] Exp096_CallSites = new ulong[]
    {
        0x804F4571A,
        0x804F9FAAA,
        0x804FA14C8,
    };

    // Original bytes at each call site (for restoration)
    private byte[] _exp096OriginalBytes = new byte[3];
    private bool[] _exp096Patched = new bool[3];
    private int _exp096TotalHits;

    /// <summary>
    /// Installs INT3 at all 3 work-submission call sites.
    /// </summary>
    private unsafe void Exp096PatchWorkSubmissionTracers()
    {
        for (int i = 0; i < Exp096_CallSites.Length; i++)
        {
            if (_exp096Patched[i]) continue;
            try
            {
                ulong addr = Exp096_CallSites[i];
                var ptr = (byte*)addr;
                uint flNewProtect = 0;
                if (VirtualProtect((void*)addr, 16u, 64u, &flNewProtect))
                {
                    _exp096OriginalBytes[i] = ptr[0];
                    ptr[0] = 0xCC;
                    _exp096Patched[i] = true;
                    Console.Error.WriteLine(
                        $"[EXP096-PATCH] call_site[{i}] at 0x{addr:X16} patched with INT3 " +
                        $"(original byte=0x{_exp096OriginalBytes[i]:X2})");
                    VirtualProtect((void*)addr, 16u, flNewProtect, &flNewProtect);
                    FlushInstructionCache(GetCurrentProcess(), (void*)addr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP096] Failed to patch call_site[{i}]: {ex.Message}");
            }
        }
    }

    /// <summary>
    /// Handles INT3 from any of the 3 work-submission call sites.
    /// </summary>
    private unsafe bool Exp096TryHandleWorkSubmissionInt3(void* contextRecord, ulong rip)
    {
        // Check if this INT3 is from one of our call sites
        int siteIndex = -1;
        for (int i = 0; i < Exp096_CallSites.Length; i++)
        {
            if (_exp096Patched[i] && rip - 1 == Exp096_CallSites[i])
            {
                siteIndex = i;
                break;
            }
        }
        if (siteIndex < 0) return false;

        _exp096TotalHits++;
        int hitNum = _exp096TotalHits;
        int tid = Environment.CurrentManagedThreadId;
        ulong siteAddr = Exp096_CallSites[siteIndex];

        // Read registers
        ulong rdi = ReadCtxU64(contextRecord, 176); // CTX_RDI — thread pool context
        ulong rsi = ReadCtxU64(contextRecord, 168); // CTX_RSI — usually 0x1 (work count)
        ulong rdx = ReadCtxU64(contextRecord, 144); // CTX_RDX
        ulong rbx = ReadCtxU64(contextRecord, 128); // CTX_RBX — often the work item
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP096-WORKSUBMIT-ENTER] hit#{hitNum} site[{siteIndex}]=0x{siteAddr:X16} " +
            $"caller=0x{callerRip:X16} tid={tid}");
        Console.Error.WriteLine(
            $"  rdi(ctx)=0x{rdi:X16} rsi(work_count)={rsi} rdx=0x{rdx:X16} rbx(work_item)=0x{rbx:X16}");

        // Read the thread pool context fields to understand the state
        if (rdi != 0 && rdi > 0x1000)
        {
            try
            {
                // Read key fields from the thread pool context structure
                // Based on disassembly: [ctx+0x10] = work counter, [ctx+0x14] = processed counter
                // [ctx+0x50] = worker array ptr, [ctx+0x58] = worker count
                // [ctx+0x68] = some flag, [ctx+0x6c] = active worker count
                ulong ctx10 = *(ulong*)(rdi + 0x10);
                ulong ctx50 = *(ulong*)(rdi + 0x50);
                uint ctx58 = *(uint*)(rdi + 0x58);
                uint ctx68 = *(uint*)(rdi + 0x68);
                uint ctx6c = *(uint*)(rdi + 0x6c);
                Console.Error.WriteLine(
                    $"  [ctx+0x10]=0x{ctx10:X16} [ctx+0x50]=0x{ctx50:X16} " +
                    $"[ctx+0x58]={ctx58} [ctx+0x68]={ctx68} [ctx+0x6c]={ctx6c}");
            }
            catch { }
        }

        // Check if the instruction BEFORE the call site is a conditional jump that might skip it
        // (We can't easily decode the previous instruction, but we can note the site index)
        string gateInfo = siteIndex == 0 ? "gated by cmp [rbx+0x6c],0" : "unknown gate";
        Console.Error.WriteLine($"  site[{siteIndex}] is {gateInfo}");

        Console.Error.Flush();

        // Restore the call site byte
        var ptr = (byte*)siteAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)siteAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp096OriginalBytes[siteIndex];
            VirtualProtect((void*)siteAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)siteAddr, 16u);
        }
        _exp096Patched[siteIndex] = false;

        // Set RIP to the call site (re-execute the call instruction)
        WriteCtxU64(contextRecord, 248, siteAddr);
        return true;
    }
}
