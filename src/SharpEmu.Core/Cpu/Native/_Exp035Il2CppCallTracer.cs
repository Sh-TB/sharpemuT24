// EXP-035: IL2CPP Runtime Call Tracer
//
// POLICY (per user):
//   - Evidence-first: trace ALL IL2CPP fake heap stub calls + NULL execute faults
//   - No silent zero returns
//   - Identify FIRST bad return value
//   - Implement minimum required runtime support only
//
// This file adds:
//   1. INT3-based instrumentation for fake heap stubs (per-function + return-fake-object + vtable)
//   2. Per-thread tracking of "last IL2CPP call" (function, return value, caller RIP)
//   3. Enhanced NULL execute fault logging (caller RIP, last IL2CPP call, thread)
//   4. Call count aggregation for top-N ranking
//
// USAGE:
//   Set SHARPEMU_EXP035_TRACE=1 to enable verbose per-call logging
//   Set SHARPEMU_EXP035_DUMP_AT=N to dump top-N calls every N calls
//   Logs go to stderr (capture with 2> /tmp/exp035_logs/call_trace.log)
//
// OUTPUT FORMAT:
//   [EXP035-CALL] func='il2cpp_thread_attach' stub=0x... caller=0x... tid=N ret=0x... count=N
//   [EXP035-NULL] #N caller=0x... last_il2cpp='il2cpp_thread_attach' last_ret=0x... tid=N
//   [EXP035-TOP]  rank=1 func='il2cpp_xxx' calls=N unique_callers=M last_ret=0x...

using System;
using System.Collections.Generic;
using System.Threading;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-035: IL2CPP call tracer state =====

    // Per-stub metadata: stub_addr -> (function_name, return_value)
    private readonly Dictionary<ulong, (string name, ulong returnValue)> _exp035StubInfo =
        new Dictionary<ulong, (string, ulong)>();

    // Call counts: function_name -> count
    private readonly Dictionary<string, long> _exp035CallCounts = new Dictionary<string, long>();

    // Unique caller RIPs per function: function_name -> set of caller RIPs
    private readonly Dictionary<string, HashSet<ulong>> _exp035UniqueCallers =
        new Dictionary<string, HashSet<ulong>>();

    // Per-thread last IL2CPP call info (for NULL execute fault correlation)
    [ThreadStatic]
    private static Exp035LastCall _exp035LastCall;

    // Vtable call count (when a fake vtable slot is invoked)
    private long _exp035VtableCallCount;

    // Return-fake-object stub call count
    private long _exp035ReturnFakeObjectCallCount;

    // Total traced calls
    private long _exp035TotalCallCount;

    // Last dump threshold (for periodic dumps)
    private long _exp035NextDumpAt;

    // Config
    private static readonly bool _exp035TraceEnabled =
        Environment.GetEnvironmentVariable("SHARPEMU_EXP035_TRACE") == "1";
    private static readonly long _exp035DumpInterval =
        long.TryParse(Environment.GetEnvironmentVariable("SHARPEMU_EXP035_DUMP_AT"), out var d) && d > 0
            ? d : 0;

    // Special stub offsets (must match DirectExecutionBackend.Imports.cs)
    // We add a new "vtable tracer" stub at offset 0x1900
    private const ulong Exp035VtableTracerStubOffset = 0x1900;
    private const ulong Exp035ReturnFakeObjectStubOffset = 0x1800;
    private const ulong Exp035ReturnZeroStubOffset = 0x1000;
    private const ulong Exp035StubsBase = 0x2000;

    private struct Exp035LastCall
    {
        public string FunctionName;
        public ulong ReturnValue;
        public ulong CallerRip;
        public long Timestamp;
    }

    // ===== EXP-035: Stub registration =====

    /// <summary>
    /// Registers a per-function fake heap stub so the INT3 handler can look it up.
    /// Called from GenerateIl2CppStub after writing the INT3 byte.
    /// </summary>
    private void Exp035RegisterStub(ulong stubAddr, string name, ulong returnValue)
    {
        lock (_exp035StubInfo)
        {
            _exp035StubInfo[stubAddr] = (name, returnValue);
        }
    }

    /// <summary>
    /// Installs the vtable tracer stub (single INT3 byte) and returns its address.
    /// Called from InitIl2CppHeap.
    /// </summary>
    private unsafe ulong Exp035InstallVtableTracerStub()
    {
        if (_il2cppHeap == 0) return 0;
        var ptr = (byte*)_il2cppHeap;
        var stubAddr = _il2cppHeap + Exp035VtableTracerStubOffset;
        ptr[Exp035VtableTracerStubOffset] = 0xCC; // INT3
        // Register in stub info so INT3 handler recognizes it
        Exp035RegisterStub(stubAddr, "<vtable_call>", 0);
        return stubAddr;
    }

    /// <summary>
    /// Writes an INT3-only stub (1 byte) for the given function.
    /// Replaces the previous "mov rax, imm64; ret" 11-byte stub.
    /// The INT3 handler will set RAX, pop return address, and resume.
    /// </summary>
    private unsafe void Exp035WriteInt3Stub(ulong stubAddr, string name, ulong returnValue)
    {
        var ptr = (byte*)stubAddr;
        ptr[0] = 0xCC; // INT3
        // Remaining 15 bytes are padding (don't care — handler skips them)
        Exp035RegisterStub(stubAddr, name, returnValue);
    }

    /// <summary>
    /// Writes the INT3-based return-fake-object stub.
    /// The INT3 handler will set RAX = fake object address.
    /// </summary>
    private unsafe void Exp035WriteReturnFakeObjectInt3Stub()
    {
        if (_il2cppHeap == 0) return;
        var ptr = (byte*)_il2cppHeap;
        ptr[Exp035ReturnFakeObjectStubOffset] = 0xCC; // INT3
        Exp035RegisterStub(
            _il2cppHeap + Exp035ReturnFakeObjectStubOffset,
            "<return_fake_object>",
            _il2cppHeap + Il2CppObjectOffset);
    }

    // ===== EXP-035: INT3 handler =====

    /// <summary>
    /// Tries to handle an INT3 trap originating from our IL2CPP fake heap.
    /// Returns true if handled (caller should return -1 to continue execution).
    /// </summary>
    private unsafe bool Exp035TryHandleIl2CppInt3(void* contextRecord, ulong rip)
    {
        if (_il2cppHeap == 0) return false;

        // INT3 advances RIP by 1, so the stub starts at rip - 1
        ulong stubAddr = rip - 1;

        // Fast range check: is this within our heap?
        if (stubAddr < _il2cppHeap || stubAddr >= _il2cppHeap + Il2CppHeapSize)
            return false;

        // Read return address from RSP[0]
        ulong rsp = ReadCtxU64(contextRecord, 152); // CTX_RSP = 152
        ulong callerRip = 0;
        try
        {
            callerRip = *(ulong*)rsp;
        }
        catch
        {
            // If we can't read the return address, bail
            return false;
        }

        // Look up stub info
        string funcName;
        ulong returnValue;

        // Check special stubs first
        if (stubAddr == _il2cppHeap + Exp035VtableTracerStubOffset)
        {
            funcName = "<vtable_call>";
            returnValue = 0;
            Interlocked.Increment(ref _exp035VtableCallCount);
        }
        else if (stubAddr == _il2cppHeap + Exp035ReturnFakeObjectStubOffset)
        {
            funcName = "<return_fake_object>";
            returnValue = _il2cppHeap + Il2CppObjectOffset;
            Interlocked.Increment(ref _exp035ReturnFakeObjectCallCount);
        }
        else if (stubAddr == _il2cppHeap + Exp035ReturnZeroStubOffset)
        {
            // Shouldn't happen — return-zero stub is xor eax, eax; ret (no INT3)
            // But just in case:
            funcName = "<return_zero>";
            returnValue = 0;
        }
        else
        {
            // Per-function stub — look up in dictionary
            lock (_exp035StubInfo)
            {
                if (!_exp035StubInfo.TryGetValue(stubAddr, out var info))
                {
                    // Unknown stub in our range — log and return 0
                    funcName = $"<unknown_stub@0x{stubAddr:X16}>";
                    returnValue = 0;
                }
                else
                {
                    funcName = info.name;
                    returnValue = info.returnValue;
                }
            }
        }

        // Update call counts
        long count;
        lock (_exp035CallCounts)
        {
            _exp035CallCounts.TryGetValue(funcName, out var c);
            c++;
            _exp035CallCounts[funcName] = c;
            count = c;

            if (!_exp035UniqueCallers.ContainsKey(funcName))
                _exp035UniqueCallers[funcName] = new HashSet<ulong>();
            _exp035UniqueCallers[funcName].Add(callerRip);
        }

        long total = Interlocked.Increment(ref _exp035TotalCallCount);

        // Update per-thread last call info
        _exp035LastCall.FunctionName = funcName;
        _exp035LastCall.ReturnValue = returnValue;
        _exp035LastCall.CallerRip = callerRip;
        _exp035LastCall.Timestamp = total;

        // Verbose per-call logging (if enabled, or first 10, or every 10000th)
        if (_exp035TraceEnabled || total <= 10 || total % 10000 == 0)
        {
            int tid = Environment.CurrentManagedThreadId;
            Console.Error.WriteLine(
                $"[EXP035-CALL] #{total} func='{funcName}' stub=0x{stubAddr:X16} " +
                $"caller=0x{callerRip:X16} tid={tid} ret=0x{returnValue:X16} count={count}");
            Console.Error.Flush();
        }

        // Periodic dump
        if (_exp035DumpInterval > 0 && total >= _exp035NextDumpAt)
        {
            _exp035NextDumpAt = total + _exp035DumpInterval;
            Exp035DumpTopCalls(20);
        }

        // Set RAX = return value, RIP = caller_rip, RSP += 8 (pop return address)
        WriteCtxU64(contextRecord, 120, returnValue); // CTX_RAX = 120
        WriteCtxU64(contextRecord, 248, callerRip);   // CTX_RIP = 248
        WriteCtxU64(contextRecord, 152, rsp + 8);     // CTX_RSP = 152
        return true;
    }

    // ===== EXP-035: NULL execute fault enhanced logging =====

    /// <summary>
    /// Logs enhanced NULL execute fault info: caller RIP, last IL2CPP call, thread,
    /// AND key registers (RBX, RDI, RSI, RDX, RCX) to help identify the object
    /// whose function pointer was NULL.
    /// </summary>
    private void Exp035LogNullExecuteFault(void* contextRecord, int recoveryNum)
    {
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        // Read key registers (Win64 CONTEXT offsets)
        ulong rax = ReadCtxU64(contextRecord, 120);
        ulong rcx = ReadCtxU64(contextRecord, 128);
        ulong rdx = ReadCtxU64(contextRecord, 136);
        ulong rbx = ReadCtxU64(contextRecord, 144);
        ulong rbp = ReadCtxU64(contextRecord, 160);
        ulong rsi = ReadCtxU64(contextRecord, 168);
        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong r8  = ReadCtxU64(contextRecord, 184);
        ulong r9  = ReadCtxU64(contextRecord, 192);

        int tid = Environment.CurrentManagedThreadId;
        var last = _exp035LastCall;

        // Try to read [rbx + 0xf8] (the NULL function pointer) and nearby fields
        // to understand the object layout
        ulong rbx_field_f8 = 0, rbx_field_100 = 0, rbx_field_108 = 0, rbx_field_70 = 0;
        bool rbx_readable = false;
        if (rbx != 0 && rbx >= 0x1000)
        {
            try
            {
                rbx_field_f8  = *(ulong*)(rbx + 0xf8);
                rbx_field_100 = *(ulong*)(rbx + 0x100);
                rbx_field_108 = *(ulong*)(rbx + 0x108);
                rbx_field_70  = *(ulong*)(rbx + 0x70);
                rbx_readable = true;
            }
            catch { }
        }

        Console.Error.WriteLine(
            $"[EXP035-NULL] #{recoveryNum} caller=0x{callerRip:X16} " +
            $"last_il2cpp='{last.FunctionName ?? "<none>"}' " +
            $"last_ret=0x{last.ReturnValue:X16} " +
            $"tid={tid}");
        Console.Error.WriteLine(
            $"[EXP035-NULL]   regs: rax=0x{rax:X16} rbx=0x{rbx:X16} rcx=0x{rcx:X16} " +
            $"rdx=0x{rdx:X16} rsi=0x{rsi:X16} rdi=0x{rdi:X16} rbp=0x{rbp:X16} " +
            $"r8=0x{r8:X16} r9=0x{r9:X16} rsp=0x{rsp:X16}");
        if (rbx_readable)
        {
            Console.Error.WriteLine(
                $"[EXP035-NULL]   [rbx+0x70]=0x{rbx_field_70:X16} (refcount?) " +
                $"[rbx+0xf8]=0x{rbx_field_f8:X16} (func_ptr!) " +
                $"[rbx+0x100]=0x{rbx_field_100:X16} (arg) " +
                $"[rbx+0x108]=0x{rbx_field_108:X16} (flag)");

            // EXP-035: Dump first 0x110 bytes of the object to understand its layout.
            // Only do this for the first few NULL executes to avoid spam.
            if (recoveryNum <= 3)
            {
                try
                {
                    Console.Error.WriteLine($"[EXP035-NULL]   === Object dump at rbx=0x{rbx:X16} (first 0x110 bytes) ===");
                    byte* objPtr = (byte*)rbx;
                    for (int off = 0; off < 0x110; off += 16)
                    {
                        ulong v0 = *(ulong*)(objPtr + off);
                        ulong v1 = *(ulong*)(objPtr + off + 8);
                        Console.Error.WriteLine(
                            $"[EXP035-NULL]   +0x{off:X3}: 0x{v0:X16} 0x{v1:X16}");
                    }
                }
                catch { }

                // Also try to read r9 as a string (it might be a type name)
                if (r9 != 0 && r9 >= 0x800000000 && r9 < 0x810000000)
                {
                    try
                    {
                        byte* strPtr = (byte*)r9;
                        byte[] strBytes = new byte[64];
                        for (int i = 0; i < 64; i++)
                        {
                            strBytes[i] = strPtr[i];
                            if (strBytes[i] == 0) { strBytes = strBytes[..i]; break; }
                        }
                        string str = System.Text.Encoding.ASCII.GetString(strBytes);
                        Console.Error.WriteLine($"[EXP035-NULL]   r9 string @0x{r9:X16}: '{str}'");
                    }
                    catch { }
                }
            }
        }
        Console.Error.Flush();
    }

    // ===== EXP-035: Top-N dump =====

    /// <summary>
    /// Dumps the top-N most-called IL2CPP functions.
    /// Called periodically and at process exit.
    /// </summary>
    public void Exp035DumpTopCalls(int n)
    {
        Console.Error.WriteLine($"[EXP035-TOP] === Top {n} IL2CPP calls (total={_exp035TotalCallCount}) ===");
        List<KeyValuePair<string, long>> sorted;
        lock (_exp035CallCounts)
        {
            sorted = new List<KeyValuePair<string, long>>(_exp035CallCounts);
        }
        sorted.Sort((a, b) => b.Value.CompareTo(a.Value));

        int rank = 1;
        foreach (var entry in sorted)
        {
            if (rank > n) break;
            int uniqueCallers = 0;
            lock (_exp035CallCounts)
            {
                if (_exp035UniqueCallers.TryGetValue(entry.Key, out var set))
                    uniqueCallers = set.Count;
            }
            ulong lastRet = 0;
            // Try to find last return value from stub info
            lock (_exp035StubInfo)
            {
                foreach (var si in _exp035StubInfo.Values)
                {
                    if (si.name == entry.Key)
                    {
                        lastRet = si.returnValue;
                        break;
                    }
                }
            }
            Console.Error.WriteLine(
                $"[EXP035-TOP] rank={rank} func='{entry.Key}' calls={entry.Value} " +
                $"unique_callers={uniqueCallers} ret=0x{lastRet:X16}");
            rank++;
        }

        // Also dump vtable and return-fake-object counts
        Console.Error.WriteLine(
            $"[EXP035-TOP] vtable_calls={_exp035VtableCallCount} " +
            $"return_fake_object_calls={_exp035ReturnFakeObjectCallCount} " +
            $"null_execute_recoveries={_nullExecuteRecoveries}");
        Console.Error.Flush();
    }

    /// <summary>
    /// Final dump — call from process exit or crash handler.
    /// </summary>
    public void Exp035FinalDump()
    {
        Console.Error.WriteLine("[EXP035] === FINAL DUMP ===");
        Exp035DumpTopCalls(50);
        Console.Error.WriteLine(
            $"[EXP035] total_calls={_exp035TotalCallCount} " +
            $"vtable_calls={_exp035VtableCallCount} " +
            $"return_fake_object_calls={_exp035ReturnFakeObjectCallCount} " +
            $"null_execute_recoveries={_nullExecuteRecoveries}");
        Console.Error.Flush();
    }
}
