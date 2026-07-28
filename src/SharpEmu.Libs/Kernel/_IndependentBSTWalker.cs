// D1.1: Independent BST walker — does NOT use _FlagWatchInstrumentation
// Walks the BST recursively with cycle detection, recording ALL reachable nodes.
using System.Collections.Generic;
using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

public static class IndependentBSTWalker
{
    public static void DumpFullBST(CpuContext ctx, string label)
    {
        Console.Error.WriteLine($"[BST-WALK] === INDEPENDENT BST WALK ({label}) ===");
        
        try
        {
            // Read list head pointer
            const ulong ListHeadPtrAddr = 0x808B53708;
            if (!ctx.TryReadUInt64(ListHeadPtrAddr, out ulong listHeadStruct))
            {
                Console.Error.WriteLine("[BST-WALK] ERROR: Cannot read list head pointer");
                return;
            }
            Console.Error.WriteLine($"[BST-WALK] List head struct: 0x{listHeadStruct:x}");
            
            // Read root node from [struct+8]
            if (!ctx.TryReadUInt64(listHeadStruct + 8, out ulong rootNode))
            {
                Console.Error.WriteLine("[BST-WALK] ERROR: Cannot read root node");
                return;
            }
            Console.Error.WriteLine($"[BST-WALK] Root node: 0x{rootNode:x}");
            
            // Walk the BST using a stack (iterative, not recursive, to avoid stack overflow)
            var visited = new HashSet<ulong>();
            var stack = new Stack<ulong>();
            stack.Push(rootNode);
            
            int totalNodes = 0;
            int realNodes = 0;
            int sentinelHits = 0;
            int cycleHits = 0;
            var allNodes = new List<(ulong addr, string name, ulong left, ulong right, byte flag)>();
            
            while (stack.Count > 0)
            {
                ulong nodeAddr = stack.Pop();
                
                // Skip null
                if (nodeAddr == 0) continue;
                
                // Check for cycles
                if (visited.Contains(nodeAddr))
                {
                    cycleHits++;
                    Console.Error.WriteLine($"[BST-WALK] CYCLE detected at 0x{nodeAddr:x} (already visited)");
                    continue;
                }
                visited.Add(nodeAddr);
                totalNodes++;
                
                // Read node fields
                byte flag = 0;
                ctx.TryReadByte(nodeAddr + 0x19, out flag);
                
                ulong rightChild = 0, leftChild = 0, symPtr = 0;
                ctx.TryReadUInt64(nodeAddr, out rightChild);        // [0x00] = right
                ctx.TryReadUInt64(nodeAddr + 0x10, out leftChild);   // [0x10] = left
                ctx.TryReadUInt64(nodeAddr + 0x20, out symPtr);      // [0x20] = symbol name
                
                // Read symbol name
                string name = "<null>";
                if (symPtr != 0 && flag == 0)
                {
                    var nameBytes = new byte[128];
                    int nameLen = 0;
                    for (int i = 0; i < 128; i++)
                    {
                        byte b;
                        if (!ctx.TryReadByte(symPtr + (ulong)i, out b)) break;
                        if (b == 0) break;
                        nameBytes[i] = b;
                        nameLen++;
                    }
                    if (nameLen > 0)
                        name = System.Text.Encoding.ASCII.GetString(nameBytes, 0, nameLen);
                }
                else if (flag != 0)
                {
                    name = "<SENTINEL>";
                    sentinelHits++;
                }
                
                if (flag == 0)
                    realNodes++;
                
                allNodes.Add((nodeAddr, name, leftChild, rightChild, flag));
                
                Console.Error.WriteLine(
                    $"[BST-WALK] Node #{totalNodes} @0x{nodeAddr:x}: name='{name}' " +
                    $"left=0x{leftChild:x} right=0x{rightChild:x} flag[0x19]={flag}");
                
                // Push children (right first, then left, so left is processed first)
                if (rightChild != 0 && !visited.Contains(rightChild))
                    stack.Push(rightChild);
                if (leftChild != 0 && !visited.Contains(leftChild))
                    stack.Push(leftChild);
                
                // Safety limit
                if (totalNodes >= 500)
                {
                    Console.Error.WriteLine("[BST-WALK] SAFETY LIMIT: 500 nodes reached, stopping");
                    break;
                }
            }
            
            Console.Error.WriteLine($"[BST-WALK] === SUMMARY ===");
            Console.Error.WriteLine($"[BST-WALK] Total nodes visited: {totalNodes}");
            Console.Error.WriteLine($"[BST-WALK] Real nodes (flag=0): {realNodes}");
            Console.Error.WriteLine($"[BST-WALK] Sentinel hits (flag=1): {sentinelHits}");
            Console.Error.WriteLine($"[BST-WALK] Cycle hits: {cycleHits}");
            Console.Error.WriteLine($"[BST-WALK] Unique addresses: {visited.Count}");
            
            // D1.3: Search for specific symbols
            Console.Error.WriteLine($"[BST-WALK] === SYMBOL SEARCH ===");
            string[] searchSymbols = { "il2cpp_init", "il2cpp_shutdown", "il2cpp_alloc", 
                                        "il2cpp_class_num_fields", "il2cpp_add_internal_call",
                                        "il2cpp_resolve_icall", "il2cpp_free" };
            foreach (var search in searchSymbols)
            {
                bool found = false;
                foreach (var node in allNodes)
                {
                    if (node.name == search)
                    {
                        Console.Error.WriteLine($"[BST-WALK] FOUND: '{search}' @0x{node.addr:x} left=0x{node.left:x} right=0x{node.right:x}");
                        found = true;
                        break;
                    }
                }
                if (!found)
                {
                    Console.Error.WriteLine($"[BST-WALK] NOT FOUND: '{search}'");
                }
            }
            
            Console.Error.WriteLine($"[BST-WALK] === INDEPENDENT BST WALK COMPLETE ===");
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"[BST-WALK] ERROR: {e.Message}");
        }
    }
}
