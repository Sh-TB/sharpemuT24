// EXP-044: Verify PRX fini_array entries at runtime.
//
// The PRX DT_INIT iterates fini_array entries at startup.
// These have RELATIVE relocations that set them to function pointers.
// Need to verify SharpEmu applies these relocations.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    private const ulong Exp044_FiniArrayEnd = 0x8089247D8; // End of fini_array (exclusive)

    /// <summary>
    /// Dumps the PRX fini_array entries at runtime.
    /// Called from the real_init INT3 handler.
    /// </summary>
    public void Exp044DumpFiniArray()
    {
        try
        {
            Console.Error.WriteLine("[EXP044-FINI_ARRAY] Dumping PRX fini_array entries:");
            // The fini_array is iterated backwards from 0x8089247D8.
            // Check 16 entries (8 bytes each) backwards.
            int nonZero = 0;
            for (int i = 1; i <= 16; i++)
            {
                ulong addr = Exp044_FiniArrayEnd - (ulong)i * 8;
                ulong val = *(ulong*)addr;
                if (val != 0)
                {
                    nonZero++;
                    Console.Error.WriteLine(
                        $"  [0x{addr:X}] = 0x{val:X} *** NON-ZERO (will be called by DT_INIT) ***");
                }
                else
                {
                    Console.Error.WriteLine(
                        $"  [0x{addr:X}] = 0x0 (NULL, skipped)");
                }
            }
            Console.Error.WriteLine($"  Non-zero entries: {nonZero}/16");
            Console.Error.Flush();
        }
        catch { }
    }
}
