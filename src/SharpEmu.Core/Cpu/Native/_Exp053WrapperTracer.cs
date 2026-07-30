// EXP-053: Trace the wrapper at 0x800805AE0 (il2cpp_codegen_register).
//
// This wrapper takes rdi = string pointer, calls insert at 0x800806940.
// It has 0 direct callers (called via function pointer).
// Goal: Determine if/when this wrapper is called on SharpEmu.
//
// Also tracks:
// - Once-init flag at 0x801E516F0 (read on every wrapper/writer/lookup entry)
// - Static table at 0x1CC0080 (dumped on first writer entry)
// - Insert function 0x800806940 (logs every call with key hash)

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-053: Wrapper / Insert / OnceInit tracing =====

    // Wrapper = il2cpp_codegen_register
    private const ulong Exp053_WrapperAddr = 0x800805AE0;
    private byte _exp053WrapperOriginalByte;
    private bool _exp053WrapperPatched;
    private int _exp053WrapperCallCount;
    private bool _exp053WrapperEverHit;

    // Insert = hash_insert (called by wrapper)
    private const ulong Exp053_InsertAddr = 0x800806940;
    private byte _exp053InsertOriginalByte;
    private bool _exp053InsertPatched;
    private int _exp053InsertCallCount;

    // Once-init flag (writer checks this before allocating)
    private const ulong Exp053_OnceInitFlagAddr = 0x801E516F0;
    private const ulong Exp053_HashTablePtrAddr = 0x801EF7610;  // CORRECTED from EXP-039
    private const ulong Exp053_HashTableStructAddr = 0x801E51618;
    private const ulong Exp053_StaticTableAddr = 0x801CC0080;
    private const ulong Exp053_StaticTableEnd = 0x801CE0080;

    // Global sequence counter for ordering
    private static long _exp053Seq;

    private static long GetExp053Seq() => Interlocked.Increment(ref _exp053Seq);

    /// <summary>
    /// Installs INT3 at the wrapper 0x800805AE0 and insert 0x800806940.
    /// Called from DirectExecutionBackend.Imports.cs after resolver completes.
    /// </summary>
    private unsafe void Exp053PatchWrapperAndInsert()
    {
        // Patch wrapper
        if (!_exp053WrapperPatched)
        {
            try
            {
                var ptr = (byte*)Exp053_WrapperAddr;
                uint fl = 0;
                if (VirtualProtect((void*)Exp053_WrapperAddr, 16u, 64u, &fl))
                {
                    _exp053WrapperOriginalByte = ptr[0];
                    ptr[0] = 0xCC;
                    _exp053WrapperPatched = true;
                    Console.Error.WriteLine(
                        $"[EXP053-PATCH] wrapper at 0x{Exp053_WrapperAddr:X16} patched with INT3 " +
                        $"(original byte=0x{_exp053WrapperOriginalByte:X2})");
                    VirtualProtect((void*)Exp053_WrapperAddr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp053_WrapperAddr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP053] Failed to patch wrapper: {ex.Message}");
            }
        }

        // Patch insert
        if (!_exp053InsertPatched)
        {
            try
            {
                var ptr = (byte*)Exp053_InsertAddr;
                uint fl = 0;
                if (VirtualProtect((void*)Exp053_InsertAddr, 16u, 64u, &fl))
                {
                    _exp053InsertOriginalByte = ptr[0];
                    ptr[0] = 0xCC;
                    _exp053InsertPatched = true;
                    Console.Error.WriteLine(
                        $"[EXP053-PATCH] insert at 0x{Exp053_InsertAddr:X16} patched with INT3 " +
                        $"(original byte=0x{_exp053InsertOriginalByte:X2})");
                    VirtualProtect((void*)Exp053_InsertAddr, 16u, fl, &fl);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp053_InsertAddr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP053] Failed to patch insert: {ex.Message}");
            }
        }

        // Dump static table first 0x100 bytes
        Console.Error.WriteLine($"[EXP053-STATIC-TABLE] Dumping first 0x100 bytes at 0x{Exp053_StaticTableAddr:X16}:");
        try
        {
            byte* tbl = (byte*)Exp053_StaticTableAddr;
            for (int i = 0; i < 0x100; i += 8)
            {
                ulong val = *(ulong*)(tbl + i);
                Console.Error.WriteLine($"  +0x{i:X4}: 0x{val:X16}");
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"  read failed: {ex.Message}");
        }

        // Dump current state of hash table pointer + once-init flag
        try
        {
            ulong htPtr = *(ulong*)Exp053_HashTablePtrAddr;
            byte onceFlag = *(byte*)Exp053_OnceInitFlagAddr;
            ulong htStruct = *(ulong*)Exp053_HashTableStructAddr;
            Console.Error.WriteLine(
                $"[EXP053-STATE-INIT] hash_table_ptr=0x{htPtr:X16} " +
                $"hash_struct=0x{htStruct:X16} once_init_flag=0x{onceFlag:X2}");
        }
        catch { }
        Console.Error.Flush();
    }

    /// <summary>
    /// Handles INT3 from the wrapper 0x800805AE0.
    /// Logs: caller, rdi (string ptr), string contents, hash table state, seq#.
    /// </summary>
    private unsafe bool Exp053TryHandleWrapperInt3(void* contextRecord, ulong rip)
    {
        if (!_exp053WrapperPatched) return false;
        if (rip - 1 != Exp053_WrapperAddr) return false;

        long seq = GetExp053Seq();
        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        // Args: rdi = string ptr, rsi = ?, rdx = ?, rcx = ?
        ulong rdi = ReadCtxU64(contextRecord, 176);  // CTX_RDI
        ulong rsi = ReadCtxU64(contextRecord, 184);  // CTX_RSI
        ulong rdx = ReadCtxU64(contextRecord, 192);  // CTX_RDX
        ulong rcx = ReadCtxU64(contextRecord, 200);  // CTX_RCX
        ulong r8  = ReadCtxU64(contextRecord, 208);  // CTX_R8
        ulong r9  = ReadCtxU64(contextRecord, 216);  // CTX_R9

        int callNum = Interlocked.Increment(ref _exp053WrapperCallCount);
        _exp053WrapperEverHit = true;

        // Read string contents (up to 256 bytes)
        string strContent = "<unreadable>";
        int strLen = 0;
        try
        {
            byte* sptr = (byte*)rdi;
            // Find null terminator (max 256 bytes)
            for (int i = 0; i < 256; i++)
            {
                if (sptr[i] == 0) { strLen = i; break; }
                if (i == 255) strLen = 256;
            }
            if (strLen > 0 && strLen <= 256)
            {
                byte[] bytes = new byte[strLen];
                for (int i = 0; i < strLen; i++) bytes[i] = sptr[i];
                strContent = System.Text.Encoding.ASCII.GetString(bytes);
            }
            else if (strLen == 0)
            {
                strContent = "<empty>";
            }
        }
        catch (Exception ex)
        {
            strContent = $"<read failed: {ex.Message}>";
        }

        // Read hash table state
        ulong htPtr = 0, htStruct = 0;
        byte onceFlag = 0;
        try { htPtr = *(ulong*)Exp053_HashTablePtrAddr; } catch { }
        try { htStruct = *(ulong*)Exp053_HashTableStructAddr; } catch { }
        try { onceFlag = *(byte*)Exp053_OnceInitFlagAddr; } catch { }

        // Count populated entries (first 100)
        int populated = 0;
        if (htPtr != 0)
        {
            try
            {
                ulong entriesPtr = *(ulong*)htPtr;
                if (entriesPtr != 0)
                {
                    for (int i = 0; i < 100; i++)
                    {
                        ulong entryHash = *(uint*)(entriesPtr + (ulong)i * 0x38);
                        if (entryHash != 0xFFFFFFFF && entryHash != 0)
                            populated++;
                    }
                }
            }
            catch { }
        }

        Console.Error.WriteLine(
            $"[EXP053-WRAPPER-ENTER] seq={seq} #{callNum} caller=0x{callerRip:X16} " +
            $"tid={tid} rdi=0x{rdi:X16} str=\"{strContent}\" len={strLen} " +
            $"rsi=0x{rsi:X16} rdx=0x{rdx:X16} rcx=0x{rcx:X16} r8=0x{r8:X16} r9=0x{r9:X16}");
        Console.Error.WriteLine(
            $"[EXP053-WRAPPER-STATE] hash_table=0x{htPtr:X16} struct=0x{htStruct:X16} " +
            $"once_flag=0x{onceFlag:X2} populated_entries(0-99)={populated}");

        // Dump return addresses (stack trace, 24 deep)
        Console.Error.WriteLine("[EXP053-WRAPPER-STACK] Return addresses:");
        try
        {
            byte* sp = (byte*)rsp;
            for (int i = 0; i < 24; i++)
            {
                ulong val = *(ulong*)(sp + i * 8);
                if (val >= 0x800000000 && val < 0x810000000)
                {
                    Console.Error.WriteLine($"  [rsp+0x{i*8:X2}] = 0x{val:X16}");
                }
            }
        }
        catch { }
        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp053_WrapperAddr;
        uint flNP = 0;
        if (VirtualProtect((void*)Exp053_WrapperAddr, 16u, 64u, &flNP))
        {
            ptr[0] = _exp053WrapperOriginalByte;
            VirtualProtect((void*)Exp053_WrapperAddr, 16u, flNP, &flNP);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp053_WrapperAddr, 16u);
        }
        _exp053WrapperPatched = false;

        WriteCtxU64(contextRecord, 248, Exp053_WrapperAddr);
        return true;
    }

    /// <summary>
    /// Handles INT3 from the insert 0x800806940.
    /// Logs: caller (should be wrapper at 0x80080602D), args, seq#.
    /// </summary>
    private unsafe bool Exp053TryHandleInsertInt3(void* contextRecord, ulong rip)
    {
        if (!_exp053InsertPatched) return false;
        if (rip - 1 != Exp053_InsertAddr) return false;

        long seq = GetExp053Seq();
        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        // Args: rdi = key, rsi = hash table struct, rdx = entry, rcx = ?
        ulong rdi = ReadCtxU64(contextRecord, 176);
        ulong rsi = ReadCtxU64(contextRecord, 184);
        ulong rdx = ReadCtxU64(contextRecord, 192);
        ulong rcx = ReadCtxU64(contextRecord, 200);

        int callNum = Interlocked.Increment(ref _exp053InsertCallCount);

        // Read string contents (key)
        string keyStr = "<unreadable>";
        int keyLen = 0;
        try
        {
            byte* sptr = (byte*)rdi;
            for (int i = 0; i < 256; i++)
            {
                if (sptr[i] == 0) { keyLen = i; break; }
                if (i == 255) keyLen = 256;
            }
            if (keyLen > 0 && keyLen <= 256)
            {
                byte[] bytes = new byte[keyLen];
                for (int i = 0; i < keyLen; i++) bytes[i] = sptr[i];
                keyStr = System.Text.Encoding.ASCII.GetString(bytes);
            }
        }
        catch { }

        Console.Error.WriteLine(
            $"[EXP053-INSERT-ENTER] seq={seq} #{callNum} caller=0x{callerRip:X16} " +
            $"tid={tid} rdi=0x{rdi:X16} key=\"{keyStr}\" len={keyLen} " +
            $"rsi=0x{rsi:X16} rdx=0x{rdx:X16} rcx=0x{rcx:X16}");
        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp053_InsertAddr;
        uint flNP = 0;
        if (VirtualProtect((void*)Exp053_InsertAddr, 16u, 64u, &flNP))
        {
            ptr[0] = _exp053InsertOriginalByte;
            VirtualProtect((void*)Exp053_InsertAddr, 16u, flNP, &flNP);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp053_InsertAddr, 16u);
        }
        _exp053InsertPatched = false;

        WriteCtxU64(contextRecord, 248, Exp053_InsertAddr);
        return true;
    }
}
