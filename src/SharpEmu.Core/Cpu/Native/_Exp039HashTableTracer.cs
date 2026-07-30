// EXP-039: Trace writes to the hash table pointer at 0x801EE7610.
//
// The hash table at 0x801EE7610 is NULL. We need to find what writes to it.
// Strategy: Install INT3 at the start of il2cpp_init's real init (0x804F04BA0),
// then single-step trace to find when 0x801EE7610 is written.
//
// Since single-stepping the entire il2cpp_init is too slow, we use a different
// approach: scan all code for MOV [0x801EE7610], <reg> patterns.

using System;
using System.Collections.Generic;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-039: Hash table write tracing =====

    private const ulong Exp039_HashTablePtrAddr = 0x801EE7610;
    private const ulong Exp039_GlobalPtrAddr = 0x801E51240;

    // Check and log the hash table state at key points
    private int _exp039StateLogCount;

    /// <summary>
    /// Logs the current state of the hash table and global pointers.
    /// Called from various hook points.
    /// </summary>
    public void Exp039LogState(string context)
    {
        _exp039StateLogCount++;
        if (_exp039StateLogCount > 100) return;  // limit

        try
        {
            ulong hashTablePtr = *(ulong*)Exp039_HashTablePtrAddr;
            ulong globalPtr = *(ulong*)Exp039_GlobalPtrAddr;
            Console.Error.WriteLine(
                $"[EXP039-STATE] #{_exp039StateLogCount} {context} " +
                $"hash_table=0x{hashTablePtr:X16} global=0x{globalPtr:X16}");
            Console.Error.Flush();
        }
        catch { }
    }

    /// <summary>
    /// Called from the il2cpp_init INT3 handler (EXP-036).
    /// Logs the state before il2cpp_init runs.
    /// </summary>
    public void Exp039OnIl2cppInitEnter()
    {
        Exp039LogState("il2cpp_init ENTER");
    }

    /// <summary>
    /// Called from the crash function INT3 handler (EXP-038).
    /// Logs the state when the crash function is called.
    /// </summary>
    public void Exp039OnCrashFuncEnter()
    {
        Exp039LogState("crash_func ENTER");
    }
}
