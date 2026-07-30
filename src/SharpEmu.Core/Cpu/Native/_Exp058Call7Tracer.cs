// EXP-058: Runtime trace call #7 (0x804F23320) — the consumer candidate.
//
// EXP-057 identified 0x804F23320 as a strong consumer candidate because:
//   - It has loops with 0x38-byte stride (matching hash table entry size)
//   - It reads a context global at [0x808923D88]
//   - It was previously mis-classified as "epilogue" by EXP-041
//
// This tracer instruments:
//   1. 0x804F23320 (call #7 entry) — dump regs, stack args, context global
//   2. 0x804F238F0 (loop body) — log every iteration's args, count iterations
//   3. 0x804F2B4D0 (called with array) — log array ptr, count, entry size
//
// Goal: Confirm or deny whether call #7 populates the hash table at [0x801EF7610].

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-058: Call #7 consumer tracer =====

    // Call #7 target — the consumer candidate
    private const ulong Exp058_Call7Addr = 0x804F23320;
    private byte _exp058Call7OriginalByte;
    private bool _exp058Call7Patched;
    private int _exp058Call7HitCount;

    // Loop body inside call #7
    private const ulong Exp058_LoopBodyAddr = 0x804F238F0;
    private byte _exp058LoopBodyOriginalByte;
    private bool _exp058LoopBodyPatched;
    private int _exp058LoopBodyHitCount;

    // Array processor inside call #7
    private const ulong Exp058_ArrayProcAddr = 0x804F2B4D0;
    private byte _exp058ArrayProcOriginalByte;
    private bool _exp058ArrayProcPatched;
    private int _exp058ArrayProcHitCount;

    // Key addresses
    private const ulong Exp058_ContextGlobalAddr = 0x808923D88;
    private const ulong Exp058_HashTablePtrAddr = 0x801EF7610;
    private const ulong Exp058_MetaDataGlobalAddr = 0x801E51240;
    private const ulong Exp058_BssObjectAddr = 0x801EC0C78;

    // Track whether call #7 completed before crash
    private bool _exp058Call7Completed;
    private int _exp058CrashFuncHits;

    /// <summary>
    /// Installs INT3 at call #7, loop body, and array processor.
    /// Called from DirectExecutionBackend.Imports.cs after resolver completes.
    /// </summary>
    private unsafe void Exp058PatchCall7Tracers()
    {
        // Patch call #7 entry
        if (!_exp058Call7Patched)
        {
            try
            {
                var ptr = (byte*)Exp058_Call7Addr;
                uint fl = 0;
                if (VirtualProtect((void*)Exp058_Call7Addr, 16u, 64u, &fl))
                {
                    _exp058Call7OriginalByte = ptr[0];
                    ptr[0] = 0xCC;
                    _exp058Call7Patched = true;
                    Console.Error.WriteLine(
                        $"[EXP058-PATCH] call#7 at 0x{Exp058_Call7Addr:X16} patched with INT3 " +
                        $"(original byte=0x{_exp058Call7OriginalByte:X2})");
                    VirtualProtect((void*)Exp058_Call7Addr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp058_Call7Addr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP058] Failed to patch call#7: {ex.Message}");
            }
        }

        // Patch loop body
        if (!_exp058LoopBodyPatched)
        {
            try
            {
                var ptr = (byte*)Exp058_LoopBodyAddr;
                uint fl = 0;
                if (VirtualProtect((void*)Exp058_LoopBodyAddr, 16u, 64u, &fl))
                {
                    _exp058LoopBodyOriginalByte = ptr[0];
                    ptr[0] = 0xCC;
                    _exp058LoopBodyPatched = true;
                    Console.Error.WriteLine(
                        $"[EXP058-PATCH] loop_body at 0x{Exp058_LoopBodyAddr:X16} patched with INT3 " +
                        $"(original byte=0x{_exp058LoopBodyOriginalByte:X2})");
                    VirtualProtect((void*)Exp058_LoopBodyAddr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp058_LoopBodyAddr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP058] Failed to patch loop_body: {ex.Message}");
            }
        }

        // Patch array processor
        if (!_exp058ArrayProcPatched)
        {
            try
            {
                var ptr = (byte*)Exp058_ArrayProcAddr;
                uint fl = 0;
                if (VirtualProtect((void*)Exp058_ArrayProcAddr, 16u, 64u, &fl))
                {
                    _exp058ArrayProcOriginalByte = ptr[0];
                    ptr[0] = 0xCC;
                    _exp058ArrayProcPatched = true;
                    Console.Error.WriteLine(
                        $"[EXP058-PATCH] array_proc at 0x{Exp058_ArrayProcAddr:X16} patched with INT3 " +
                        $"(original byte=0x{_exp058ArrayProcOriginalByte:X2})");
                    VirtualProtect((void*)Exp058_ArrayProcAddr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp058_ArrayProcAddr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP058] Failed to patch array_proc: {ex.Message}");
            }
        }

        // Dump initial state of context global and hash table
        Console.Error.WriteLine("[EXP058-INIT-STATE] Dumping context global and hash table:");
        try
        {
            ulong ctxPtr = *(ulong*)Exp058_ContextGlobalAddr;
            Console.Error.WriteLine($"  [0x{Exp058_ContextGlobalAddr:X}] (context global) = 0x{ctxPtr:X16}");

            if (ctxPtr != 0)
            {
                // Dump first 0x100 bytes of context struct
                Console.Error.WriteLine($"  Context struct at 0x{ctxPtr:X16} (first 0x100 bytes):");
                byte* ctx = (byte*)ctxPtr;
                for (int i = 0; i < 0x100; i += 8)
                {
                    ulong val = *(ulong*)(ctx + i);
                    string cls = "";
                    if (val >= 0x804CD5000 && val < 0x808800000) cls = " (PRX)";
                    else if (val >= 0x800000000 && val < 0x804CD5000) cls = " (eboot)";
                    else if (val >= 0x600000000 && val < 0x700000000) cls = " (heap)";
                    else if (val == 0) cls = " (NULL)";
                    Console.Error.WriteLine($"    +0x{i:02X}: 0x{val:X16}{cls}");
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"  context global read failed: {ex.Message}");
        }

        try
        {
            ulong htPtr = *(ulong*)Exp058_HashTablePtrAddr;
            Console.Error.WriteLine($"  [0x{Exp058_HashTablePtrAddr:X}] (hash table ptr) = 0x{htPtr:X16}");
            if (htPtr != 0)
            {
                ulong entriesPtr = *(ulong*)htPtr;
                ulong mask = *(ulong*)(htPtr + 8);
                Console.Error.WriteLine($"    entries=0x{entriesPtr:X16} mask=0x{mask:X16}");
                if (entriesPtr != 0)
                {
                    int populated = 0;
                    for (int i = 0; i < 100; i++)
                    {
                        uint h = *(uint*)(entriesPtr + (ulong)i * 0x38);
                        if (h != 0xFFFFFFFF && h != 0) populated++;
                    }
                    Console.Error.WriteLine($"    populated_entries(0-99)={populated}");
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"  hash table read failed: {ex.Message}");
        }

        try
        {
            ulong meta = *(ulong*)Exp058_MetaDataGlobalAddr;
            ulong bssObj = *(ulong*)Exp058_BssObjectAddr;
            Console.Error.WriteLine($"  [0x{Exp058_MetaDataGlobalAddr:X}] (metadata global) = 0x{meta:X16}");
            Console.Error.WriteLine($"  [0x{Exp058_BssObjectAddr:X}] (BSS object) = 0x{bssObj:X16}");
        }
        catch { }
        Console.Error.Flush();
    }

    /// <summary>
    /// Handles INT3 from call #7 (0x804F23320).
    /// Dumps all registers, stack args, and context global.
    /// </summary>
    private unsafe bool Exp058TryHandleCall7Int3(void* contextRecord, ulong rip)
    {
        if (!_exp058Call7Patched) return false;
        if (rip - 1 != Exp058_Call7Addr) return false;

        int hitNum = Interlocked.Increment(ref _exp058Call7HitCount);
        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);

        // Read all registers
        ulong rax = ReadCtxU64(contextRecord, 120);
        ulong rbx = ReadCtxU64(contextRecord, 128);
        ulong rcx = ReadCtxU64(contextRecord, 136);
        ulong rdx = ReadCtxU64(contextRecord, 144);
        ulong rsi = ReadCtxU64(contextRecord, 184);
        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong r8 = ReadCtxU64(contextRecord, 208);
        ulong r9 = ReadCtxU64(contextRecord, 216);
        ulong r10 = ReadCtxU64(contextRecord, 224);
        ulong r11 = ReadCtxU64(contextRecord, 232);
        ulong r12 = ReadCtxU64(contextRecord, 240);
        ulong r13 = ReadCtxU64(contextRecord, 248);
        ulong r14 = ReadCtxU64(contextRecord, 256);
        ulong r15 = ReadCtxU64(contextRecord, 264);
        ulong rbp = ReadCtxU64(contextRecord, 160);

        // Read caller from stack
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP058-CALL7-ENTER] hit#{hitNum} caller=0x{callerRip:X16} tid={tid}");
        Console.Error.WriteLine(
            $"  RAX=0x{rax:X16} RBX=0x{rbx:X16} RCX=0x{rcx:X16} RDX=0x{rdx:X16}");
        Console.Error.WriteLine(
            $"  RSI=0x{rsi:X16} RDI=0x{rdi:X16} R8=0x{r8:X16} R9=0x{r9:X16}");
        Console.Error.WriteLine(
            $"  R10=0x{r10:X16} R11=0x{r11:X16} R12=0x{r12:X16} R13=0x{r13:X16}");
        Console.Error.WriteLine(
            $"  R14=0x{r14:X16} R15=0x{r15:X16} RBP=0x{rbp:X16} RSP=0x{rsp:X16}");

        // Dump context global
        try
        {
            ulong ctxPtr = *(ulong*)Exp058_ContextGlobalAddr;
            Console.Error.WriteLine($"  [0x{Exp058_ContextGlobalAddr:X}] (context) = 0x{ctxPtr:X16}");
            if (ctxPtr != 0)
            {
                // Dump first 0x80 bytes
                byte* ctx = (byte*)ctxPtr;
                for (int i = 0; i < 0x80; i += 8)
                {
                    ulong val = *(ulong*)(ctx + i);
                    string cls = "";
                    if (val == 0x8086E9000) cls = " <-- CodeReg!";
                    else if (val == 0x80885C580) cls = " <-- MetaReg!";
                    else if (val >= 0x804CD5000 && val < 0x808800000) cls = " (PRX)";
                    else if (val >= 0x800000000 && val < 0x804CD5000) cls = " (eboot)";
                    else if (val >= 0x600000000 && val < 0x700000000) cls = " (heap)";
                    Console.Error.WriteLine($"    ctx+0x{i:02X}: 0x{val:X16}{cls}");
                }
            }
        }
        catch { }

        // Dump hash table state BEFORE call #7
        try
        {
            ulong htPtr = *(ulong*)Exp058_HashTablePtrAddr;
            Console.Error.WriteLine($"  [0x{Exp058_HashTablePtrAddr:X}] (hash_table) = 0x{htPtr:X16}");
            if (htPtr != 0)
            {
                ulong entriesPtr = *(ulong*)htPtr;
                if (entriesPtr != 0)
                {
                    int populated = 0;
                    for (int i = 0; i < 100; i++)
                    {
                        uint h = *(uint*)(entriesPtr + (ulong)i * 0x38);
                        if (h != 0xFFFFFFFF && h != 0) populated++;
                    }
                    Console.Error.WriteLine($"    populated_entries(0-99) BEFORE call#7: {populated}");
                }
            }
        }
        catch { }

        // Dump stack arguments (beyond the 6 register args)
        Console.Error.WriteLine("  Stack arguments:");
        try
        {
            byte* sp = (byte*)rsp;
            for (int i = 1; i <= 6; i++)
            {
                ulong val = *(ulong*)(sp + i * 8);
                Console.Error.WriteLine($"    [rsp+0x{i*8:X2}] = 0x{val:X16}");
            }
        }
        catch { }
        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp058_Call7Addr;
        uint flNP = 0;
        if (VirtualProtect((void*)Exp058_Call7Addr, 16u, 64u, &flNP))
        {
            ptr[0] = _exp058Call7OriginalByte;
            VirtualProtect((void*)Exp058_Call7Addr, 16u, flNP, &flNP);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp058_Call7Addr, 16u);
        }
        _exp058Call7Patched = false;
        _exp058Call7Completed = false;  // will set true when we detect return

        WriteCtxU64(contextRecord, 248, Exp058_Call7Addr);
        return true;
    }

    /// <summary>
    /// Handles INT3 from loop body (0x804F238F0).
    /// Logs every iteration's arguments and counts total iterations.
    /// </summary>
    private unsafe bool Exp058TryHandleLoopBodyInt3(void* contextRecord, ulong rip)
    {
        if (!_exp058LoopBodyPatched) return false;
        if (rip - 1 != Exp058_LoopBodyAddr) return false;

        int iterNum = Interlocked.Increment(ref _exp058LoopBodyHitCount);
        int tid = Environment.CurrentManagedThreadId;

        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong rsi = ReadCtxU64(contextRecord, 184);
        ulong rdx = ReadCtxU64(contextRecord, 144);
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        // Only log first 5 and every 50th iteration
        if (iterNum <= 5 || iterNum % 50 == 0)
        {
            Console.Error.WriteLine(
                $"[EXP058-LOOP-ITER] iter#{iterNum} caller=0x{callerRip:X16} " +
                $"rdi=0x{rdi:X16} rsi=0x{rsi:X16} rdx=0x{rdx:X16}");

            // Try to read what rdi points to (the entry being processed)
            try
            {
                if (rdi != 0 && rdi >= 0x800000000)
                {
                    // Read first 0x38 bytes of the entry
                    byte* entry = (byte*)rdi;
                    Console.Error.Write("    entry bytes: ");
                    for (int i = 0; i < 0x38; i++)
                    {
                        Console.Error.Write($"{entry[i]:02X} ");
                    }
                    Console.Error.WriteLine();
                }
            }
            catch { }
            Console.Error.Flush();
        }

        // Restore and let it execute
        var ptr = (byte*)Exp058_LoopBodyAddr;
        uint flNP = 0;
        if (VirtualProtect((void*)Exp058_LoopBodyAddr, 16u, 64u, &flNP))
        {
            ptr[0] = _exp058LoopBodyOriginalByte;
            VirtualProtect((void*)Exp058_LoopBodyAddr, 16u, flNP, &flNP);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp058_LoopBodyAddr, 16u);
        }
        _exp058LoopBodyPatched = false;

        WriteCtxU64(contextRecord, 248, Exp058_LoopBodyAddr);
        return true;
    }

    /// <summary>
    /// Handles INT3 from array processor (0x804F2B4D0).
    /// Logs array pointer, count, and entry size.
    /// </summary>
    private unsafe bool Exp058TryHandleArrayProcInt3(void* contextRecord, ulong rip)
    {
        if (!_exp058ArrayProcPatched) return false;
        if (rip - 1 != Exp058_ArrayProcAddr) return false;

        int hitNum = Interlocked.Increment(ref _exp058ArrayProcHitCount);
        int tid = Environment.CurrentManagedThreadId;

        ulong rdi = ReadCtxU64(contextRecord, 176);  // array pointer
        ulong rsi = ReadCtxU64(contextRecord, 184);  // count or end
        ulong rdx = ReadCtxU64(contextRecord, 144);  // count or entry_size
        ulong rcx = ReadCtxU64(contextRecord, 136);  // entry_size or count
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        // Read hash table entries pointer for comparison
        ulong htEntriesPtr = 0;
        try
        {
            ulong htPtr = *(ulong*)Exp058_HashTablePtrAddr;
            if (htPtr != 0)
                htEntriesPtr = *(ulong*)htPtr;
        }
        catch { }

        bool matchesHashTable = (rdi == htEntriesPtr && rdi != 0);

        Console.Error.WriteLine(
            $"[EXP058-ARRAYPROC-ENTER] hit#{hitNum} caller=0x{callerRip:X16} tid={tid}");
        Console.Error.WriteLine(
            $"  rdi(array)=0x{rdi:X16} rsi=0x{rsi:X16} rdx=0x{rdx:X16} rcx=0x{rcx:X16}");
        Console.Error.WriteLine(
            $"  hash_table_entries=0x{htEntriesPtr:X16} matches_array={matchesHashTable}");

        // Check entry size: rsi = count * 0x38, so count = rsi / 0x38
        if (rsi != 0 && rsi % 0x38 == 0)
        {
            ulong count = rsi / 0x38;
            Console.Error.WriteLine($"  entry_size=0x38, count={count}");
        }

        // Dump first few entries of the array (BEFORE processing)
        try
        {
            if (rdi != 0 && rdi >= 0x600000000)
            {
                Console.Error.WriteLine("  First 3 entries BEFORE processing:");
                for (int i = 0; i < 3; i++)
                {
                    uint h = *(uint*)(rdi + (ulong)i * 0x38);
                    Console.Error.WriteLine($"    entry[{i}].hash = 0x{h:X8}");
                }
            }
        }
        catch { }
        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp058_ArrayProcAddr;
        uint flNP = 0;
        if (VirtualProtect((void*)Exp058_ArrayProcAddr, 16u, 64u, &flNP))
        {
            ptr[0] = _exp058ArrayProcOriginalByte;
            VirtualProtect((void*)Exp058_ArrayProcAddr, 16u, flNP, &flNP);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp058_ArrayProcAddr, 16u);
        }
        _exp058ArrayProcPatched = false;

        WriteCtxU64(contextRecord, 248, Exp058_ArrayProcAddr);
        return true;
    }
}
