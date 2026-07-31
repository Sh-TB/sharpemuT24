// EXP-095: Trace the _ThreadPoolWaitCallback lookup at 0x804F055D6.
//
// real_init calls il2cpp_class_get_method_from_name (0x804F21D70) at 0x804F055D6
// with:
//   rdi = [0x808B539F0]  (type pointer — Il2CppClass* for System.Threading.ThreadPool)
//   rsi = "System.Threading"  (namespace string)
//   rdx = "_ThreadPoolWaitCallback"  (method name string)
//   result stored at [0x808B53C48]
//
// EXP-094 confirmed the lookup uses [0x808923D88] (context), NOT 0x801EF7610.
// The context IS populated, [context+0x30] IS non-NULL, but the lookup returns NULL.
//
// This tracer uses a TWO-STAGE INT3 patch:
//   Stage 1: INT3 at 0x804F055D6 (call site) — capture args (rdi, rsi, rdx, strings)
//            Then patch 0x804F055DB (return site) with INT3 to capture the result.
//   Stage 2: INT3 at 0x804F055DB (return site) — capture rax (return value)
//
// Also dumps:
//   - [0x808923D88] (context pointer)
//   - [context+0x30] (method table pointer)
//   - First 8 entries of the method table (if accessible)
//
// This will answer:
//   1. Is "_ThreadPoolWaitCallback" missing from the table?
//   2. Is the lookup key wrong?
//   3. Is the method table incomplete?
//   4. Is SharpEmu creating the context but not populating methods?
//   5. Is there another initialization stage after module_start that fills the table?

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-095: _ThreadPoolWaitCallback lookup tracer =====

    // Call site: 0x804F055D6 (call 0x804f21d70 — 5 bytes: E8 + rel32)
    private const ulong Exp095_CallSiteAddr = 0x804F055D6;

    // Return site: 0x804F055DB (mov [rip+0x3c4e666], rax — 7 bytes: 48 89 05 + rel32)
    // This is the instruction RIGHT AFTER the call. When we hit this, rax = return value.
    private const ulong Exp095_ReturnSiteAddr = 0x804F055DB;

    // Context global (from EXP-094)
    private const ulong Exp095_ContextGlobalAddr = 0x808923D88;

    // Type pointer global (loaded into rdi before the call)
    private const ulong Exp095_TypePtrGlobalAddr = 0x808B539F0;

    // Result global (where the return value is stored)
    private const ulong Exp095_ResultGlobalAddr = 0x808B53C48;

    // Stage 1: call site patch state
    private byte _exp095CallSiteOriginalByte;
    private bool _exp095CallSitePatched;

    // Stage 2: return site patch state
    private byte _exp095ReturnSiteOriginalByte;
    private bool _exp095ReturnSitePatched;

    // Track which call we're tracing (there are 3 sequential calls to 0x804F21D70
    // at 0x804F055B5, 0x804F055D6, 0x804F055F7). We only patch 0x804F055D6.
    private int _exp095HitCount;

    /// <summary>
    /// Installs INT3 at the call site (0x804F055D6).
    /// Called from DirectExecutionBackend.Imports.cs during resolver initialization.
    /// </summary>
    private unsafe void Exp095PatchThreadPoolLookup()
    {
        if (_exp095CallSitePatched) return;
        try
        {
            var ptr = (byte*)Exp095_CallSiteAddr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp095_CallSiteAddr, 16u, 64u, &flNewProtect))
            {
                _exp095CallSiteOriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp095CallSitePatched = true;
                Console.Error.WriteLine(
                    $"[EXP095-PATCH] call_site at 0x{Exp095_CallSiteAddr:X16} patched with INT3 " +
                    $"(original byte=0x{_exp095CallSiteOriginalByte:X2})");
                VirtualProtect((void*)Exp095_CallSiteAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp095_CallSiteAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP095] Failed to patch call_site: {ex.Message}");
        }
    }

    /// <summary>
    /// Stage 1 handler: INT3 at the call site (0x804F055D6).
    /// Captures: rdi (type ptr), rsi (namespace), rdx (method name), and the strings.
    /// Then patches the return site (0x804F055DB) to capture the result.
    /// </summary>
    private unsafe bool Exp095TryHandleCallSiteInt3(void* contextRecord, ulong rip)
    {
        if (!_exp095CallSitePatched) return false;
        if (rip - 1 != Exp095_CallSiteAddr) return false;

        _exp095HitCount++;
        int hitNum = _exp095HitCount;
        int tid = Environment.CurrentManagedThreadId;

        // Read registers
        ulong rdi = ReadCtxU64(contextRecord, 176); // CTX_RDI — type pointer
        ulong rsi = ReadCtxU64(contextRecord, 168); // CTX_RSI — namespace string
        ulong rdx = ReadCtxU64(contextRecord, 144); // CTX_RDX — method name string
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP095-CALLSITE-ENTER] hit#{hitNum} caller=0x{callerRip:X16} tid={tid}");
        Console.Error.WriteLine(
            $"  rdi(type_ptr)=0x{rdi:X16} rsi(namespace)=0x{rsi:X16} rdx(method_name)=0x{rdx:X16}");

        // Read the namespace string (rsi points to a null-terminated ASCII string)
        string namespaceStr = Exp095ReadCString(rsi, 128);
        string methodNameStr = Exp095ReadCString(rdx, 128);
        Console.Error.WriteLine(
            $"  namespace=\"{namespaceStr}\" method_name=\"{methodNameStr}\"");

        // Read the type pointer global
        ulong typePtrGlobal = 0;
        try { typePtrGlobal = *(ulong*)Exp095_TypePtrGlobalAddr; } catch { }
        Console.Error.WriteLine(
            $"  [0x{Exp095_TypePtrGlobalAddr:X}] (type_ptr_global) = 0x{typePtrGlobal:X16}");

        // Read the context global and method table
        Exp095DumpContextAndMethodTable("CALLSITE");

        // Read the result global BEFORE the call (should be NULL/uninitialized)
        ulong resultBefore = 0;
        try { resultBefore = *(ulong*)Exp095_ResultGlobalAddr; } catch { }
        Console.Error.WriteLine(
            $"  [0x{Exp095_ResultGlobalAddr:X}] (result_global BEFORE call) = 0x{resultBefore:X16}");

        Console.Error.Flush();

        // Restore the call site byte
        var ptr = (byte*)Exp095_CallSiteAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp095_CallSiteAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp095CallSiteOriginalByte;
            VirtualProtect((void*)Exp095_CallSiteAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp095_CallSiteAddr, 16u);
        }
        _exp095CallSitePatched = false;

        // Now patch the RETURN site (0x804F055DB) to capture rax after the call returns
        Exp095PatchReturnSite();

        // Set RIP to the call site (re-execute the call instruction)
        WriteCtxU64(contextRecord, 248, Exp095_CallSiteAddr);
        return true;
    }

    /// <summary>
    /// Patches the return site (0x804F055DB) with INT3.
    /// Called after the call site handler restores the call and lets it execute.
    /// </summary>
    private unsafe void Exp095PatchReturnSite()
    {
        if (_exp095ReturnSitePatched) return;
        try
        {
            var ptr = (byte*)Exp095_ReturnSiteAddr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp095_ReturnSiteAddr, 16u, 64u, &flNewProtect))
            {
                _exp095ReturnSiteOriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp095ReturnSitePatched = true;
                Console.Error.WriteLine(
                    $"[EXP095-PATCH] return_site at 0x{Exp095_ReturnSiteAddr:X16} patched with INT3 " +
                    $"(original byte=0x{_exp095ReturnSiteOriginalByte:X2})");
                VirtualProtect((void*)Exp095_ReturnSiteAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp095_ReturnSiteAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP095] Failed to patch return_site: {ex.Message}");
        }
    }

    /// <summary>
    /// Stage 2 handler: INT3 at the return site (0x804F055DB).
    /// Captures: rax (return value of il2cpp_class_get_method_from_name).
    /// </summary>
    private unsafe bool Exp095TryHandleReturnSiteInt3(void* contextRecord, ulong rip)
    {
        if (!_exp095ReturnSitePatched) return false;
        if (rip - 1 != Exp095_ReturnSiteAddr) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rax = ReadCtxU64(contextRecord, 120); // CTX_RAX — return value

        Console.Error.WriteLine(
            $"[EXP095-RETURNSITE-ENTER] tid={tid}");
        Console.Error.WriteLine(
            $"  rax(return_value)=0x{rax:X16}  {(rax == 0 ? "*** NULL — lookup FAILED ***" : "*** NON-NULL — lookup SUCCEEDED ***")}");

        // Read the result global AFTER the call (the mov [rip+...], rax hasn't executed yet,
        // but rax IS the value that will be stored)
        Console.Error.WriteLine(
            $"  result will be stored at [0x{Exp095_ResultGlobalAddr:X}]");

        // Dump context and method table again (post-call state)
        Exp095DumpContextAndMethodTable("RETURNSITE");

        // EXP-096 fix: Skip the MethodInfo content dump to avoid .NET JIT crash.
        // The return value (rax) is sufficient — we only need to know it's non-NULL.
        if (rax != 0 && rax > 0x1000)
        {
            Console.Error.WriteLine($"  Method info at 0x{rax:X16} (content dump skipped — EXP-096)");
        }

        Console.Error.Flush();

        // Restore the return site byte
        var ptr = (byte*)Exp095_ReturnSiteAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp095_ReturnSiteAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp095ReturnSiteOriginalByte;
            VirtualProtect((void*)Exp095_ReturnSiteAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp095_ReturnSiteAddr, 16u);
        }
        _exp095ReturnSitePatched = false;

        // Set RIP to the return site (re-execute the mov instruction)
        WriteCtxU64(contextRecord, 248, Exp095_ReturnSiteAddr);
        return true;
    }

    /// <summary>
    /// Dumps the context global [0x808923D88] and method table [context+0x30].
    /// </summary>
    private unsafe void Exp095DumpContextAndMethodTable(string stage)
    {
        try
        {
            ulong ctxPtr = *(ulong*)Exp095_ContextGlobalAddr;
            Console.Error.WriteLine(
                $"  [EXP095-{stage}] [0x{Exp095_ContextGlobalAddr:X}] (context) = 0x{ctxPtr:X16}");

            if (ctxPtr == 0)
            {
                Console.Error.WriteLine($"  [EXP095-{stage}] context is NULL — cannot dump method table");
                return;
            }

            // Read [context+0x30] — the method table pointer
            ulong methodTablePtr = *(ulong*)(ctxPtr + 0x30);
            Console.Error.WriteLine(
                $"  [EXP095-{stage}] [context+0x30] (method_table_ptr) = 0x{methodTablePtr:X16}");

            if (methodTablePtr == 0)
            {
                Console.Error.WriteLine($"  [EXP095-{stage}] method_table_ptr is NULL — table not populated");
                return;
            }

            // EXP-096 fix: Skip the method table content dump to avoid .NET JIT crash.
            // The pointer value itself is sufficient — we only need to know it's non-NULL.
            Console.Error.WriteLine($"  [EXP095-{stage}] Method table at 0x{methodTablePtr:X16} (content dump skipped — EXP-096)");
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"  [EXP095-{stage}] Failed to dump context/method_table: {ex.Message}");
        }
    }

    /// <summary>
    /// Reads a null-terminated ASCII string from a guest address.
    /// Returns the string (truncated to maxLen) or an error message.
    /// </summary>
    private unsafe string Exp095ReadCString(ulong addr, int maxLen)
    {
        if (addr == 0 || addr < 0x1000)
            return $"<NULL: 0x{addr:X16}>";

        try
        {
            byte* p = (byte*)addr;
            var bytes = new System.Collections.Generic.List<byte>(maxLen);
            for (int i = 0; i < maxLen; i++)
            {
                byte b = p[i];
                if (b == 0) break;
                bytes.Add(b);
            }
            return System.Text.Encoding.ASCII.GetString(bytes.ToArray());
        }
        catch (Exception ex)
        {
            return $"<READ_ERROR: {ex.Message}>";
        }
    }
}
