# CONTRADICTIONS.md (Append-Only)

## CONTRADICTION-001: "6 nodes" vs "239 nodes"
- Finding A: "Only 6 real nodes reachable in BST" (Evidence_v6, L1-TRACE)
- Finding B: "239 real nodes + 1 sentinel reachable" (test_d1_bst_walk.log, IndependentBSTWalker)
- Status: RESOLVED
- Resolution: Finding A was WRONG. L1-TRACE only followed RIGHT children (the resolver's
  traversal path for il2cpp_init query). IndependentBSTWalker follows BOTH left AND right
  children. The BST has 239 nodes but they are NOT correctly sorted, so the resolver
  can't find most of them.
- Lesson: Always traverse BOTH children in a BST walker.

## CONTRADICTION-002: "BST is correct" vs "BST has 238 sorting violations"
- Finding A: "BST correctly populated with 239 nodes" (Evidence_v5, L1-TRACE)
- Finding B: "238/239 nodes have sorting violations" (Python parser on BST-WALK output)
- Status: RESOLVED
- Resolution: Both are TRUE simultaneously. The BST HAS 239 nodes (correct count)
  but they are NOT correctly sorted (wrong order). The insertion function created
  all nodes but linked them incorrectly because strcmp returned wrong results.
- Lesson: Node count and node ordering are independent properties.

## CONTRADICTION-003: "No faults during register_symbols" vs "strcmp fails"
- Finding A: "No posix-signals or NULL execute faults during register_symbols" (log analysis)
- Finding B: "HLE strcmp returns MEMORY_FAULT for PRX data addresses" (source analysis)
- Status: RESOLVED
- Resolution: HLE strcmp failure does NOT cause a posix-signal. It returns an error
  code through the HLE dispatch framework. The BST insertion function reads eax
  (which contains the error code, not a fault signal). The error is SILENT —
  no crash, no signal, just wrong comparison results.
- Lesson: HLE dispatch failures are silent — they don't cause signals.
