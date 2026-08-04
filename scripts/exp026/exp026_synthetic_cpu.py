#!/usr/bin/env python3
"""
EXP-026 Stage 3: Synthetic x86-64 CPU Emulator for Resolver Execution Divergence Test.

Goal: Find the EXACT instruction where the resolver diverges from the reference
implementation. Run the resolver's instruction sequence in a synthetic CPU
(no game, no IL2CPP, only the resolver algorithm) and trace every branch
decision.

This emulator implements the resolver's exact instruction sequence (reconstructed
from the static disassembly at 0x804ED9B90 in Il2cppUserAssemblies.prx):

    0x804ED9B90: push rbp
    0x804ED9B91: mov rbp, rsp
    0x804ED9B94: push r15; push r14; push r12; push rbx
    0x804ED9B9B: mov r15, [rip+0x3c79b66]    ; r15 = list head struct (= sentinel)
    0x804ED9BA2: mov rbx, [r15+8]              ; rbx = root node (from sentinel+8)
    0x804ED9BA6: cmp byte [rbx+0x19], 0        ; check matched flag (sentinel check)
    0x804ED9BAA: je 0x804ED9BB7                ; if not matched, do lookup
    0x804ED9BAC: xor eax, eax                  ; already matched: return 0
    0x804ED9BAE: pop rbx; pop r12; pop r14; pop r15; pop rbp
    0x804ED9BB6: ret
    0x804ED9BB7: mov r14, rdi                  ; r14 = query string
    0x804ED9BBA: mov r12, r15                  ; r12 = candidate (initially sentinel = none)
    0x804ED9BBD: nop
    0x804ED9BC0: mov rdi, [rbx+0x20]           ; rdi = NODE symbol name
    0x804ED9BC4: mov rsi, r14                  ; rsi = QUERY
    0x804ED9BC7: call strcmp                   ; rax = strcmp(NODE, QUERY)
    0x804ED9BCC: test eax, eax                 ; sets SF, ZF
    0x804ED9BCE: lea rcx, [rbx+0x10]           ; rcx = LEFT child addr
    0x804ED9BD2: cmovns rcx, rbx               ; if SF=0 (NODE>=QUERY): rcx = rbx (RIGHT)
    0x804ED9BD6: cmovns r12, rbx               ; if SF=0 (NODE>=QUERY): r12 = rbx (candidate)
    0x804ED9BDA: mov rbx, [rcx]                ; rbx = next node
    0x804ED9BDD: cmp byte [rbx+0x19], 0        ; sentinel check
    0x804ED9BE1: je 0x804ED9BC0                 ; loop if not sentinel
    0x804ED9BE3: cmp r12, r15                  ; candidate == sentinel? (no candidate)
    0x804ED9BE6: je 0x804ED9BAC                 ; if no candidate, return 0
    0x804ED9BE8: mov rsi, [r12+0x20]           ; rsi = CANDIDATE symbol name
    0x804ED9BED: mov rdi, r14                  ; rdi = QUERY
    0x804ED9BF0: call strcmp                   ; rax = strcmp(QUERY, CANDIDATE)
    0x804ED9BF5: test eax, eax
    0x804ED9BF7: js 0x804ED9BAC                 ; if SF=1 (QUERY<CANDIDATE), return 0
    0x804ED9BF9: mov rax, [r12+0x28]           ; rax = func_impl
    (ret follows)

For every instruction, log:
    - RIP
    - instruction bytes (mnemonic + operands)
    - registers: RAX, RBX, RCX, RDI, RSI, R12, R14, R15, RBP, RSP
    - flags: SF, ZF, CF, OF, PF
    - branch taken/not taken (for conditional jumps and cmovs)

Compare against the reference Python RBTree.search() implementation to find
any divergence.
"""

import json
import sys
from pathlib import Path

TREE_JSON = '/home/z/my-project/scripts/exp026_tree.json'

# ===========================================================================
# x86-64 emulator state (minimal, only what resolver needs)
# ===========================================================================

class X86Flags:
    """EFLAGS subset relevant to resolver."""
    def __init__(self):
        self.SF = 0  # Sign flag
        self.ZF = 0  # Zero flag
        self.CF = 0  # Carry flag
        self.OF = 0  # Overflow flag
        self.PF = 0  # Parity flag

    def set_from_sub_cmp(self, result, src_val, dst_val, size=8):
        """Set flags based on CMP/SUB result (dst - src)."""
        mask = (1 << (size * 8)) - 1
        result_masked = result & mask
        sign_bit = 1 << (size * 8 - 1)

        self.ZF = 1 if result_masked == 0 else 0
        self.SF = 1 if (result_masked & sign_bit) else 0
        self.CF = 1 if (dst_val & mask) < (src_val & mask) else 0
        # OF: signs of operands differ AND sign of result differs from dst
        d_sign = (dst_val & mask) & sign_bit
        s_sign = (src_val & mask) & sign_bit
        r_sign = result_masked & sign_bit
        self.OF = 1 if (d_sign != s_sign) and (r_sign != d_sign) else 0
        # PF: parity of low 8 bits
        low8 = result_masked & 0xFF
        self.PF = 1 if (bin(low8).count('1') % 2 == 0) else 0

    def set_from_test(self, result, size=8):
        """Set flags based on TEST/AND result (dst & src)."""
        mask = (1 << (size * 8)) - 1
        result_masked = result & mask
        sign_bit = 1 << (size * 8 - 1)

        self.ZF = 1 if result_masked == 0 else 0
        self.SF = 1 if (result_masked & sign_bit) else 0
        self.CF = 0
        self.OF = 0
        low8 = result_masked & 0xFF
        self.PF = 1 if (bin(low8).count('1') % 2 == 0) else 0

    def __str__(self):
        return f"SF={self.SF} ZF={self.ZF} CF={self.CF} OF={self.OF} PF={self.PF}"


class Regs:
    """Register file."""
    def __init__(self):
        self.rax = 0
        self.rbx = 0
        self.rcx = 0
        self.rdx = 0
        self.rdi = 0
        self.rsi = 0
        self.rbp = 0
        self.rsp = 0
        self.r8 = 0; self.r9 = 0; self.r10 = 0; self.r11 = 0
        self.r12 = 0
        self.r13 = 0
        self.r14 = 0
        self.r15 = 0
        self.rip = 0
        self.flags = X86Flags()

    def get(self, name):
        return getattr(self, name.lower())

    def set(self, name, val):
        setattr(self, name.lower(), val & 0xFFFFFFFFFFFFFFFF)


# ===========================================================================
# Memory: address-keyed dict; addresses in resolver are node addrs
# ===========================================================================

class Memory:
    """Sparse memory for the resolver's data structures."""
    def __init__(self, tree_data):
        self.tree = tree_data['nodes']  # dict: "0x..." -> node dict
        self.list_head_ptr_addr = tree_data['list_head_ptr_addr']
        self.list_head_struct_addr = tree_data['list_head_struct_addr']
        self.root_node_addr = tree_data['root_node_addr']
        self.node_struct_size = tree_data['node_struct_size']
        self.fields = tree_data['node_field_offsets']

        # Symbol name pool: assign fake addresses for each unique symbol name
        # so that [rbx+0x20] returns a string pointer that strcmp can use.
        self.string_addrs = {}  # name -> fake addr
        self.string_store = {}  # fake addr -> name
        next_str_addr = 0x40000000
        for node in self.tree.values():
            if node['name'] and node['name'] not in self.string_addrs:
                self.string_addrs[node['name']] = next_str_addr
                self.string_store[next_str_addr] = node['name']
                next_str_addr += len(node['name']) + 16

        # Patch each node's symbol_name field with the fake string addr
        for node in self.tree.values():
            if node['name']:
                node['symbol_name_addr'] = self.string_addrs[node['name']]
            else:
                node['symbol_name_addr'] = 0

    def get_node(self, addr):
        """Get node by address. Returns None if not found."""
        key = f"0x{addr:x}"
        return self.tree.get(key)

    def read_u64(self, addr):
        """Read 8 bytes from memory at addr.
        For node addresses, returns the appropriate field based on offset.
        For string addresses, returns 0 (not used as u64).
        """
        # Check if it's the global list head pointer
        if addr == self.list_head_ptr_addr:
            return self.list_head_struct_addr

        # Check if addr points inside a node (mask lower bits)
        # Node field offsets: 0x00, 0x08, 0x10, 0x18, 0x20, 0x28
        # Node size is 0x30
        node_base = addr & ~0x2F  # mask to 0x30 boundary
        offset = addr & 0x2F

        # Try to find the node — addresses may not be 0x30-aligned, so check direct first
        node = self.get_node(addr)
        if node is None:
            # Try aligning
            # Actually node addresses from BST-WALK are arbitrary; check direct match
            # by trying addr itself first, then addr - 0, addr - 8, etc.
            # Since we don't know alignment, let's check all known node addresses
            for n_addr_str, n in self.tree.items():
                n_addr = int(n_addr_str, 16)
                if n_addr <= addr < n_addr + self.node_struct_size:
                    node = n
                    offset = addr - n_addr
                    break

        if node is None:
            # Might be the list head struct itself
            if addr == self.list_head_struct_addr:
                # [+0x00] is unused, [+0x08] is root
                return 0
            if addr == self.list_head_struct_addr + 8:
                return self.root_node_addr
            return 0

        # Read field based on offset
        if offset == self.fields['right']:       # 0x00
            return node['right']
        elif offset == self.fields['parent']:    # 0x08
            # parent not in BST-WALK; for sentinel, +8 = root
            # The list head struct happens to be at the sentinel addr!
            if node.get('flag_19') == 1:  # sentinel
                return self.root_node_addr
            return 0
        elif offset == self.fields['left']:      # 0x10
            return node['left']
        elif offset == self.fields['color']:     # 0x18
            return node['color']
        elif offset == self.fields['symbol_name']:# 0x20
            return node['symbol_name_addr']
        elif offset == self.fields['func_impl']: # 0x28
            return node['func_ptr']
        else:
            return 0

    def read_u8(self, addr):
        """Read 1 byte from memory at addr."""
        # Check node matched_flag at offset 0x19
        for n_addr_str, n in self.tree.items():
            n_addr = int(n_addr_str, 16)
            if n_addr <= addr < n_addr + self.node_struct_size:
                offset = addr - n_addr
                if offset == self.fields['matched_flag']:  # 0x19
                    return n['flag_19']
                if offset == self.fields['color']:  # 0x18
                    return n['color']
                return 0
        return 0

    def read_cstring(self, addr):
        """Read a C string from a string address."""
        return self.string_store.get(addr, "")


# ===========================================================================
# strcmp implementation (matches libc semantics)
# ===========================================================================

def strcmp(s1, s2):
    """Standard strcmp: returns negative/zero/positive."""
    if s1 is None or s2 is None:
        return 0
    for c1, c2 in zip(s1, s2):
        if c1 != c2:
            return ord(c1) - ord(c2)
    return len(s1) - len(s2)


# ===========================================================================
# Synthetic CPU: emulates the resolver instruction-by-instruction
# ===========================================================================

class SyntheticResolverCPU:
    """Emulates the resolver function with full per-instruction tracing."""

    # Resolver instruction addresses (from disassembly)
    ADDR_PUSH_RBP         = 0x804ED9B90
    ADDR_MOV_RBP_RSP      = 0x804ED9B91
    ADDR_PUSH_R14_R15_R12_RBX = 0x804ED9B94
    ADDR_MOV_R15_RIP      = 0x804ED9B9B
    ADDR_MOV_RBX_R15_8    = 0x804ED9BA2
    ADDR_CMP_BYTE_RBX_19  = 0x804ED9BA6
    ADDR_JE_DO_LOOKUP     = 0x804ED9BAA
    ADDR_XOR_EAX          = 0x804ED9BAC
    ADDR_POP_REGS_RET     = 0x804ED9BAE
    ADDR_RET              = 0x804ED9BB6
    ADDR_MOV_R14_RDI      = 0x804ED9BB7
    ADDR_MOV_R12_R15      = 0x804ED9BBA
    ADDR_NOP              = 0x804ED9BBD
    ADDR_LOOP_START       = 0x804ED9BC0
    ADDR_MOV_RDI_RBX_20   = 0x804ED9BC0
    ADDR_MOV_RSI_R14      = 0x804ED9BC4
    ADDR_CALL_STRCMP      = 0x804ED9BC7
    ADDR_TEST_EAX         = 0x804ED9BCC
    ADDR_LEA_RCX_RBX_10   = 0x804ED9BCE
    ADDR_CMOVNS_RCX_RBX   = 0x804ED9BD2
    ADDR_CMOVNS_R12_RBX   = 0x804ED9BD6
    ADDR_MOV_RBX_RCX      = 0x804ED9BDA
    ADDR_CMP_BYTE_RBX_19_2 = 0x804ED9BDD
    ADDR_JE_LOOP          = 0x804ED9BE1
    ADDR_CMP_R12_R15      = 0x804ED9BE3
    ADDR_JE_RETURN_0      = 0x804ED9BE6
    ADDR_MOV_RSI_R12_20   = 0x804ED9BE8
    ADDR_MOV_RDI_R14      = 0x804ED9BED
    ADDR_CALL_STRCMP_2    = 0x804ED9BF0
    ADDR_TEST_EAX_2       = 0x804ED9BF5
    ADDR_JS_RETURN_0      = 0x804ED9BF7
    ADDR_MOV_RAX_R12_28   = 0x804ED9BF9

    def __init__(self, memory, query_string):
        self.mem = memory
        self.regs = Regs()
        self.query = query_string
        self.query_addr = 0x50000000  # fake addr for the query string
        self.mem.string_addrs[query_string] = self.query_addr
        self.mem.string_store[self.query_addr] = query_string

        self.trace = []  # list of instruction trace records
        self.returned = False
        self.return_value = None
        self.step_count = 0
        self.max_steps = 500  # safety limit

        # Set up initial registers as if the wrapper called us
        self.regs.rdi = self.query_addr
        # rsp doesn't matter much; pick a high addr
        self.regs.rsp = 0x7FFFFFFFE000
        self.regs.rip = self.ADDR_PUSH_RBP

    def log_instruction(self, rip, mnemonic, operands, notes="", branch_decision=None):
        """Record one instruction's execution."""
        rec = {
            'step': self.step_count,
            'rip': f"0x{rip:x}",
            'mnemonic': mnemonic,
            'operands': operands,
            'RAX': f"0x{self.regs.rax:x}",
            'RBX': f"0x{self.regs.rbx:x}",
            'RCX': f"0x{self.regs.rcx:x}",
            'RDI': f"0x{self.regs.rdi:x}",
            'RSI': f"0x{self.regs.rsi:x}",
            'R12': f"0x{self.regs.r12:x}",
            'R14': f"0x{self.regs.r14:x}",
            'R15': f"0x{self.regs.r15:x}",
            'RFLAGS': str(self.regs.flags),
            'notes': notes,
            'branch': branch_decision,  # "TAKEN", "NOT_TAKEN", or None
        }
        self.trace.append(rec)

    def run(self):
        """Run the resolver to completion."""
        while not self.returned and self.step_count < self.max_steps:
            self.step_count += 1
            rip = self.regs.rip

            if rip == self.ADDR_PUSH_RBP:
                self.regs.rsp -= 8
                self.regs.rip = self.ADDR_MOV_RBP_RSP
                self.log_instruction(rip, "push", "rbp", "prologue")
            elif rip == self.ADDR_MOV_RBP_RSP:
                self.regs.rbp = self.regs.rsp
                self.regs.rip = self.ADDR_PUSH_R14_R15_R12_RBX
                self.log_instruction(rip, "mov", "rbp, rsp", "frame pointer")
            elif rip == self.ADDR_PUSH_R14_R15_R12_RBX:
                # push r15, r14, r12, rbx (4 pushes)
                self.regs.rsp -= 32
                self.regs.rip = self.ADDR_MOV_R15_RIP
                self.log_instruction(rip, "push", "r15; r14; r12; rbx", "save callee-saved")
            elif rip == self.ADDR_MOV_R15_RIP:
                # mov r15, [rip+0x3c79b66] → r15 = list head struct (= sentinel)
                self.regs.r15 = self.mem.read_u64(self.mem.list_head_ptr_addr)
                self.regs.rip = self.ADDR_MOV_RBX_R15_8
                self.log_instruction(rip, "mov", f"r15, [rip+0x3c79b66]",
                                     f"r15 = list_head_struct = 0x{self.regs.r15:x}")
            elif rip == self.ADDR_MOV_RBX_R15_8:
                # mov rbx, [r15+8] → rbx = root node
                self.regs.rbx = self.mem.read_u64(self.regs.r15 + 8)
                self.regs.rip = self.ADDR_CMP_BYTE_RBX_19
                self.log_instruction(rip, "mov", f"rbx, [r15+8]",
                                     f"rbx = root = 0x{self.regs.rbx:x}")
            elif rip == self.ADDR_CMP_BYTE_RBX_19:
                # cmp byte [rbx+0x19], 0
                val = self.mem.read_u8(self.regs.rbx + 0x19)
                result = val - 0
                self.regs.flags.set_from_sub_cmp(result, 0, val, size=1)
                # je = jump if ZF=1
                taken = self.regs.flags.ZF == 1
                next_rip = self.ADDR_MOV_R14_RDI if taken else self.ADDR_XOR_EAX
                self.regs.rip = next_rip
                self.log_instruction(rip, "cmp", f"byte [rbx+0x19]={val}, 0",
                                     f"flag_19={val} ({'SENTINEL' if val else 'real'})",
                                     "TAKEN→do_lookup" if taken else "NOT_TAKEN→return_0")
            elif rip == self.ADDR_JE_DO_LOOKUP:
                # Already handled above (we combined cmp+je for clarity)
                pass
            elif rip == self.ADDR_XOR_EAX:
                # xor eax, eax → rax = 0
                self.regs.rax = 0
                self.regs.flags.set_from_test(0)
                self.regs.rip = self.ADDR_RET
                self.log_instruction(rip, "xor", "eax, eax", "return value = 0")
            elif rip == self.ADDR_RET:
                self.returned = True
                self.return_value = self.regs.rax
                self.log_instruction(rip, "ret", "",
                                     f"RETURN rax=0x{self.regs.rax:x} ({'NULL' if self.regs.rax == 0 else 'non-zero'})")
            elif rip == self.ADDR_MOV_R14_RDI:
                # mov r14, rdi (save query string addr)
                self.regs.r14 = self.regs.rdi
                self.regs.rip = self.ADDR_MOV_R12_R15
                self.log_instruction(rip, "mov", "r14, rdi", f"r14 = query = 0x{self.regs.r14:x}")
            elif rip == self.ADDR_MOV_R12_R15:
                # mov r12, r15 (candidate = sentinel initially)
                self.regs.r12 = self.regs.r15
                self.regs.rip = self.ADDR_LOOP_START
                self.log_instruction(rip, "mov", "r12, r15",
                                     f"r12 = candidate = sentinel = 0x{self.regs.r12:x} (no candidate yet)")
            elif rip == self.ADDR_NOP:
                self.regs.rip = self.ADDR_LOOP_START
                self.log_instruction(rip, "nop", "", "")
            elif rip == self.ADDR_LOOP_START:
                # mov rdi, [rbx+0x20] → rdi = NODE symbol name addr
                self.regs.rdi = self.mem.read_u64(self.regs.rbx + 0x20)
                self.regs.rip = self.ADDR_MOV_RSI_R14
                node_name = self.mem.read_cstring(self.regs.rdi)
                self.log_instruction(rip, "mov", "rdi, [rbx+0x20]",
                                     f"rdi = NODE name addr = 0x{self.regs.rdi:x} ('{node_name}')")
            elif rip == self.ADDR_MOV_RSI_R14:
                # mov rsi, r14 → rsi = QUERY
                self.regs.rsi = self.regs.r14
                self.regs.rip = self.ADDR_CALL_STRCMP
                self.log_instruction(rip, "mov", "rsi, r14",
                                     f"rsi = QUERY = 0x{self.regs.rsi:x} ('{self.query}')")
            elif rip == self.ADDR_CALL_STRCMP:
                # call strcmp(rdi=NODE, rsi=QUERY) → rax = strcmp(NODE, QUERY)
                node_name = self.mem.read_cstring(self.regs.rdi)
                query_name = self.mem.read_cstring(self.regs.rsi)
                result = strcmp(node_name, query_name)
                # Convert to 32-bit signed
                if result < 0:
                    self.regs.rax = (1 << 64) + (result & 0xFFFFFFFF)  # negative as unsigned 64-bit
                else:
                    self.regs.rax = result & 0xFFFFFFFF
                # The CALL itself doesn't set flags; the callee's TEST does (next step)
                self.regs.rip = self.ADDR_TEST_EAX
                self.log_instruction(rip, "call", "strcmp",
                                     f"strcmp('{node_name}', '{query_name}') = {result} → rax = 0x{self.regs.rax:x}")
            elif rip == self.ADDR_TEST_EAX:
                # test eax, eax
                eax_val = self.regs.rax & 0xFFFFFFFF
                # Convert to signed 32-bit
                if eax_val & 0x80000000:
                    eax_signed = eax_val - (1 << 32)
                else:
                    eax_signed = eax_val
                self.regs.flags.set_from_test(eax_val, size=4)
                self.regs.rip = self.ADDR_LEA_RCX_RBX_10
                self.log_instruction(rip, "test", "eax, eax",
                                     f"eax = {eax_signed} (0x{eax_val:x}) → {self.regs.flags}")
            elif rip == self.ADDR_LEA_RCX_RBX_10:
                # lea rcx, [rbx+0x10] → rcx = LEFT child addr
                self.regs.rcx = self.regs.rbx + 0x10
                self.regs.rip = self.ADDR_CMOVNS_RCX_RBX
                self.log_instruction(rip, "lea", "rcx, [rbx+0x10]",
                                     f"rcx = LEFT addr = 0x{self.regs.rcx:x} (default: go LEFT)")
            elif rip == self.ADDR_CMOVNS_RCX_RBX:
                # cmovns rcx, rbx → if SF=0: rcx = rbx (use RIGHT child)
                taken = self.regs.flags.SF == 0
                if taken:
                    self.regs.rcx = self.regs.rbx  # rcx = rbx (RIGHT child addr)
                self.regs.rip = self.ADDR_CMOVNS_R12_RBX
                decision = "TAKEN → rcx = rbx (use RIGHT child)"
                if not taken:
                    decision = "NOT_TAKEN → rcx stays (use LEFT child)"
                self.log_instruction(rip, "cmovns", "rcx, rbx",
                                     f"SF={self.regs.flags.SF} → {decision}", "TAKEN" if taken else "NOT_TAKEN")
            elif rip == self.ADDR_CMOVNS_R12_RBX:
                # cmovns r12, rbx → if SF=0: r12 = rbx (candidate = current)
                taken = self.regs.flags.SF == 0
                if taken:
                    self.regs.r12 = self.regs.rbx  # candidate = current node
                self.regs.rip = self.ADDR_MOV_RBX_RCX
                decision = "TAKEN → r12 = rbx (candidate updated)"
                if not taken:
                    decision = "NOT_TAKEN → r12 unchanged (no candidate update)"
                self.log_instruction(rip, "cmovns", "r12, rbx",
                                     f"SF={self.regs.flags.SF} → {decision}", "TAKEN" if taken else "NOT_TAKEN")
            elif rip == self.ADDR_MOV_RBX_RCX:
                # mov rbx, [rcx] → rbx = next node
                # rcx is either rbx (RIGHT) or rbx+0x10 (LEFT)
                # If rcx == rbx_old, then [rcx] = [rbx_old + 0x00] = right child
                # If rcx == rbx_old + 0x10, then [rcx] = [rbx_old + 0x10] = left child
                self.regs.rbx = self.mem.read_u64(self.regs.rcx)
                self.regs.rip = self.ADDR_CMP_BYTE_RBX_19_2
                self.log_instruction(rip, "mov", "rbx, [rcx]",
                                     f"rbx = next node = 0x{self.regs.rbx:x}")
            elif rip == self.ADDR_CMP_BYTE_RBX_19_2:
                # cmp byte [rbx+0x19], 0 (sentinel check after move)
                val = self.mem.read_u8(self.regs.rbx + 0x19)
                result = val - 0
                self.regs.flags.set_from_sub_cmp(result, 0, val, size=1)
                # je = jump if ZF=1 (i.e., val == 0, meaning NOT sentinel → continue loop)
                taken = self.regs.flags.ZF == 1
                next_rip = self.ADDR_LOOP_START if taken else self.ADDR_CMP_R12_R15
                self.regs.rip = next_rip
                self.log_instruction(rip, "cmp", f"byte [rbx+0x19]={val}, 0",
                                     f"flag_19={val} ({'SENTINEL' if val else 'real'})",
                                     "TAKEN→loop" if taken else "NOT_TAKEN→after_loop")
            elif rip == self.ADDR_CMP_R12_R15:
                # cmp r12, r15 → is candidate still sentinel?
                result = self.regs.r12 - self.regs.r15
                self.regs.flags.set_from_sub_cmp(result, self.regs.r15, self.regs.r12, size=8)
                # je = jump if ZF=1 (candidate == sentinel → no candidate → return 0)
                taken = self.regs.flags.ZF == 1
                next_rip = self.ADDR_XOR_EAX if taken else self.ADDR_MOV_RSI_R12_20
                self.regs.rip = next_rip
                self.log_instruction(rip, "cmp", "r12, r15",
                                     f"r12=0x{self.regs.r12:x} r15=0x{self.regs.r15:x}",
                                     "TAKEN→return_0 (no candidate)" if taken else "NOT_TAKEN→final_check")
            elif rip == self.ADDR_MOV_RSI_R12_20:
                # mov rsi, [r12+0x20] → rsi = CANDIDATE symbol name
                self.regs.rsi = self.mem.read_u64(self.regs.r12 + 0x20)
                self.regs.rip = self.ADDR_MOV_RDI_R14
                cand_name = self.mem.read_cstring(self.regs.rsi)
                self.log_instruction(rip, "mov", "rsi, [r12+0x20]",
                                     f"rsi = CANDIDATE name addr = 0x{self.regs.rsi:x} ('{cand_name}')")
            elif rip == self.ADDR_MOV_RDI_R14:
                # mov rdi, r14 → rdi = QUERY
                self.regs.rdi = self.regs.r14
                self.regs.rip = self.ADDR_CALL_STRCMP_2
                self.log_instruction(rip, "mov", "rdi, r14",
                                     f"rdi = QUERY = 0x{self.regs.rdi:x} ('{self.query}')")
            elif rip == self.ADDR_CALL_STRCMP_2:
                # call strcmp(rdi=QUERY, rsi=CANDIDATE) → rax = strcmp(QUERY, CANDIDATE)
                cand_name = self.mem.read_cstring(self.regs.rsi)
                query_name = self.mem.read_cstring(self.regs.rdi)
                result = strcmp(query_name, cand_name)
                if result < 0:
                    self.regs.rax = (1 << 64) + (result & 0xFFFFFFFF)
                else:
                    self.regs.rax = result & 0xFFFFFFFF
                self.regs.rip = self.ADDR_TEST_EAX_2
                self.log_instruction(rip, "call", "strcmp (final)",
                                     f"strcmp('{query_name}', '{cand_name}') = {result} → rax = 0x{self.regs.rax:x}")
            elif rip == self.ADDR_TEST_EAX_2:
                # test eax, eax
                eax_val = self.regs.rax & 0xFFFFFFFF
                if eax_val & 0x80000000:
                    eax_signed = eax_val - (1 << 32)
                else:
                    eax_signed = eax_val
                self.regs.flags.set_from_test(eax_val, size=4)
                self.regs.rip = self.ADDR_JS_RETURN_0
                self.log_instruction(rip, "test", "eax, eax",
                                     f"eax = {eax_signed} (0x{eax_val:x}) → {self.regs.flags}")
            elif rip == self.ADDR_JS_RETURN_0:
                # js → if SF=1 (QUERY < CANDIDATE), return 0
                taken = self.regs.flags.SF == 1
                next_rip = self.ADDR_XOR_EAX if taken else self.ADDR_MOV_RAX_R12_28
                self.regs.rip = next_rip
                self.log_instruction(rip, "js", "return_0",
                                     f"SF={self.regs.flags.SF}",
                                     "TAKEN→return_0 (QUERY<CANDIDATE)" if taken else "NOT_TAKEN→return_func_ptr")
            elif rip == self.ADDR_MOV_RAX_R12_28:
                # mov rax, [r12+0x28] → rax = func_impl
                self.regs.rax = self.mem.read_u64(self.regs.r12 + 0x28)
                self.regs.rip = self.ADDR_RET
                self.log_instruction(rip, "mov", "rax, [r12+0x28]",
                                     f"rax = func_impl = 0x{self.regs.rax:x} (SUCCESS)")
            else:
                self.log_instruction(rip, "?", "?", f"UNKNOWN RIP — stopping")
                break

        return self.return_value


# ===========================================================================
# Reference implementation (Python RBTree search)
# ===========================================================================

def reference_search(tree_data, query):
    """Run the reference Python RBTree search and return path."""
    nodes = tree_data['nodes']
    root_addr = tree_data['root_node_addr']
    list_head_struct = tree_data['list_head_struct_addr']

    # Find sentinel addr (the list head struct IS the sentinel)
    sentinel_addr = list_head_struct

    path = []
    current = root_addr
    candidate = sentinel_addr  # use sentinel as "no candidate" marker

    level = 0
    while True:
        node = nodes.get(f"0x{current:x}")
        if node is None:
            path.append({'level': level, 'addr': current, 'name': '<missing>',
                         'action': 'MISSING_NODE — stop'})
            break

        if node['flag_19'] == 1:  # sentinel
            path.append({'level': level, 'addr': current, 'name': '<SENTINEL>',
                         'action': 'SENTINEL — exit loop'})
            break

        node_name = node['name']
        cmp = strcmp(node_name, query)
        # strcmp(NODE, QUERY) >= 0 → go RIGHT, update candidate
        if cmp >= 0:
            candidate = current
            next_node = node['right']
            direction = 'RIGHT (update candidate)'
        else:
            next_node = node['left']
            direction = 'LEFT'

        path.append({
            'level': level,
            'addr': current,
            'name': node_name,
            'left': node['left'],
            'right': node['right'],
            'cmp_NODE_QUERY': cmp,
            'direction': direction,
            'next': next_node,
            'candidate': candidate,
        })

        current = next_node
        level += 1
        if level > 30:
            path.append({'level': level, 'addr': current, 'name': '?',
                         'action': 'MAX_DEPTH — stop'})
            break

    # Final check
    final_result = None
    if candidate == sentinel_addr:
        final_result = ('NULL', 'no candidate found')
    else:
        cand_node = nodes.get(f"0x{candidate:x}")
        if cand_node:
            cand_name = cand_node['name']
            final_cmp = strcmp(query, cand_name)  # strcmp(QUERY, CANDIDATE)
            if final_cmp < 0:
                final_result = ('NULL', f'QUERY < CANDIDATE (strcmp(QUERY,CANDIDATE)={final_cmp})')
            elif final_cmp == 0:
                final_result = (f"0x{cand_node['func_ptr']:x}", f'EXACT MATCH (strcmp(QUERY,CANDIDATE)=0)')
            else:
                # QUERY > CANDIDATE — but js only triggers if SF=1 (negative)
                # If strcmp(QUERY, CANDIDATE) > 0, js is NOT taken → return func_ptr
                final_result = (f"0x{cand_node['func_ptr']:x}",
                                f'QUERY > CANDIDATE (strcmp(QUERY,CANDIDATE)={final_cmp}) → js NOT taken → return func_ptr')

    return path, final_result


# ===========================================================================
# Main: run synthetic CPU and compare with reference
# ===========================================================================

def main():
    queries = sys.argv[1:] if len(sys.argv) > 1 else ['il2cpp_init']

    if not Path(TREE_JSON).exists():
        print(f"[!] Tree JSON not found at {TREE_JSON}")
        print(f"    Run exp026_build_tree.py first.")
        sys.exit(1)

    tree_data = json.loads(Path(TREE_JSON).read_text())
    mem = Memory(tree_data)

    print(f"[*] Tree loaded: {len(tree_data['nodes'])} nodes")
    print(f"[*] Root: 0x{tree_data['root_node_addr']:x}")
    print(f"[*] List head struct (= sentinel): 0x{tree_data['list_head_struct_addr']:x}")
    print(f"[*] List head ptr addr: 0x{tree_data['list_head_ptr_addr']:x}")
    print()

    all_results = []

    for query in queries:
        print("=" * 80)
        print(f"QUERY: '{query}'")
        print("=" * 80)

        # Run synthetic CPU
        cpu = SyntheticResolverCPU(mem, query)
        result = cpu.run()

        print(f"\n[SYNTHETIC CPU] Result: 0x{result:x} ({'NULL' if result == 0 else 'NON-ZERO'})")
        print(f"[SYNTHETIC CPU] Steps: {cpu.step_count}")
        print()
        print("[SYNTHETIC CPU] Instruction trace:")
        for rec in cpu.trace:
            line = f"  {rec['step']:3d} {rec['rip']:18s}  {rec['mnemonic']:8s} {rec['operands']:25s}"
            if rec['notes']:
                line += f"  | {rec['notes']}"
            if rec['branch']:
                line += f"  [{rec['branch']}]"
            print(line)

        # Run reference
        ref_path, ref_result = reference_search(tree_data, query)
        print(f"\n[REFERENCE] Result: {ref_result[0]} ({ref_result[1]})")
        print(f"[REFERENCE] Path:")
        for step in ref_path:
            if 'action' in step:
                print(f"  L{step['level']}: 0x{step['addr']:x} {step['name']} → {step['action']}")
            else:
                print(f"  L{step['level']}: 0x{step['addr']:x} sym='{step['name']}' "
                      f"strcmp(NODE,QUERY)={step['cmp_NODE_QUERY']} → {step['direction']} "
                      f"→ next=0x{step['next']:x} (candidate=0x{step['candidate']:x})")

        # Compare
        synthetic_ok = result != 0
        ref_ok = ref_result[0] != 'NULL'
        match = synthetic_ok == ref_ok

        print(f"\n[COMPARISON]")
        print(f"  Synthetic: {'FOUND' if synthetic_ok else 'NULL'}")
        print(f"  Reference: {'FOUND' if ref_ok else 'NULL'}")
        print(f"  Match:     {'YES' if match else 'NO — DIVERGENCE!'}")

        all_results.append({
            'query': query,
            'synthetic_result': f"0x{result:x}",
            'reference_result': ref_result[0],
            'match': match,
            'synthetic_steps': cpu.step_count,
            'reference_path_length': len(ref_path),
        })

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for r in all_results:
        status = 'OK' if r['match'] else 'DIVERGENCE'
        print(f"  {r['query']:40s}  synth={r['synthetic_result']:20s}  ref={r['reference_result']:20s}  [{status}]")

    # Save full trace to file
    out_path = '/home/z/my-project/scripts/exp026_synthetic_trace.json'
    Path(out_path).write_text(json.dumps({
        'queries': all_results,
        'first_query_full_trace': cpu.trace if cpu.trace else [],
    }, indent=2))
    print(f"\n[+] Full trace saved to {out_path}")


if __name__ == '__main__':
    main()
