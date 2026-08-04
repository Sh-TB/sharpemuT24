#!/usr/bin/env python3
"""EXP-079: Compute PS5 NID hashes for relevant symbols and match them to GOT slots."""
import sys, hashlib, base64, struct
sys.path.insert(0, '/home/z/my-project/scripts')

PS5_NAMES_FILE = "/tmp/my-project/work/sharpemuT24/scripts/ps5_names.txt"
PS5_SUFFIX = bytes([0x51, 0x8D, 0x64, 0xA6, 0x35, 0xDE, 0xD8, 0xC1,
                    0xE6, 0xB0, 0x39, 0xB1, 0xC3, 0xE5, 0x52, 0x30])

def compute_nid(name):
    h = hashlib.sha1(name.encode('utf-8') + PS5_SUFFIX).digest()
    reversed_bytes = h[:8][::-1]
    # PS5 NID encoding uses URL-safe base64 with no padding? Actually uses standard +,-
    s = base64.b64encode(reversed_bytes).decode('ascii').rstrip('=')
    # The catalog seems to use '+','/' alphabet (not URL-safe)
    return s

def main():
    # Build NID → name map
    nid_to_name = {}
    with open(PS5_NAMES_FILE) as f:
        for line in f:
            name = line.strip()
            if not name: continue
            nid = compute_nid(name)
            if nid in nid_to_name:
                # Don't overwrite — first wins
                pass
            else:
                nid_to_name[nid] = name
    
    print(f"Built NID map: {len(nid_to_name)} entries")
    
    # Target NIDs from our GOT slot analysis
    targets = {
        '2Of0f+3mhhE': '0x801D1AD80 (CLEAR calls 0x801937610 on [r12+0x30])',
        '4czppHBiriw': '0x801D1AE50 (CLEAR calls 0x8019377b0 with rdi=handle,esi=1)',
        'R1Jvn8bSCW8': '0x801D1AE60 (CLEAR calls 0x8019377d0 with rdi=handle,eax=count)',
        'cd+Rtw+D1x8': '0x801D1AE68 (0x8019377e0)',
        'JK2wamZPzwM': '0x801D1AE70 (0x8019377f0)',
        'onNY9Byn-W8': '0x801D1AE58 (0x8019377c0)',
    }
    
    print("\n=== Resolved GOT slots ===")
    for nid, who in targets.items():
        name = nid_to_name.get(nid, '<NOT IN CATALOG>')
        print(f"  NID {nid}  →  '{name}'   ({who})")
    
    # Also check our task: what NID is "sceKernelSignalSema"?
    print("\n=== Key PS5 symbol NIDs ===")
    for sym in ['sceKernelSignalSema', 'sceKernelWaitSema', 'sceKernelCreateSema',
                'sceKernelDeleteSema', 'sceKernelPollSema', 'sceKernelCancelSema',
                'sceKernelOpenSema', 'sceKernelCloseSema',
                'scePthreadCondSignal', 'scePthreadCondWait', 'scePthreadCondTimedwait',
                'scePthreadMutexLock', 'scePthreadMutexUnlock',
                'Baselib_SystemSemaphore_Signal', 'Baselib_SystemSemaphore_Wait',
                'Baselib_SystemSemaphore_TryAcquire', 'Baselib_SystemSemaphore_Release',
                'Baselib_SystemSemaphore_NotifyOne', 'Baselib_SystemSemaphore_NotifyAll',
                'Baselib_Thread_WaitForCondition', 'Baselib_Thread_Sleep',
                '_Mtx_lock', '_Mtx_unlock', '_Cnd_wait', '_Cnd_signal', '_Cnd_broadcast']:
        nid = compute_nid(sym)
        print(f"  {sym:48s}  →  NID {nid}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
