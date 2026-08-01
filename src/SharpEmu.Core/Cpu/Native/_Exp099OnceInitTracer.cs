// EXP-099: Trace the once-init primitive 0x804FC33B0 and compare with the
// working path's once-init 0x804FC3750.
//
// EXP-098 found that the registration helper 0x804F889D0 calls 0x804FC33B0
// (a PLT stub: jmp [GOT 0x8089243C8]) and checks its return value:
//   0x804F88A00: call 0x804FC33B0
//   0x804F88A05: mov ebx, 0x1f
//   0x804F88A0A: test eax, eax
//   0x804F88A0C: jne error_path (0x804F88A79)
//
// The working path uses a DIFFERENT once-init: 0x804FC3750 (PLT stub: jmp [GOT 0x808924598])
//
// Hypothesis: 0x804FC33B0 returns failure (non-zero), causing the registration
// to be skipped. The working path's 0x804FC3750 succeeds.
//
// This tracer:
//   1. INT3 at 0x804F88A00 (before call to 0x804FC33B0) — dump args
//   2. INT3 at 0x804F88A05 (after call returns) — dump eax (return value)
//   3. Also INT3 at 0x804FBF799 (working path's call to 0x804FC3750) for comparison

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-099: Once-init primitive tracer =====

    // Dead path: call to 0x804FC33B0 at 0x804F88A00 (inside 0x804F889D0)
    private const ulong Exp099_DeadCallSite = 0x804F88A00;
    private const ulong Exp099_DeadReturnSite = 0x804F88A05;

    // Working path: call to 0x804FC3750 at 0x804FBF799 (inside 0x804FBF780)
    private const ulong Exp099_WorkingCallSite = 0x804FBF799;
    private const ulong Exp099_WorkingReturnSite = 0x804FBF79E;

    private byte _exp099DeadCallOrig;
    private bool _exp099DeadCallPatched;
    private byte _exp099DeadRetOrig;
    private bool _exp099DeadRetPatched;
    private byte _exp099WorkCallOrig;
    private bool _exp099WorkCallPatched;
    private byte _exp099WorkRetOrig;
    private bool _exp099WorkRetPatched;

    // EXP-099: Patches both call sites and return sites to trace the once-init
    // primitives' arguments and return values.
    // Hypothesis: 0x804FC33B0 (dead path) returns failure, 0x804FC3750 (working) succeeds.
    // Confirm: eax != 0 at 0x804F88A05 (dead return) = hypothesis confirmed.
    // Reject: eax == 0 at 0x804F88A05 = registration succeeds, issue is elsewhere.
    private unsafe void Exp099PatchOnceInitTracers()
    {
        // Patch dead path call site
        if (!_exp099DeadCallPatched)
        {
            try
            {
                var ptr = (byte*)Exp099_DeadCallSite;
                uint fl = 0;
                if (VirtualProtect((void*)Exp099_DeadCallSite, 16u, 64u, &fl))
                {
                    _exp099DeadCallOrig = ptr[0];
                    ptr[0] = 0xCC;
                    _exp099DeadCallPatched = true;
                    Console.Error.WriteLine($"[EXP099-PATCH] dead_call at 0x{Exp099_DeadCallSite:X16} patched (byte=0x{_exp099DeadCallOrig:X2})");
                    VirtualProtect((void*)Exp099_DeadCallSite, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_DeadCallSite, 16u);
                }
            }
            catch (Exception ex) { Console.Error.WriteLine($"[EXP099] dead_call patch failed: {ex.Message}"); }
        }

        // Patch working path call site
        if (!_exp099WorkCallPatched)
        {
            try
            {
                var ptr = (byte*)Exp099_WorkingCallSite;
                uint fl = 0;
                if (VirtualProtect((void*)Exp099_WorkingCallSite, 16u, 64u, &fl))
                {
                    _exp099WorkCallOrig = ptr[0];
                    ptr[0] = 0xCC;
                    _exp099WorkCallPatched = true;
                    Console.Error.WriteLine($"[EXP099-PATCH] work_call at 0x{Exp099_WorkingCallSite:X16} patched (byte=0x{_exp099WorkCallOrig:X2})");
                    VirtualProtect((void*)Exp099_WorkingCallSite, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_WorkingCallSite, 16u);
                }
            }
            catch (Exception ex) { Console.Error.WriteLine($"[EXP099] work_call patch failed: {ex.Message}"); }
        }
    }

    // EXP-099: Handle INT3 from dead path call site (before 0x804FC33B0)
    // Dumps: rdi (arg1 — pointer to once_init struct), caller RIP
    // Then patches the return site to capture eax.
    private unsafe bool Exp099TryHandleDeadCallInt3(void* contextRecord, ulong rip)
    {
        if (!_exp099DeadCallPatched) return false;
        if (rip - 1 != Exp099_DeadCallSite) return false;

        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP099-DEAD-CALL] caller=0x{callerRip:X16} rdi(once_init_ptr)=0x{rdi:X16}");

        // Restore call site
        var ptr = (byte*)Exp099_DeadCallSite;
        uint fl = 0;
        if (VirtualProtect((void*)Exp099_DeadCallSite, 16u, 64u, &fl))
        {
            ptr[0] = _exp099DeadCallOrig;
            VirtualProtect((void*)Exp099_DeadCallSite, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_DeadCallSite, 16u);
        }
        _exp099DeadCallPatched = false;

        // Patch return site to capture eax
        if (!_exp099DeadRetPatched)
        {
            var rptr = (byte*)Exp099_DeadReturnSite;
            uint rfl = 0;
            if (VirtualProtect((void*)Exp099_DeadReturnSite, 16u, 64u, &rfl))
            {
                _exp099DeadRetOrig = rptr[0];
                rptr[0] = 0xCC;
                _exp099DeadRetPatched = true;
                Console.Error.WriteLine($"[EXP099-PATCH] dead_ret at 0x{Exp099_DeadReturnSite:X16} patched");
                VirtualProtect((void*)Exp099_DeadReturnSite, 16u, rfl, &rfl);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_DeadReturnSite, 16u);
            }
        }

        WriteCtxU64(contextRecord, 248, Exp099_DeadCallSite);
        return true;
    }

    // EXP-099: Handle INT3 from dead path return site (after 0x804FC33B0)
    // Dumps: eax (return value — 0=success, non-zero=failure)
    private unsafe bool Exp099TryHandleDeadRetInt3(void* contextRecord, ulong rip)
    {
        if (!_exp099DeadRetPatched) return false;
        if (rip - 1 != Exp099_DeadReturnSite) return false;

        ulong rax = ReadCtxU64(contextRecord, 120);
        ulong rbx = ReadCtxU64(contextRecord, 128);

        string verdict = rax == 0 ? "*** SUCCESS (eax=0) ***" : "*** FAILURE (eax!=0) — registration skipped! ***";
        Console.Error.WriteLine(
            $"[EXP099-DEAD-RET] eax(return)=0x{rax:X16} ebx=0x{rbx:X16}  {verdict}");

        // Restore return site
        var ptr = (byte*)Exp099_DeadReturnSite;
        uint fl = 0;
        if (VirtualProtect((void*)Exp099_DeadReturnSite, 16u, 64u, &fl))
        {
            ptr[0] = _exp099DeadRetOrig;
            VirtualProtect((void*)Exp099_DeadReturnSite, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_DeadReturnSite, 16u);
        }
        _exp099DeadRetPatched = false;

        WriteCtxU64(contextRecord, 248, Exp099_DeadReturnSite);
        return true;
    }

    // EXP-099: Handle INT3 from working path call site (before 0x804FC3750)
    private unsafe bool Exp099TryHandleWorkCallInt3(void* contextRecord, ulong rip)
    {
        if (!_exp099WorkCallPatched) return false;
        if (rip - 1 != Exp099_WorkingCallSite) return false;

        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP099-WORK-CALL] caller=0x{callerRip:X16} rdi=0x{rdi:X16}");

        var ptr = (byte*)Exp099_WorkingCallSite;
        uint fl = 0;
        if (VirtualProtect((void*)Exp099_WorkingCallSite, 16u, 64u, &fl))
        {
            ptr[0] = _exp099WorkCallOrig;
            VirtualProtect((void*)Exp099_WorkingCallSite, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_WorkingCallSite, 16u);
        }
        _exp099WorkCallPatched = false;

        // Patch working return site
        if (!_exp099WorkRetPatched)
        {
            var rptr = (byte*)Exp099_WorkingReturnSite;
            uint rfl = 0;
            if (VirtualProtect((void*)Exp099_WorkingReturnSite, 16u, 64u, &rfl))
            {
                _exp099WorkRetOrig = rptr[0];
                rptr[0] = 0xCC;
                _exp099WorkRetPatched = true;
                Console.Error.WriteLine($"[EXP099-PATCH] work_ret at 0x{Exp099_WorkingReturnSite:X16} patched");
                VirtualProtect((void*)Exp099_WorkingReturnSite, 16u, rfl, &rfl);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_WorkingReturnSite, 16u);
            }
        }

        WriteCtxU64(contextRecord, 248, Exp099_WorkingCallSite);
        return true;
    }

    // EXP-099: Handle INT3 from working path return site (after 0x804FC3750)
    private unsafe bool Exp099TryHandleWorkRetInt3(void* contextRecord, ulong rip)
    {
        if (!_exp099WorkRetPatched) return false;
        if (rip - 1 != Exp099_WorkingReturnSite) return false;

        ulong rax = ReadCtxU64(contextRecord, 120);

        string verdict = rax == 0 ? "*** SUCCESS (eax=0) ***" : "*** FAILURE (eax!=0) ***";
        Console.Error.WriteLine(
            $"[EXP099-WORK-RET] eax(return)=0x{rax:X16}  {verdict}");

        var ptr = (byte*)Exp099_WorkingReturnSite;
        uint fl = 0;
        if (VirtualProtect((void*)Exp099_WorkingReturnSite, 16u, 64u, &fl))
        {
            ptr[0] = _exp099WorkRetOrig;
            VirtualProtect((void*)Exp099_WorkingReturnSite, 16u, fl, &fl);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp099_WorkingReturnSite, 16u);
        }
        _exp099WorkRetPatched = false;

        WriteCtxU64(contextRecord, 248, Exp099_WorkingReturnSite);
        return true;
    }
}
