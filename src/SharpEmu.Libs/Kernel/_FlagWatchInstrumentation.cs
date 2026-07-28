// Flag Watch Instrumentation — polls [rbx+0x19] at every import dispatch
// to find the FIRST write to the resolver flag.

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

public static class FlagWatchInstrumentation
{
    public const ulong ResolverListHeadPtr = 0x808B53708;

    private static ulong _flagAddress;
    private static byte _lastFlagValue = 0xFF;
    private static bool _flagAddressFound;
    private static long _importCounter;
    private static long _flagChangeCount;
    private static string _lastImportNid = "(none)";
    private static ulong _lastImportRetAddr;

    public static void Initialize(CpuContext ctx)
    {
        // Try to initialize (or re-initialize) the flag address
        try
        {
            if (ctx.TryReadUInt64(ResolverListHeadPtr, out ulong listHead) && listHead != 0)
            {
                if (ctx.TryReadUInt64(listHead + 8, out ulong firstNode) && firstNode != 0)
                {
                    if (!_flagAddressFound)
                    {
                        _flagAddress = firstNode + 0x19;
                        byte flagVal = 0;
                        ctx.TryReadByte(_flagAddress, out flagVal);
                        _lastFlagValue = flagVal;
                        _flagAddressFound = true;
                        Console.Error.WriteLine(
                            $"[FLAG-WATCH] Init: list_head=0x{listHead:x} first_node=0x{firstNode:x} " +
                            $"flag_addr=0x{_flagAddress:x} initial_value={flagVal}");
                    }
                }
            }
        }
        catch { }
    }

    public static void PollAtImport(CpuContext ctx, string nid, ulong retAddr)
    {
        Initialize(ctx);
        if (!_flagAddressFound) return;

        _importCounter++;

        try
        {
            byte currentVal = 0;
            ctx.TryReadByte(_flagAddress, out currentVal);

            if (currentVal != _lastFlagValue)
            {
                _flagChangeCount++;
                Console.Error.WriteLine(
                    $"[FLAG-WATCH] CHANGE #{_flagChangeCount} at import #{_importCounter}: " +
                    $"flag 0x{_flagAddress:x} = {_lastFlagValue} -> {currentVal} " +
                    $"(prev_import nid={_lastImportNid} ret=0x{_lastImportRetAddr:x}, " +
                    $"curr_import nid={nid} ret=0x{retAddr:x})");
                _lastFlagValue = currentVal;
            }

            _lastImportNid = nid;
            _lastImportRetAddr = retAddr;
        }
        catch { }
    }

    public static void DumpResolverNodes(CpuContext ctx, string label)
    {
        Console.Error.WriteLine($"[FLAG-WATCH] === RESOLVER NODE DUMP ({label}) ===");
        Initialize(ctx);
        if (!_flagAddressFound)
        {
            Console.Error.WriteLine("[FLAG-WATCH] Cannot dump — flag address not initialized (list head still 0?)");
            return;
        }

        try
        {
            if (!ctx.TryReadUInt64(ResolverListHeadPtr, out ulong listHead))
            {
                Console.Error.WriteLine("[FLAG-WATCH] Cannot read list head pointer");
                return;
            }
            Console.Error.WriteLine($"[FLAG-WATCH] List head struct: 0x{listHead:x}");

            if (listHead == 0 || !ctx.TryReadUInt64(listHead + 8, out ulong firstNode))
            {
                Console.Error.WriteLine("[FLAG-WATCH] Cannot read first node");
                return;
            }
            Console.Error.WriteLine($"[FLAG-WATCH] First node: 0x{firstNode:x}");

            ulong currentNode = firstNode;
            int nodeCount = 0;
            while (currentNode != 0 && nodeCount < 500)
            {
                nodeCount++;

                ulong nextPtr = 0, symbolPtr = 0, funcPtr = 0, field10 = 0, field18 = 0;
                byte flag18 = 0, flag19 = 0, flag1a = 0;

                try { ctx.TryReadUInt64(currentNode + 0x00, out nextPtr); } catch { }
                try { ctx.TryReadUInt64(currentNode + 0x08, out field10); } catch { }
                try { ctx.TryReadUInt64(currentNode + 0x10, out symbolPtr); } catch { }
                try { ctx.TryReadUInt64(currentNode + 0x18, out field18); } catch { }
                try { ctx.TryReadUInt64(currentNode + 0x20, out funcPtr); } catch { }
                try { ctx.TryReadByte(currentNode + 0x18, out flag18); } catch { }
                try { ctx.TryReadByte(currentNode + 0x19, out flag19); } catch { }
                try { ctx.TryReadByte(currentNode + 0x1a, out flag1a); } catch { }

                string symbolName = "<null>";
                if (symbolPtr != 0)
                {
                    try
                    {
                        var nameBytes = new byte[256];
                        int len = 0;
                        for (int i = 0; i < 256; i++)
                        {
                            byte b;
                            if (!ctx.TryReadByte(symbolPtr + (ulong)i, out b)) break;
                            if (b == 0) break;
                            nameBytes[i] = b;
                            len++;
                        }
                        if (len > 0)
                            symbolName = System.Text.Encoding.ASCII.GetString(nameBytes, 0, len);
                    }
                    catch { }
                }

                Console.Error.WriteLine(
                    $"[FLAG-WATCH] Node #{nodeCount} @0x{currentNode:x}: " +
                    $"next=0x{nextPtr:x} field[0x08]=0x{field10:x} " +
                    $"symbol_ptr=0x{symbolPtr:x} name='{symbolName}' " +
                    $"func_ptr=0x{funcPtr:x} " +
                    $"[0x18]={flag18} [0x19]={flag19} [0x1a]={flag1a}");

                if (nextPtr == 0 || nextPtr == currentNode) break;
                currentNode = nextPtr;
            }

            Console.Error.WriteLine($"[FLAG-WATCH] Total nodes: {nodeCount}");
            Console.Error.WriteLine($"[FLAG-WATCH] === RESOLVER NODE DUMP COMPLETE ===");
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"[FLAG-WATCH] Dump error: {e.Message}");
        }
    }
}
