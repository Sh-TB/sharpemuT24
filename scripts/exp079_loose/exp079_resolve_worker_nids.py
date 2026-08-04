#!/usr/bin/env python3
"""EXP-079: Resolve NIDs for all PLT calls in the worker function."""
import sys, struct, hashlib, base64
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000
PS5_NAMES_FILE = "/tmp/my-project/work/sharpemuT24/scripts/ps5_names.txt"
PS5_SUFFIX = bytes([0x51, 0x8D, 0x64, 0xA6, 0x35, 0xDE, 0xD8, 0xC1,
                    0xE6, 0xB0, 0x39, 0xB1, 0xC3, 0xE5, 0x52, 0x30])

def compute_nid(name):
    h = hashlib.sha1(name.encode('utf-8') + PS5_SUFFIX).digest()
    reversed_bytes = h[:8][::-1]
    return base64.b64encode(reversed_bytes).decode('ascii').rstrip('=')

def main():
    img = ElfImage(EBOOT_PATH)
    
    # Build NID → name map (limited to relevant names)
    relevant_keywords = ['Sema', 'Mutex', 'Cond', 'Wait', 'Signal', 'Baselib', 'Thread', 'Lock', 'Unlock', 'Sync', 'Wake', 'Notif', 'Pool', 'Job', 'Task', 'Cnd', 'Mtx']
    nid_to_name = {}
    with open(PS5_NAMES_FILE) as f:
        for line in f:
            name = line.strip()
            if not name: continue
            # Only compute if name might be relevant
            if any(k in name for k in relevant_keywords):
                nid = compute_nid(name)
                if nid not in nid_to_name:
                    nid_to_name[nid] = name
    
    # PLT calls in worker function 0x800AA0170
    plt_targets = {
        0x801937720: 'WAIT? called with rdi=sema,esi=1,edx=0',
        0x8019377b0: 'SIGNAL? called with rdi=sema,esi=1',
        0x8019377d0: 'DELETE? called with rdi=sema',
        0x801937610: 'CLEAR calls on [r12+0x30]',
        # Also: 0x801937500, 0x8019377d0, 0x801938160, 0x800BB0860, 0x8007E2280
        0x801937500: 'inside 0x800BB0860 (worker_wake)',
        0x801938160: 'ud2 caller (assert?)',
        0x800B85330: 'called from init/worker functions',
        0x8015450F0: 'called from worker_main 0x800AA0050',
        0x8019366A0: 'called from init 0x800A9F414',
        0x801585CC0: 'called from init 0x800A9F423',
        0x8019369B0: 'error/log function',
        0x8007DF6C0: 'called from FREE_HELPER 0x8007E22B6',
        0x801936840: 'called from FREE_HELPER 0x8007E2314',
        0x801936800: 'called from FREE_HELPER 0x8007E22FC',
    }
    
    # Read PLT thunk: jmp [rip+disp32]
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from capstone.x86 import X86_REG_RIP, X86_OP_MEM
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    
    print("=== PLT call resolutions ===")
    for plt_addr, ctx in sorted(plt_targets.items()):
        vaddr = plt_addr - PS5_BASE
        data = img.read_bytes(vaddr, 16)
        if not data or data[0] != 0xFF or data[1] != 0x25:
            print(f"  0x{plt_addr:X}: not a PLT thunk (data={data[:8].hex()})")
            continue
        # jmp [rip + disp32]
        disp32 = struct.unpack_from('<i', data, 2)[0]
        got_addr = plt_addr + 6 + disp32
        # Look up GOT slot in PLT map
        # Re-read PLT map for this slot
        got_vaddr = got_addr - PS5_BASE
        # Read the GOT slot value (initial value points back to PLT)
        got_off = img.vaddr_to_offset(got_vaddr)
        # Use PLT map from /tmp/exp079_plt_map.txt
        nid = None
        try:
            with open('/tmp/exp079_plt_map.txt') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) == 2:
                        addr_str, name_nid = parts
                        if int(addr_str, 16) == got_vaddr:
                            nid = name_nid.split('#')[0]
                            break
        except FileNotFoundError:
            pass
        
        sym_name = nid_to_name.get(nid, '<NOT IN CATALOG>') if nid else '<GOT not in PLT map>'
        print(f"  PLT 0x{plt_addr:X} → GOT 0x{got_addr:X} → NID '{nid}' → '{sym_name}'   ({ctx})")
    
    # Also check what 0x8007E2280 (FREE_HELPER) actually does — already done
    # And 0x800BB0860 (worker wake)
    return 0

if __name__ == "__main__":
    sys.exit(main())
