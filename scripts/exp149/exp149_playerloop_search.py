#!/usr/bin/env python3
"""
EXP-149 Step 4: Search for PlayerLoop registration in the PRX.
NOT repeating XREF search (done in EXP-148).
Instead: search for strings, method names, registration table patterns.
"""

import struct

PRX_PATH = "/tmp/exp125_games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
EBOOT_PATH = "/tmp/exp125_games/yatzi/eboot.bin"
PRX_BASE = 0x804CD5000
EBOOT_BASE = 0x800000000

def parse_elf64(path):
    data = open(path, 'rb').read()
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_flags = struct.unpack_from('<I', data, off + 4)[0]
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        segments.append({'type': p_type, 'flags': p_flags, 'offset': p_offset,
                         'vaddr': p_vaddr, 'filesz': p_filesz})
    return data, segments

def search_strings(data, segments, patterns, binary_name, load_base):
    """Search for string patterns in data sections."""
    print(f"\n  Searching in {binary_name}...")
    for pat in patterns:
        pat_bytes = pat.encode('utf-8') + b'\x00'
        idx = 0
        hits = []
        while True:
            i = data.find(pat_bytes, idx)
            if i == -1:
                break
            # Find which segment
            for seg in segments:
                if seg['offset'] <= i < seg['offset'] + seg['filesz']:
                    vaddr = seg['vaddr'] + (i - seg['offset'])
                    runtime = load_base + vaddr
                    seg_type = 'CODE' if seg['flags'] & 1 else ('DATA-W' if seg['flags'] & 2 else 'DATA-R')
                    hits.append((runtime, seg_type))
                    break
            idx = i + 1
        if hits:
            print(f"    '{pat}': {len(hits)} hits")
            for runtime, seg_type in hits[:5]:
                print(f"      0x{runtime:X} ({seg_type})")
        else:
            print(f"    '{pat}': NOT FOUND")

def main():
    print("=" * 80)
    print("EXP-149 Step 4: PlayerLoop Registration Search in PRX")
    print("=" * 80)
    
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    
    # Search for PlayerLoop-related strings
    print("\n[1] Searching for PlayerLoop-related strings:")
    player_loop_patterns = [
        'PlayerLoop',
        'PlayerLoopInterface',
        'PlayerLoopInternal',
        'RegisterPlayerLoop',
        'InitPlayerLoop',
        'SetupPlayerLoop',
        'playerloop',
        'PlayerLoopRunner',
        'UnityPlayerLoop',
        'LowLevel',
        'InitializePlayerLoop',
        'PlayerLoopSystem',
        'NativePlayerLoop',
        'RegisterPlayerLoopCallbacks',
    ]
    search_strings(prx_data, prx_segs, player_loop_patterns, "PRX", PRX_BASE)
    search_strings(eboot_data, eboot_segs, player_loop_patterns, "eboot", EBOOT_BASE)
    
    # Search for bootstrap-related strings
    print("\n[2] Searching for bootstrap-related strings:")
    bootstrap_patterns = [
        'bootstrap',
        'Bootstrap',
        'BootStrap',
        'Initialize',
        'init_runtime',
        'runtime_init',
        'il2cpp_init',
        'il2cpp_runtime_init',
        'Start_Runtime',
        'GameInit',
        'GameStart',
        'MainLoop',
        'main_loop',
    ]
    search_strings(prx_data, prx_segs, bootstrap_patterns, "PRX", PRX_BASE)
    search_strings(eboot_data, eboot_segs, bootstrap_patterns, "eboot", EBOOT_BASE)
    
    # Search for job system strings
    print("\n[3] Searching for job system strings:")
    job_patterns = [
        'ScheduleJob',
        'ScheduleBatchedJobs',
        'Schedule_Injected',
        'JobQueue',
        'JobSystem',
        'BatchJob',
        'SubmitJob',
        'EnqueueJob',
        'JobHandle',
        'Unity.Jobs',
        'JobsUtility',
        'JobWorker',
    ]
    search_strings(prx_data, prx_segs, job_patterns, "PRX", PRX_BASE)
    search_strings(eboot_data, eboot_segs, job_patterns, "eboot", EBOOT_BASE)
    
    # Search for IL2CPP method registration strings
    print("\n[4] Searching for IL2CPP method registration strings:")
    il2cpp_patterns = [
        'il2cpp_codegen_initialize_runtime_metadata',
        'il2cpp_codegen_initialize_method',
        'il2cpp_codegen_initialize',
        'Il2CppCodeGenOptions',
        'g_AssemblyU2DCallBack',
        'CodeGenModule',
        's_Il2CppCodegenRegistration',
        'il2cpp_codegen_register',
        'Il2CppCodeRegistration',
        'Il2CppMetadataRegistration',
        'g_CodeRegistration',
        'g_MetadataRegistration',
    ]
    search_strings(prx_data, prx_segs, il2cpp_patterns, "PRX", PRX_BASE)
    search_strings(eboot_data, eboot_segs, il2cpp_patterns, "eboot", EBOOT_BASE)
    
    # Search for Unity callback registration strings
    print("\n[5] Searching for Unity callback registration strings:")
    callback_patterns = [
        'RegisterCallback',
        'AddCallback',
        'SetCallback',
        'InstallCallback',
        'PlayerLoopCallbacks',
        'EarlyUpdate',
        'Update',
        'LateUpdate',
        'FixedUpdate',
        'PreUpdate',
        'PostLateUpdate',
        'PlayerLoopUpdate',
        'TimeUpdate',
    ]
    search_strings(prx_data, prx_segs, callback_patterns, "PRX", PRX_BASE)
    search_strings(eboot_data, eboot_segs, callback_patterns, "eboot", EBOOT_BASE)
    
    # Search for the dt_init function and trace its call chain
    print("\n[6] Analyzing dt_init (module_start) at 0x804CD5010:")
    dt_init = 0x804CD5010
    dt_init_vaddr = dt_init - PRX_BASE
    dt_foff = None
    for seg in prx_segs:
        if seg['vaddr'] <= dt_init_vaddr < seg['vaddr'] + seg['filesz']:
            dt_foff = seg['offset'] + (dt_init_vaddr - seg['vaddr'])
            break
    
    if dt_foff:
        print(f"  File offset: 0x{dt_foff:X}")
        # Read first 256 bytes and look for CALL instructions
        chunk = prx_data[dt_foff:dt_foff + 512]
        print(f"  First 64 bytes: {chunk[:64].hex()}")
        
        # Find all E8 CALL instructions in the first 512 bytes
        print(f"  CALL instructions in first 512 bytes:")
        for i in range(len(chunk) - 5):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = dt_init + i
                target = call_addr + 5 + rel
                print(f"    0x{call_addr:X}: call 0x{target:X}")
    
    # Search for the function that creates the GC thread (entry 0x804F88AA0)
    print("\n[7] Finding what creates the GC thread (entry 0x804F88AA0):")
    gc_thread_entry = 0x804F88AA0
    gc_entry_bytes = struct.pack('<Q', gc_thread_entry)
    
    # Search for this address in eboot data sections (it's passed as argument to pthread_create)
    print(f"  Searching for 0x{gc_thread_entry:X} as 64-bit LE in eboot data...")
    for seg in eboot_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = eboot_data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(gc_entry_bytes, idx)
            if i == -1:
                break
            ref_runtime = EBOOT_BASE + seg['vaddr'] + i
            print(f"    Found at 0x{ref_runtime:X}")
            idx = i + 1
    
    # Also search in PRX data
    print(f"  Searching for 0x{gc_thread_entry:X} as 64-bit LE in PRX data...")
    for seg in prx_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = prx_data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(gc_entry_bytes, idx)
            if i == -1:
                break
            ref_runtime = PRX_BASE + seg['vaddr'] + i
            print(f"    Found at 0x{ref_runtime:X}")
            idx = i + 1
    
    # Search for the AGC thread entry (0x800BB06A0)
    print("\n[8] Finding what creates AGC threads (entry 0x800BB06A0):")
    agc_entry = 0x800BB06A0
    agc_entry_bytes = struct.pack('<Q', agc_entry)
    
    print(f"  Searching for 0x{agc_entry:X} as 64-bit LE in eboot data...")
    for seg in eboot_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = eboot_data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(agc_entry_bytes, idx)
            if i == -1:
                break
            ref_runtime = EBOOT_BASE + seg['vaddr'] + i
            print(f"    Found at 0x{ref_runtime:X}")
            idx = i + 1
    
    print(f"  Searching for 0x{agc_entry:X} as 64-bit LE in PRX data...")
    for seg in prx_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = prx_data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(agc_entry_bytes, idx)
            if i == -1:
                break
            ref_runtime = PRX_BASE + seg['vaddr'] + i
            print(f"    Found at 0x{ref_runtime:X}")
            idx = i + 1
    
    # Search for the dispatch loop entry (0x804F6E510)
    print("\n[9] Finding references to dispatch loop (0x804F6E510):")
    dispatch_loop = 0x804F6E510
    dispatch_bytes = struct.pack('<Q', dispatch_loop)
    
    print(f"  Searching for 0x{dispatch_loop:X} as 64-bit LE in PRX data...")
    for seg in prx_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = prx_data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(dispatch_bytes, idx)
            if i == -1:
                break
            ref_runtime = PRX_BASE + seg['vaddr'] + i
            print(f"    Found at 0x{ref_runtime:X}")
            idx = i + 1
    
    print(f"  Searching for 0x{dispatch_loop:X} as 64-bit LE in eboot data...")
    for seg in eboot_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = eboot_data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(dispatch_bytes, idx)
            if i == -1:
                break
            ref_runtime = EBOOT_BASE + seg['vaddr'] + i
            print(f"    Found at 0x{ref_runtime:X}")
            idx = i + 1
    
    print("\n" + "=" * 80)
    print("Search Complete")
    print("=" * 80)

if __name__ == '__main__':
    main()
