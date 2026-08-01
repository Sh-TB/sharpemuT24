// EXP-101: Trace all 5 PLT stub calls inside the registration helper.
//
// Purpose:
// Determine whether any of the 5 PLT stubs called by the registration helper
// (0x804F889D0 and 0x804FA8490) return failure (non-zero), which would cause
// the callback storage at 0x804F88A76 (xchg [r14], rax) to be skipped.
//
// Also capture the NID for each PLT stub by reading SharpEmu's import stub
// entry, so we know WHAT function each stub resolves to.
//
// The 5 PLT stubs and their call sites:
//   1. 0x804FC36F0 — called at 0x804FA84B2 (inside 0x804FA8490, callback storage)
//   2. 0x804FC3700 — called at 0x804FA84C3 (inside 0x804FA8490, callback storage)
//   3. 0x804FC33C0 — called at 0x804F88A3F (inside 0x804F889D0, registration)
//   4. 0x804FC33D0 — called at 0x804F88A55 (inside 0x804F889D0, registration)
//   5. 0x804FC33E0 — called at 0x804F88A67 (inside 0x804F889D0, registration)
//
// Hypothesis:
// One of these 5 PLT stubs returns non-zero, causing the callback storage
// to be skipped. If all return 0, the callback IS stored (Case B/C).
//
// Expected results:
// - If any stub returns non-zero: Case A — callback NOT stored, that stub is the blocker
// - If all return 0: Case B — callback stored, mystery shifts to "stored but never invoked"
//
// EXP-101 introduced this tracer.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-101: PLT stub return value tracer =====

    // The 5 call sites (where the call instruction is) and their return sites
    // (the instruction right after the call, where we capture eax)
    private static readonly ulong[] Exp101_CallSites = new ulong[]
    {
        0x804FA84B2,  // call 0x804FC36F0 (in 0x804FA8490)
        0x804FA84C3,  // call 0x804FC3700 (in 0x804FA8490)
        0x804F88A3F,  // call 0x804FC33C0 (in 0x804F889D0)
        0x804F88A55,  // call 0x804FC33D0 (in 0x804F889D0)
        0x804F88A67,  // call 0x804FC33E0 (in 0x804F889D0)
    };

    private static readonly ulong[] Exp101_PLTTargets = new ulong[]
    {
        0x804FC36F0,
        0x804FC3700,
        0x804FC33C0,
        0x804FC33D0,
        0x804FC33E0,
    };

    private static readonly string[] Exp101_Labels = new string[]
    {
        "PLT36F0 (in 0x804FA8490, callback storage #1)",
        "PLT3700 (in 0x804FA8490, callback storage #2)",
        "PLT33C0 (in 0x804F889D0, registration #1)",
        "PLT33D0 (in 0x804F889D0, registration #2)",
        "PLT33E0 (in 0x804F889D0, registration #3)",
    };

    private byte[] _exp101OrigBytes = new byte[5];
    private bool[] _exp101Patched = new bool[5];
    private int _exp101HitCount;

    // EXP-101: Patches all 5 call sites with INT3.
    // On hit: logs the PLT target, then patches the return site to capture eax.
    // Hypothesis: if any stub returns non-zero, callback storage is skipped.
    private unsafe void Exp101PatchPLTTracers()
    {
        for (int i = 0; i < Exp101_CallSites.Length; i++)
        {
            if (_exp101Patched[i]) continue;
            try
            {
                ulong addr = Exp101_CallSites[i];
                var ptr = (byte*)addr;
                uint fl = 0;
                if (VirtualProtect((void*)addr, 16u, 64u, &fl))
                {
                    _exp101OrigBytes[i] = ptr[0];
                    ptr[0] = 0xCC;
                    _exp101Patched[i] = true;
                    Console.Error.WriteLine(
                        $"[EXP101-PATCH] call_site[{i}] at 0x{addr:X16} patched " +
                        $"(byte=0x{_exp101OrigBytes[i]:X2}) — target: 0x{Exp101_PLTTargets[i]:X}");
                    VirtualProtect((void*)addr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)addr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP101] call_site[{i}] patch failed: {ex.Message}");
            }
        }
    }

    // EXP-101: Handles INT3 from any of the 5 call sites.
    // Logs: which stub, caller RIP, input registers (rdi, rsi, rdx, rcx)
    // Then patches the return site (instruction after the call) to capture eax.
    private unsafe bool Exp101TryHandlePLTCallInt3(void* contextRecord, ulong rip)
    {
        int siteIndex = -1;
        for (int i = 0; i < Exp101_CallSites.Length; i++)
        {
            if (_exp101Patched[i] && rip - 1 == Exp101_CallSites[i])
            {
                siteIndex = i;
                break;
            }
        }
        if (siteIndex < 0) return false;

        _exp101HitCount++;
        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong rsi = ReadCtxU64(contextRecord, 168);
        ulong rdx = ReadCtxU64(contextRecord, 144);
        ulong rcx = ReadCtxU64(contextRecord, 136);
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP101-CALL] #{_exp101HitCount} site[{siteIndex}]=0x{Exp101_CallSites[siteIndex]:X} " +
            $"PLT=0x{Exp101_PLTTargets[siteIndex]:X} {Exp101_Labels[siteIndex]}");
        Console.Error.WriteLine(
            $"  caller=0x{callerRip:X16} rdi=0x{rdi:X16} rsi=0x{rsi:X} rdx=0x{rdx:X16} rcx=0x{rcx:X16}");

        // Restore call site
        ulong callAddr = Exp101_CallSites[siteIndex];
        var ptr = (byte*)callAddr;
        uint fl = 0;
        if (VirtualProtect((void*)callAddr, 16u, 64u, &fl))
        {
            ptr[0] = _exp101OrigBytes[siteIndex];
            VirtualProtect((void*)callAddr, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)callAddr, 16u);
        }
        _exp101Patched[siteIndex] = false;

        // Patch return site (call instruction is 5 bytes: E8 + rel32)
        ulong retSite = callAddr + 5;
        var rptr = (byte*)retSite;
        uint rfl = 0;
        if (VirtualProtect((void*)retSite, 16u, 64u, &rfl))
        {
            // Store the original byte and site index for the return handler
            // We need a way to map return site -> site index
            // Use a simple array since we only have 5 sites
            _exp101RetOrigByte = rptr[0];
            _exp101RetSiteIdx = siteIndex;
            _exp101RetSiteAddr = retSite;
            rptr[0] = 0xCC;
            _exp101RetPatched = true;
            Console.Error.WriteLine($"[EXP101-PATCH] ret_site at 0x{retSite:X16} patched");
            VirtualProtect((void*)retSite, 16u, rfl, &rfl);
            FlushInstructionCache(GetCurrentProcess(), (void*)retSite, 16u);
        }

        WriteCtxU64(contextRecord, 248, callAddr);
        return true;
    }

    // Return-site state (only one return site patched at a time)
    private byte _exp101RetOrigByte;
    private int _exp101RetSiteIdx;
    private ulong _exp101RetSiteAddr;
    private bool _exp101RetPatched;

    // EXP-101: Handles INT3 from the return site.
    // Captures eax (return value) and classifies as success (0) or failure (non-zero).
    private unsafe bool Exp101TryHandlePLTRetInt3(void* contextRecord, ulong rip)
    {
        if (!_exp101RetPatched) return false;
        if (rip - 1 != _exp101RetSiteAddr) return false;

        ulong rax = ReadCtxU64(contextRecord, 120);

        string verdict = rax == 0 ? "*** SUCCESS (eax=0) ***" : "*** FAILURE (eax!=0) — callback storage may be skipped! ***";
        Console.Error.WriteLine(
            $"[EXP101-RET] site[{_exp101RetSiteIdx}] PLT=0x{Exp101_PLTTargets[_exp101RetSiteIdx]:X} " +
            $"eax=0x{rax:X16}  {verdict}");

        // Restore return site
        var ptr = (byte*)_exp101RetSiteAddr;
        uint fl = 0;
        if (VirtualProtect((void*)_exp101RetSiteAddr, 16u, 64u, &fl))
        {
            ptr[0] = _exp101RetOrigByte;
            VirtualProtect((void*)_exp101RetSiteAddr, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)_exp101RetSiteAddr, 16u);
        }
        _exp101RetPatched = false;

        WriteCtxU64(contextRecord, 248, _exp101RetSiteAddr);
        return true;
    }
}
