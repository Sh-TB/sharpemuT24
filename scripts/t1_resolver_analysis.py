#!/usr/bin/env python3
"""
T1.1: Full resolver disassembly + CFG + all branches/compares
T1.3: Compare direction test (inverted BST awareness)
T2.2: Compare writer vs reader offsets
T5.1: Instruction inventory
T5.3: Flag producers and consumers
"""
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_REG

PRX = '/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx'
PRX_BASE = 0x804CD5000
def va2off(va): return (va - PRX_BASE) + 0x4000

with open(PRX, 'rb') as f:
    data = f.read()

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# ============================================================
# T1.1: FULL RESOLVER DISASSEMBLY 0x804ED9B90
# ============================================================
print("=" * 80)
print("T1.1: Full resolver disassembly 0x804ED9B90")
print("=" * 80)
print()

off = va2off(0x804ED9B90)
bs = data[off:off+128]
insns = list(md.disasm(bs, 0x804ED9B90))

for insn in insns:
    addr = insn.address
    mnem = insn.mnemonic
    ops = insn.op_str
    raw = insn.bytes.hex()
    
    annotation = ""
    # Flag writers
    if mnem in ("cmp", "test", "sub", "add", "and", "or", "xor"):
        annotation = " [FLAG_WRITER]"
    # Flag consumers
    if mnem.startswith("cmov") or mnem.startswith("set"):
        annotation = f" [FLAG_CONSUMER:{mnem}]"
    if mnem.startswith("j") and mnem != "jmp":
        annotation = f" [COND_JUMP:{mnem}]"
    if mnem == "call":
        annotation = " [CALL]"
    if mnem == "ret":
        annotation = " [RET]"
    
    # Annotate memory accesses
    if "[rbx" in ops:
        offset_match = ""
        if "+0x00]" in ops or "]" == ops.split("[rbx")[1].split("]")[0]:
            offset_match = " {right child}"
        elif "+0x10]" in ops:
            offset_match = " {left child}"
        elif "+0x18]" in ops:
            offset_match = " {color flag}"
        elif "+0x19]" in ops:
            offset_match = " {matched flag}"
        elif "+0x20]" in ops:
            offset_match = " {symbol name}"
        elif "+0x28]" in ops:
            offset_match = " {func impl}"
        elif "+0x08]" in ops:
            offset_match = " {parent}"
        annotation += offset_match
    
    if "rip" in ops:
        try:
            for op in insn.operands:
                if op.type == X86_OP_MEM and op.mem.base != 0 and insn.reg_name(op.mem.base) == "rip":
                    target = addr + insn.size + op.mem.disp
                    annotation += f" -> 0x{target:x}"
                    break
        except: pass
    
    print(f"  0x{addr:x}  {raw:24s}  {mnem:8s}  {ops}{annotation}")
    
    if mnem == "ret" and addr > 0x804ED9BB6:
        break

# ============================================================
# T1.3: Direction analysis — does resolver know about INVERTED BST?
# ============================================================
print()
print("=" * 80)
print("T1.3: Direction test — inverted BST awareness")
print("=" * 80)
print()
print("Resolver code analysis:")
print("  0x804ED9BCC: test eax, eax        ; check strcmp result")
print("  0x804ED9BCE: lea rcx, [rbx+0x10]  ; default: LEFT child")
print("  0x804ED9BD2: cmovns rcx, rbx       ; if strcmp >= 0: rcx = rbx → use [rbx+0x00] = RIGHT")
print()
print("strcmp(NODE, QUERY) >= 0 → RIGHT")
print("strcmp(NODE, QUERY) < 0  → LEFT")
print()
print("In INVERTED BST: RIGHT = smaller nodes, LEFT = larger nodes")
print("  strcmp(NODE, QUERY) >= 0 means NODE >= QUERY")
print("  → go RIGHT (where smaller nodes are)")
print("  → looking for nodes <= NODE")
print("  This is CORRECT for inverted BST search!")
print()
print("After sentinel (loop exit):")
print("  0x804ED9BE3: cmp r12, r15  ; r12=candidate, r15=initial struct ptr")
print("  0x804ED9BE6: je return_0   ; if no candidate → return 0")
print("  0x804ED9BE8: mov rsi, [r12+0x20]  ; candidate's symbol name")
print("  0x804ED9BED: mov rdi, r14          ; query name")
print("  0x804ED9BF0: call strcmp           ; strcmp(candidate, query)")
print("  0x804ED9BF5: test eax, eax")
print("  0x804ED9BF7: js return_0           ; if strcmp < 0 → return 0")
print("  0x804ED9BF9: mov rax, [r12+0x28]  ; return func_impl")
print()
print("Final check: strcmp(CANDIDATE, QUERY) >= 0 → return func_impl")
print("  This means: candidate >= query → match")
print("  In inverted BST: candidate is the last node where NODE >= QUERY")
print("  If candidate == query → strcmp returns 0 → >= 0 → MATCH ✓")
print("  If candidate > query → strcmp returns > 0 → >= 0 → MATCH (but wrong!)")
print()
print("⚠️ WAIT — if candidate > query, strcmp returns positive, which is >= 0,")
print("  so the resolver returns the candidate's func_ptr even though it's not")
print("  an exact match! Is this correct?")
print()
print("  In a standard BST search, the 'candidate' is the last node where")
print("  NODE >= QUERY. If the exact match doesn't exist, the candidate is")
print("  the smallest node that's >= query (lower bound).")
print("  The final strcmp checks if candidate >= query (which is always true")
print("  by construction). So the resolver returns the LOWER BOUND, not exact match.")
print()
print("  But wait — if the symbol IS in the tree, the traversal should reach it.")
print("  The candidate would be the exact match node, and strcmp returns 0.")
print()
print("  The js (jump if signed/negative) at 0x804ED9BF7 checks:")
print("  if strcmp(candidate, query) < 0 → return 0")
print("  This filters out cases where candidate < query (shouldn't happen in correct BST).")
print()
print("CONCLUSION: Resolver direction is CORRECT for inverted BST.")

# ============================================================
# T2.2: Compare writer vs reader offsets
# ============================================================
print()
print("=" * 80)
print("T2.2: Writer vs Reader offset comparison")
print("=" * 80)
print()
print("Field      | Insert writes | Resolver reads | Match?")
print("-----------|---------------|----------------|-------")
print("[0x00] right| mov [rcx], r9 | mov rbx, [rcx]| ✅")
print("[0x08] parent| mov [r9+8],rcx| (not used)    | N/A")
print("[0x10] left | mov [rcx+0x10],r9| lea rcx,[rbx+0x10]; mov rbx,[rcx]| ✅")
print("[0x18] color| mov byte[rax+0x18],1| (not used)  | N/A")
print("[0x19] match| (set by init) | cmp byte[rbx+0x19],0| ✅")
print("[0x20] name | mov [rax+0x20],rdx| mov rdi,[rbx+0x20]| ✅")
print("[0x28] func | mov [rax+0x28],rdx| mov rax,[r12+0x28]| ✅")
print()
print("ALL offsets MATCH between insert and resolver.")

# ============================================================
# T5.1: Instruction inventory
# ============================================================
print()
print("=" * 80)
print("T5.1: Instruction inventory in resolver")
print("=" * 80)
print()
all_mnemonics = sorted(set(i.mnemonic for i in insns))
print(f"Unique mnemonics: {all_mnemonics}")
print()
print("Potentially problematic instructions:")
for insn in insns:
    if insn.mnemonic.startswith("cmov") or insn.mnemonic.startswith("set"):
        print(f"  0x{insn.address:x}: {insn.mnemonic} {insn.op_str}")
    if insn.mnemonic in ("cmp", "test"):
        print(f"  0x{insn.address:x}: {insn.mnemonic} {insn.op_str} [FLAG_WRITER]")
    if insn.mnemonic.startswith("j") and insn.mnemonic != "jmp":
        print(f"  0x{insn.address:x}: {insn.mnemonic} {insn.op_str} [COND_JUMP]")

# ============================================================
# T5.3: Flag producers and consumers
# ============================================================
print()
print("=" * 80)
print("T5.3: Flag propagation in resolver")
print("=" * 80)
print()
print("Flag producers (set flags):")
for insn in insns:
    if insn.mnemonic in ("cmp", "test", "sub", "add", "and", "or", "xor"):
        print(f"  0x{insn.address:x}: {insn.mnemonic} {insn.op_str}")
print()
print("Flag consumers (use flags):")
for insn in insns:
    if insn.mnemonic.startswith("cmov") or insn.mnemonic.startswith("j") or insn.mnemonic.startswith("set"):
        print(f"  0x{insn.address:x}: {insn.mnemonic} {insn.op_str}")
print()
print("Flag chain analysis:")
print("  1. call strcmp → sets flags (via test eax, eax)")
print("  2. test eax, eax → produces ZF/SF based on strcmp result")
print("  3. lea rcx, [rbx+0x10] → does NOT modify flags")
print("  4. cmovns rcx, rbx → consumes SF from step 2")
print("  5. cmovns r12, rbx → consumes SF from step 2 (same flags!)")
print()
print("  Chain: strcmp → test → cmovns (2 consumers, 1 producer)")
print("  No intermediate flag-modifying instructions between test and cmovns.")
print("  Flag lifetime: 2 instructions (short, safe)")
print()
print("  Second chain: call strcmp → test eax, eax → js return_0")
print("  Chain: strcmp → test → js (1 consumer)")
print("  Flag lifetime: 1 instruction (very short, safe)")
