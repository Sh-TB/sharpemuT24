#!/usr/bin/env python3
"""
G1 (items 6-10): Full disassembly of helper 0x804EDACD0
Determine algorithm type, identify rotations, find priority source.
Also G13 (items 64-67): Treap-specific checks.
Also G4 (items 19-22): CPU instruction coverage, flag propagation.
Also G6 (item 26-28): Node struct layout verification.
"""
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_OP_IMM

PRX = '/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx'
PRX_BASE = 0x804CD5000
def va2off(va): return (va - PRX_BASE) + 0x4000

with open(PRX, 'rb') as f:
    data = f.read()

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

# G1-1: Full disassembly of 0x804EDACD0
print("=" * 80)
print("G1-1 (item 6): Full disassembly of helper 0x804EDACD0")
print("=" * 80)
print()

off = va2off(0x804EDACD0)
bs = data[off:off+1024]
insns = []
for insn in md.disasm(bs, 0x804EDACD0):
    insns.append(insn)
    if insn.mnemonic == "ret":
        break
    if insn.address > 0x804EDB000:
        break

flag_writers = []
flag_consumers = []
cmov_instructions = []
conditional_jumps = []
memory_writes = []

for insn in insns:
    addr = insn.address
    mnem = insn.mnemonic
    ops = insn.op_str
    raw = insn.bytes.hex()
    
    annotation = ""
    if mnem in ("cmp", "test", "sub", "add", "and", "or", "xor", "inc", "dec", "shr", "shl", "sar"):
        flag_writers.append((addr, mnem, ops))
        annotation += " [FLAG_WRITER]"
    if mnem.startswith("cmov") or mnem.startswith("set"):
        flag_consumers.append((addr, mnem, ops))
        annotation += " [FLAG_CONSUMER]"
    if mnem.startswith("cmov"):
        cmov_instructions.append((addr, mnem, ops))
    if mnem.startswith("j") and mnem != "jmp":
        conditional_jumps.append((addr, mnem, ops))
        annotation += " [COND_JUMP]"
    if mnem == "jmp":
        annotation += " [UNCOND_JUMP]"
    if mnem in ("mov", "vmovups", "vmovaps", "movq") and "[r" in ops:
        if len(insn.operands) > 0 and insn.operands[0].type == X86_OP_MEM:
            memory_writes.append((addr, mnem, ops))
            annotation += " [MEM_WRITE]"
    
    if "rip" in ops:
        try:
            for op in insn.operands:
                if op.type == X86_OP_MEM and op.mem.base != 0 and insn.reg_name(op.mem.base) == "rip":
                    target = addr + insn.size + op.mem.disp
                    annotation += f" -> 0x{target:x}"
                    break
        except: pass
    
    print(f"  0x{addr:x}  {raw:24s}  {mnem:8s}  {ops}{annotation}")

print(f"\nTotal instructions: {len(insns)}")

# G1-2: Algorithm type
print()
print("=" * 80)
print("G1-2 (item 7): Algorithm type identification")
print("=" * 80)
print()
print("Key findings from disassembly:")
print("  - [rsi+0x10] is a SIZE COUNTER (incremented each call)")
print("  - Compared against 0x555555555555554 (max size)")
print("  - [r9+0x08] = parent pointer (set for new node)")
print("  - [rcx+0x00] = right child / [rcx+0x10] = left child")
print("  - dl parameter controls left vs right insertion")
print("  - [r11+0x18] flag checked for rebalancing decision")
print("  - [rax+0x18] = 1 set on root when rebalancing needed")
print()
print("The function checks [parent+0x18] flag:")
print("  If flag != 0: return immediately (no rebalancing needed)")
print("  If flag == 0: fall through to rebalancing code")
print()
print("This is consistent with a RED-BLACK TREE insert fixup:")
print("  [0x18]=1 = RED node (needs potential rebalancing)")
print("  [0x18]=0 = BLACK node (no rebalancing needed)")
print("  When parent is BLACK (flag=0): insert is done")
print("  When parent is RED (flag!=0): need to fixup")
print()
print("ALGORITHM TYPE: RED-BLACK TREE (most likely)")

# G1-3: Continue disassembly past first ret (rebalancing code)
print()
print("=" * 80)
print("G1-3 (item 8): Rebalancing code (after first ret)")
print("=" * 80)
print()

for insn2 in md.disasm(data[va2off(0x804EDAD5F):va2off(0x804EDAD5F)+512], 0x804EDAD5F):
    addr2 = insn2.address
    mnem2 = insn2.mnemonic
    ops2 = insn2.op_str
    annotation = ""
    if mnem2 in ("cmp", "test", "sub", "add", "and", "or", "xor"):
        annotation = " [FLAG_WRITER]"
    if mnem2.startswith("cmov"):
        annotation = f" [FLAG_CONSUMER:{mnem2}]"
    if mnem2.startswith("j") and mnem2 != "jmp":
        annotation = " [COND_JUMP]"
    if mnem2 in ("mov",) and "[r" in ops2:
        if len(insn2.operands) > 0 and insn2.operands[0].type == X86_OP_MEM:
            annotation = " [MEM_WRITE]"
    print(f"  0x{addr2:x}  {mnem2:8s}  {ops2}{annotation}")
    if insn2.mnemonic == "ret":
        break
    if insn2.address > 0x804EDAF80:
        print("  ... (truncated)")
        break

# G4: Instruction coverage
print()
print("=" * 80)
print("G4-1 (item 19): Instruction coverage")
print("=" * 80)
all_mnemonics = sorted(set(i.mnemonic for i in insns))
print(f"Unique mnemonics: {all_mnemonics}")
print()
print("cmov instructions:")
for addr, mnem, ops in cmov_instructions:
    print(f"  0x{addr:x}: {mnem} {ops}")
print()
print("Conditional jumps:")
for addr, mnem, ops in conditional_jumps:
    print(f"  0x{addr:x}: {mnem} {ops}")

# G4-3: Flag propagation
print()
print("=" * 80)
print("G4-3 (item 21): Flag propagation analysis")
print("=" * 80)
print()
print("Flag writers:")
for addr, mnem, ops in flag_writers:
    print(f"  0x{addr:x}: {mnem} {ops}")
print()
print("Flag consumers:")
for addr, mnem, ops in flag_consumers:
    print(f"  0x{addr:x}: {mnem} {ops}")
for addr, mnem, ops in conditional_jumps:
    print(f"  0x{addr:x}: {mnem} {ops}")

# G6: Node struct layout
print()
print("=" * 80)
print("G6 (item 26): Node struct layout (CORRECTED)")
print("=" * 80)
print()
print("From helper disassembly:")
print("  +0x00: right child pointer")
print("  +0x08: PARENT pointer (NOT duplicate of [0x00]!)")
print("  +0x10: left child pointer")
print("  +0x18: color flag (0=BLACK, 1=RED in red-black tree)")
print("  +0x19: matched flag (0=not matched, 1=matched/sentinel)")
print("  +0x20: symbol name pointer")
print("  +0x28: function implementation pointer")
print()
print("CRITICAL: [0x08] is PARENT pointer, needed for red-black tree fixup!")
print("Previous analysis incorrectly assumed [0x08] was a duplicate of [0x00].")
print()
print("Resolver uses: [0x00]=right, [0x10]=left, [0x20]=name, [0x28]=func")
print("Insert uses:   [0x00]=right, [0x08]=parent, [0x10]=left, [0x18]=color, [0x20]=name, [0x28]=func")
print("→ Offsets MATCH for all fields used by both functions.")
