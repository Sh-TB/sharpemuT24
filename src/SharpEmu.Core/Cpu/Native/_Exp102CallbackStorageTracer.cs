// EXP-102: Trace the callback storage address and connect to EXP-096.
//
// Purpose:
// At 0x804F88A76 (xchg [r14], rax), capture the value of r14 — the address
// where the callback pointer is stored. Then search for readers of that address.
//
// From static analysis:
//   0x804F889D0 receives rdi = [rbx + 8] (from 0x804FA20E0)
//   0x804F889E6: mov r14, rdi  ; r14 = the registration context
//   0x804F88A76: xchg [r14], rax  ; store callback at [r14]
//
// So the callback is stored at [r14] = [original_arg + 8].
// The original arg comes from callers of 0x804FA20E0 (3 callers found).
//
// Hypothesis:
// The callback is stored at a specific address inside an IL2CPP context structure.
// Finding that address and searching for readers will reveal the invocation path.
//
// Cross-reference with EXP-096:
// The work-submission function 0x804F6EC20 reads [entry+0x88] for the semaphore
// handle and [entry+0x90] for the work counter. Check if r14's target is the
// same structure that 0x804F6EC20 reads from.
//
// EXP-102 introduced this tracer.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-102: Callback storage address tracer =====

    // INT3 at 0x804F88A76 (the xchg [r14], rax instruction)
    private const ulong Exp102_XchgAddr = 0x804F88A76;
    private byte _exp102XchgOrigByte1;
    private byte _exp102XchgOrigByte2;
    private bool _exp102XchgPatched;
    private bool _exp102Dumped;

    // EXP-102: Patches the xchg instruction with INT3 to capture r14.
    // The xchg [r14], rax is a 2-byte instruction (48 87 06 = xchg rax, [r14]).
    // Actually let me check: 48 87 06 = REX.W xchg rax, [r14] = 3 bytes.
    // But we only need to patch the first byte with CC (INT3).
    // On hit: dump r14 (the storage address), rax (the callback pointer being stored),
    // and the memory at [r14] before and after the xchg.
    private unsafe void Exp102PatchXchgTracer()
    {
        if (_exp102XchgPatched) return;
        try
        {
            var ptr = (byte*)Exp102_XchgAddr;
            uint fl = 0;
            if (VirtualProtect((void*)Exp102_XchgAddr, 16u, 64u, &fl))
            {
                _exp102XchgOrigByte1 = ptr[0];
                _exp102XchgOrigByte2 = ptr[1];
                ptr[0] = 0xCC;
                _exp102XchgPatched = true;
                Console.Error.WriteLine(
                    $"[EXP102-PATCH] xchg at 0x{Exp102_XchgAddr:X16} patched (bytes=0x{_exp102XchgOrigByte1:X2} 0x{_exp102XchgOrigByte2:X2})");
                VirtualProtect((void*)Exp102_XchgAddr, 16u, fl, &fl);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp102_XchgAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP102] xchg patch failed: {ex.Message}");
        }
    }

    // EXP-102: Handles INT3 from the xchg instruction.
    // Captures: r14 (storage address), rax (callback pointer being stored),
    // [r14] before xchg, and classifies the address (global vs heap).
    private unsafe bool Exp102TryHandleXchgInt3(void* contextRecord, ulong rip)
    {
        if (!_exp102XchgPatched) return false;
        if (rip - 1 != Exp102_XchgAddr) return false;

        if (_exp102Dumped)
        {
            // Already captured once — just restore and continue
            var ptr = (byte*)Exp102_XchgAddr;
            uint fl = 0;
            if (VirtualProtect((void*)Exp102_XchgAddr, 16u, 64u, &fl))
            {
                ptr[0] = _exp102XchgOrigByte1;
                ptr[1] = _exp102XchgOrigByte2;
                VirtualProtect((void*)Exp102_XchgAddr, 16u, fl, &fl);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp102_XchgAddr, 16u);
            }
            _exp102XchgPatched = false;
            WriteCtxU64(contextRecord, 248, Exp102_XchgAddr);
            return true;
        }
        _exp102Dumped = true;

        ulong r14 = ReadCtxU64(contextRecord, 232); // CTX_R14 (corrected from 284 in EXP-103)
        ulong rax = ReadCtxU64(contextRecord, 120); // CTX_RAX
        ulong r12 = ReadCtxU64(contextRecord, 216); // CTX_R12 (corrected from 276 in EXP-103)

        Console.Error.WriteLine(
            $"[EXP102-XCHG] *** CALLBACK STORAGE *** r14=0x{r14:X16} rax=0x{rax:X16} (callback ptr)");
        Console.Error.WriteLine(
            $"  r12(IL2CPP context)=0x{r12:X16}");

        // Classify the address
        string region = "UNKNOWN";
        if (r14 >= 0x804CD5000 && r14 < 0x808800000) region = "PRX data segment";
        else if (r14 >= 0x800000000 && r14 < 0x804CD5000) region = "EBOOT";
        else if (r14 >= 0x600000000 && r14 < 0x700000000) region = "guest heap";
        else if (r14 >= 0x6FFFF000000 && r14 < 0x700000000000) region = "stack/import area";
        Console.Error.WriteLine($"  r14 region: {region}");

        // Read [r14] BEFORE the xchg — ONLY if r14 is non-NULL (EXP-103 fix: prevent JIT crash)
        if (r14 != 0 && r14 > 0x1000)
        {
            ulong beforeVal = 0;
            try { beforeVal = *(ulong*)r14; } catch { }
            Console.Error.WriteLine(
                $"  [r14] BEFORE xchg = 0x{beforeVal:X16}");

            // Read what's at [r14-8] and [r14+8]
            try
            {
                ulong pre = *(ulong*)(r14 - 8UL);
                ulong post = *(ulong*)(r14 + 8UL);
                Console.Error.WriteLine(
                    $"  [r14-8]=0x{pre:X16}  [r14]=0x{beforeVal:X16}  [r14+8]=0x{post:X16}");
            }
            catch { }

            // Also read more context around r14
            try
            {
                Console.Error.WriteLine($"  Context around r14 (0x{r14:X16}):");
                for (int i = -0x20; i <= 0x20; i += 8)
                {
                    ulong val = *(ulong*)(r14 + (ulong)i);
                    string cls = "";
                    if (val >= 0x804CD5000 && val < 0x808800000) cls = " (PRX)";
                    else if (val >= 0x600000000 && val < 0x700000000) cls = " (heap)";
                    else if (val == 0) cls = " (NULL)";
                    Console.Error.WriteLine($"    [r14+0x{i:X2}] = 0x{val:X16}{cls}");
                }
            }
            catch { }
        }
        else
        {
            Console.Error.WriteLine($"  *** r14 is NULL or invalid — skipping memory dump ***");
        }

        // Check: is r14 inside the IL2CPP context structure at [0x808923D88]?
        try
        {
            ulong ctxPtr = *(ulong*)0x808923D88;
            Console.Error.WriteLine(
                $"  IL2CPP context [0x808923D88] = 0x{ctxPtr:X16}");
            if (ctxPtr != 0 && r14 >= ctxPtr && r14 < ctxPtr + 0x1000)
            {
                ulong offset = r14 - ctxPtr;
                Console.Error.WriteLine(
                    $"  *** r14 is at context+0x{offset:X} (inside IL2CPP context structure!) ***");
            }
        }
        catch { }

        Console.Error.Flush();

        // Restore and let the xchg execute
        var ptr2 = (byte*)Exp102_XchgAddr;
        uint fl2 = 0;
        if (VirtualProtect((void*)Exp102_XchgAddr, 16u, 64u, &fl2))
        {
            ptr2[0] = _exp102XchgOrigByte1;
            ptr2[1] = _exp102XchgOrigByte2;
            VirtualProtect((void*)Exp102_XchgAddr, 16u, fl2, &fl2);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp102_XchgAddr, 16u);
        }
        _exp102XchgPatched = false;

        WriteCtxU64(contextRecord, 248, Exp102_XchgAddr);
        return true;
    }
}
