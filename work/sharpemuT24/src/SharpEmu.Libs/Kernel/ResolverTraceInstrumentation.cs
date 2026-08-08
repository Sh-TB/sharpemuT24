// Resolver Trace Instrumentation — LOG ONLY, NO BEHAVIOR CHANGE
//
// This file adds logging to two HLE stubs:
// 1. Il2cppApiRegisterSymbols (called at Import#2083, BEFORE the wrapper's 232 resolver calls)
// 2. UnityMonoSetUserMallocMutex (called at Import#2084, AFTER the wrapper returned)
//
// The logging captures:
// - Pre-wrapper snapshot of 125 global variables (where resolver results are stored)
// - Pre-wrapper snapshot of the resolver's linked list head + first node's [rbx+0x19] flag
// - Post-wrapper comparison: how many globals changed, what are their new values
// - Post-wrapper check of the resolver's [rbx+0x19] flags
//
// Return values of both stubs are UNCHANGED (still return 0).

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

public static class ResolverTraceInstrumentation
{
    // 125 global variable addresses where the wrapper stores resolver results
    // (extracted from static disassembly: each 'mov [rip+X], rax' after 'call 0x8019374d0')
    private static readonly ulong[] ResolverStoreAddresses = new ulong[]
    {
        0x801ed6320, 0x801ed6328, 0x801ed6330, 0x801ed6338, 0x801ed6340,
        0x801ed6348, 0x801ed6350, 0x801ed6358, 0x801ed6360, 0x801ed6368,
        0x801ed6370, 0x801ed6378, 0x801ed6380, 0x801ed6388, 0x801ed6390,
        0x801ed6398, 0x801ed63a0, 0x801ed63a8, 0x801ed63b0, 0x801ed63b8,
        0x801ed63c0, 0x801ed63c8, 0x801ed63d0, 0x801ed63d8, 0x801ed63e0,
        0x801ed63e8, 0x801ed63f0, 0x801ed63f8, 0x801ed6400, 0x801ed6408,
        0x801ed6410, 0x801ed6418, 0x801ed6420, 0x801ed6428, 0x801ed6430,
        0x801ed6438, 0x801ed6440, 0x801ed6448, 0x801ed6450, 0x801ed6458,
        0x801ed6460, 0x801ed6468, 0x801ed6470, 0x801ed6478, 0x801ed6480,
        0x801ed6488, 0x801ed6490, 0x801ed6498, 0x801ed64a0, 0x801ed64a8,
        0x801ed64b0, 0x801ed64b8, 0x801ed64c0, 0x801ed64c8, 0x801ed64d0,
        0x801ed64d8, 0x801ed64e0, 0x801ed64e8, 0x801ed64f0, 0x801ed64f8,
        0x801ed6500, 0x801ed6508, 0x801ed6510, 0x801ed6518, 0x801ed6520,
        0x801ed6528, 0x801ed6530, 0x801ef1e48, 0x801ed6538, 0x801ed6540,
        0x801ed6548, 0x801ed6550, 0x801ed6558, 0x801ed6560, 0x801ed6568,
        0x801ed6570, 0x801ed6578, 0x801ed6580, 0x801ed6588, 0x801ed6590,
        0x801ed6598, 0x801ed65a0, 0x801ed65a8, 0x801ed65b0, 0x801ed65b8,
        0x801ed65c0, 0x801ed65c8, 0x801ed65d0, 0x801ed65d8, 0x801ed65e0,
        0x801ed65e8, 0x801ed65f0, 0x801eef9c0, 0x801ed65f8, 0x801ed6600,
        0x801ed6608, 0x801ed6610, 0x801ed6618, 0x801ed6620, 0x801ed6628,
        0x801ed6630, 0x801ed6638, 0x801ed6640, 0x801ed6648, 0x801ed6650,
        0x801ed6658, 0x801ed6660, 0x801ed6668, 0x801ed6670, 0x801ed6678,
        0x801ed6680, 0x801ed6688, 0x801ed6690, 0x801ed6698, 0x801ed66a0,
        0x801ed66a8, 0x801eee0b8, 0x801ed66b0, 0x801ed66b8, 0x801ed66c0,
        0x801ed66c8, 0x801ed66d0, 0x801ed66d8, 0x801ed66e0, 0x801ed66e8,
    };

    // Resolver linked list head pointer (in Il2cppUserAssemblies.prx data section)
    // Computed: 0x804ED9BA2 + 0x3c79b66 = 0x808B53708
    private const ulong ResolverListHeadPtr = 0x808B53708;

    // Resolver function entry (for reference)
    private const ulong ResolverEntryVA = 0x804ED9B90;

    // Snapshot storage
    private static ulong[]? _preSnapshot;
    private static int _preNonNullCount;
    private static bool _snapshotTaken;

    // Linked list node flags snapshot
    private static int _preListNodesChecked;
    private static int _preListFlagsSet;

    /// <summary>
    /// Called from Il2cppApiRegisterSymbols (Import#2083, BEFORE wrapper's 232 resolver calls).
    /// Takes a snapshot of all 125 global variables + resolver list flags.
    /// </summary>
    public static void TakePreWrapperSnapshot(CpuContext ctx)
    {
        _preSnapshot = new ulong[ResolverStoreAddresses.Length];
        _preNonNullCount = 0;

        Console.Error.WriteLine($"[RESOLVER-TRACE] === PRE-WRAPPER SNAPSHOT (Import#2083: il2cpp_api_register_symbols) ===");
        Console.Error.WriteLine($"[RESOLVER-TRACE] Snapshotting {ResolverStoreAddresses.Length} global variables (where resolver results are stored)");
        Console.Error.WriteLine($"[RESOLVER-TRACE] Resolver function entry: 0x{ResolverEntryVA:x}");
        Console.Error.WriteLine($"[RESOLVER-TRACE] Resolver list head pointer: 0x{ResolverListHeadPtr:x}");

        for (int i = 0; i < ResolverStoreAddresses.Length; i++)
        {
            ulong addr = ResolverStoreAddresses[i];
            ulong val = 0;
            try
            {
                ctx.TryReadUInt64(addr, out val);
            }
            catch { }
            _preSnapshot[i] = val;
            if (val != 0)
                _preNonNullCount++;
        }

        Console.Error.WriteLine($"[RESOLVER-TRACE] Pre-wrapper: {_preNonNullCount}/{ResolverStoreAddresses.Length} globals are non-zero");

        // Also check the resolver's linked list
        _preListNodesChecked = 0;
        _preListFlagsSet = 0;
        try
        {
            // Read list head pointer
            if (ctx.TryReadUInt64(ResolverListHeadPtr, out ulong listHead))
            {
                Console.Error.WriteLine($"[RESOLVER-TRACE] Resolver list head struct: 0x{listHead:x}");

                // [listHead + 8] = first node pointer
                if (listHead != 0 && ctx.TryReadUInt64(listHead + 8, out ulong firstNode))
                {
                    Console.Error.WriteLine($"[RESOLVER-TRACE] First list node: 0x{firstNode:x}");

                    // Walk the linked list (up to 300 nodes for safety)
                    ulong currentNode = firstNode;
                    for (int n = 0; n < 300 && currentNode != 0; n++)
                    {
                        _preListNodesChecked++;

                        // Read [currentNode + 0x19] (the matched flag)
                        byte flag = 0;
                        try { ctx.TryReadByte(currentNode + 0x19, out flag); } catch { }
                        if (flag != 0)
                            _preListFlagsSet++;

                        // Read [currentNode] (next node pointer) — but this might be at offset 0 or another offset
                        // From the disassembly: mov rbx, [rcx] where rcx = rbx+0x10 or rbx
                        // The linked list traversal is: mov rbx, [rcx] where rcx = rbx+0x10 (if cmovns) or rbx
                        // For simplicity, try [currentNode] as next pointer
                        ulong nextNode = 0;
                        try { ctx.TryReadUInt64(currentNode, out nextNode); } catch { }

                        if (nextNode == currentNode || nextNode == 0)
                            break;
                        currentNode = nextNode;
                    }

                    Console.Error.WriteLine($"[RESOLVER-TRACE] Pre-wrapper: walked {_preListNodesChecked} list nodes, {_preListFlagsSet} have [rbx+0x19] flag set");
                }
            }
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"[RESOLVER-TRACE] List walk error: {e.Message}");
        }

        _snapshotTaken = true;
        Console.Error.WriteLine($"[RESOLVER-TRACE] === PRE-WRAPPER SNAPSHOT COMPLETE ===");
    }

    /// <summary>
    /// Called from UnityMonoSetUserMallocMutex (Import#2084, AFTER wrapper returned).
    /// Compares current state with pre-wrapper snapshot.
    /// </summary>
    public static void ComparePostWrapper(CpuContext ctx)
    {
        Console.Error.WriteLine($"[RESOLVER-TRACE] === POST-WRAPPER COMPARISON (Import#2084: unity_mono_set_user_malloc_mutex) ===");

        if (!_snapshotTaken || _preSnapshot == null)
        {
            Console.Error.WriteLine($"[RESOLVER-TRACE] ERROR: No pre-wrapper snapshot was taken!");
            return;
        }

        int changedCount = 0;
        int postNonNullCount = 0;
        int wasZeroNowNonZero = 0;
        int wasNonZeroNowDifferent = 0;

        for (int i = 0; i < ResolverStoreAddresses.Length; i++)
        {
            ulong addr = ResolverStoreAddresses[i];
            ulong preVal = _preSnapshot[i];
            ulong postVal = 0;
            try { ctx.TryReadUInt64(addr, out postVal); } catch { }

            if (postVal != 0)
                postNonNullCount++;

            if (postVal != preVal)
            {
                changedCount++;
                if (preVal == 0)
                    wasZeroNowNonZero++;
                else
                    wasNonZeroNowDifferent++;

                // Log each changed global (up to 30 to avoid flooding)
                if (changedCount <= 30)
                {
                    Console.Error.WriteLine($"[RESOLVER-TRACE]   Global #{i+1} @0x{addr:x}: 0x{preVal:x} -> 0x{postVal:x}");
                }
            }
        }

        if (changedCount > 30)
        {
            Console.Error.WriteLine($"[RESOLVER-TRACE]   ... and {changedCount - 30} more changed globals");
        }

        Console.Error.WriteLine($"[RESOLVER-TRACE] Post-wrapper: {postNonNullCount}/{ResolverStoreAddresses.Length} globals are non-zero");
        Console.Error.WriteLine($"[RESOLVER-TRACE] Changed globals: {changedCount}/{ResolverStoreAddresses.Length}");
        Console.Error.WriteLine($"[RESOLVER-TRACE]   Was 0, now non-zero: {wasZeroNowNonZero}");
        Console.Error.WriteLine($"[RESOLVER-TRACE]   Was non-zero, now different: {wasNonZeroNowDifferent}");

        // Also check the resolver's linked list flags again
        int postListNodesChecked = 0;
        int postListFlagsSet = 0;
        try
        {
            if (ctx.TryReadUInt64(ResolverListHeadPtr, out ulong listHead))
            {
                if (listHead != 0 && ctx.TryReadUInt64(listHead + 8, out ulong firstNode))
                {
                    ulong currentNode = firstNode;
                    for (int n = 0; n < 300 && currentNode != 0; n++)
                    {
                        postListNodesChecked++;
                        byte flag = 0;
                        try { ctx.TryReadByte(currentNode + 0x19, out flag); } catch { }
                        if (flag != 0)
                            postListFlagsSet++;

                        ulong nextNode = 0;
                        try { ctx.TryReadUInt64(currentNode, out nextNode); } catch { }
                        if (nextNode == currentNode || nextNode == 0)
                            break;
                        currentNode = nextNode;
                    }
                }
            }
        }
        catch { }

        Console.Error.WriteLine($"[RESOLVER-TRACE] Post-wrapper list: walked {postListNodesChecked} nodes, {postListFlagsSet} have [rbx+0x19] flag set");
        Console.Error.WriteLine($"[RESOLVER-TRACE] Pre-wrapper list:  walked {_preListNodesChecked} nodes, {_preListFlagsSet} had [rbx+0x19] flag set");

        int newFlagsSet = postListFlagsSet - _preListFlagsSet;
        Console.Error.WriteLine($"[RESOLVER-TRACE] New flags set during wrapper: {newFlagsSet}");

        // Final verdict
        Console.Error.WriteLine($"[RESOLVER-TRACE] === VERDICT ===");
        if (changedCount > 0)
        {
            Console.Error.WriteLine($"[RESOLVER-TRACE] RESOLVER DID EXECUTE: {changedCount} globals changed (proof: resolver wrote return values)");
        }
        else if (newFlagsSet > 0)
        {
            Console.Error.WriteLine($"[RESOLVER-TRACE] RESOLVER DID EXECUTE: {newFlagsSet} new [rbx+0x19] flags set (proof: resolver matched symbols)");
        }
        else
        {
            Console.Error.WriteLine($"[RESOLVER-TRACE] RESOLVER DID NOT EXECUTE (or returned 0 for all symbols without setting any flags)");
            Console.Error.WriteLine($"[RESOLVER-TRACE]   - 0 globals changed");
            Console.Error.WriteLine($"[RESOLVER-TRACE]   - 0 new list flags set");
            Console.Error.WriteLine($"[RESOLVER-TRACE]   Cannot distinguish 'resolver not called' from 'resolver called but returned 0 for all'");
        }
        Console.Error.WriteLine($"[RESOLVER-TRACE] === POST-WRAPPER COMPARISON COMPLETE ===");
    }
}
