#!/usr/bin/env python3
"""
EXP-151 Steps 1-5: Comprehensive PlayerLoop registration investigation.

Step 1: Analyze the gate at 0x804FB8E60 — determine if je jumps TO init or PAST init
Step 2: Search PRX for PlayerLoop registration code and Unity startup strings
Step 3: Trace managed execution path — find il2cpp_runtime_invoke function address
Step 4: Search for function pointer tables (delegate tables, callback tables)
Step 5: Compare against real Unity startup model
"""

import struct
import sys

EBOOT_PATH = "/tmp/exp151_games/eboot.bin"
PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
METADATA_PATH = "/tmp/exp151_games/global-metadata.dat"

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
        p_memsz = struct.unpack_from('<Q', data, off + 40)[0]
        segments.append({'type': p_type, 'flags': p_flags, 'offset': p_offset,
                         'vaddr': p_vaddr, 'filesz': p_filesz, 'memsz': p_memsz})
    return data, segments

def runtime_to_file(segments, runtime, load_base):
    vaddr = runtime - load_base
    for seg in segments:
        if seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
            return seg['offset'] + (vaddr - seg['vaddr'])
    return None

def hex_dump(data, foff, count, base_addr):
    for i in range(0, count, 16):
        if foff + i >= len(data):
            break
        addr = base_addr + i
        chunk = data[foff + i:foff + min(i + 16, count)]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        print(f"  0x{addr:X}: {hex_str}")

def search_strings(data, patterns, binary_name):
    """Search for string patterns in binary."""
    results = {}
    for pat in patterns:
        pat_bytes = pat.encode('utf-8') + b'\x00'
        idx = 0
        hits = []
        while True:
            i = data.find(pat_bytes, idx)
            if i == -1:
                break
            hits.append(i)
            idx = i + 1
        if hits:
            results[pat] = hits
    return results

def find_callers_of(data, segments, target_addr, load_base):
    """Find all E8 CALL instructions targeting target_addr."""
    callers = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
            if data[i] == 0xE8:
                rel = struct.unpack_from('<i', data, i + 1)[0]
                call_addr = load_base + seg['vaddr'] + (i - seg['offset'])
                target = call_addr + 5 + rel
                if target == target_addr:
                    callers.append(call_addr)
    return callers

def find_function_start(data, segments, addr, load_base):
    """Find function start by searching backward for prologue."""
    foff = runtime_to_file(segments, addr, load_base)
    if foff is None:
        return None
    for back in range(0, 4096):
        if foff - back < 0:
            return None
        if foff - back + 4 <= len(data):
            b = data[foff - back:foff - back + 4]
            if b == b'\x55\x48\x89\xe5':
                if foff - back - 1 >= 0:
                    prev = data[foff - back - 1]
                    if prev in (0xCC, 0xC3, 0xC9):
                        return addr - back
    return None

def follow_jmp(data, segments, addr, load_base, depth=0, visited=None):
    """Follow JMP thunks to find the real function."""
    if visited is None:
        visited = set()
    if addr in visited or depth > 10:
        return addr
    visited.add(addr)
    foff = runtime_to_file(segments, addr, load_base)
    if foff is None or foff >= len(data) - 5:
        return addr
    if data[foff] == 0xE9:
        rel = struct.unpack_from('<i', data, foff + 1)[0]
        target = addr + 5 + rel
        return follow_jmp(data, segments, target, load_base, depth + 1, visited)
    return addr


def main():
    print("=" * 80)
    print("EXP-151: Comprehensive PlayerLoop Registration Investigation")
    print("=" * 80)
    
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    
    print(f"\nPRX size: {len(prx_data)} bytes")
    print(f"Eboot size: {len(eboot_data)} bytes")
    
    # ===== STEP 1: Analyze gate at 0x804FB8E60 =====
    print("\n" + "=" * 80)
    print("STEP 1: Gate Analysis at 0x804FB8E60")
    print("=" * 80)
    
    gate_addr = 0x804FB8E60
    gate_foff = runtime_to_file(prx_segs, gate_addr, PRX_BASE)
    
    print(f"\nGate function at 0x{gate_addr:X} (file: 0x{gate_foff:X}):")
    print("First 96 bytes:")
    hex_dump(prx_data, gate_foff, 96, gate_addr)
    
    # The gate: cmp byte [rip+0x3DAED31], 0; je +0x28
    # Byte address = 0x804FB8E60 + 7 + 0x3DAED31 = 0x808D67B98
    byte_addr = gate_addr + 7 + 0x3DAED31
    print(f"\nByte address: 0x{byte_addr:X}")
    
    # je target = 0x804FB8E60 + 7 + 2 + 0x28 = 0x804FB8E91
    je_target = gate_addr + 7 + 2 + 0x28
    print(f"je target (if byte==0): 0x{je_target:X}")
    
    # Disassemble the code at the je target to see if it's init or skip
    print(f"\nCode at je target (0x{je_target:X}):")
    je_foff = runtime_to_file(prx_segs, je_target, PRX_BASE)
    if je_foff:
        hex_dump(prx_data, je_foff, 64, je_target)
    
    # Also show the not-taken path (byte != 0)
    not_taken = gate_addr + 9
    print(f"\nNot-taken path (byte != 0, 0x{not_taken:X}):")
    hex_dump(prx_data, gate_foff + 9, 64, not_taken)
    
    # ===== STEP 2: Search for PlayerLoop and Unity startup strings =====
    print("\n" + "=" * 80)
    print("STEP 2: Search for PlayerLoop Registration Code")
    print("=" * 80)
    
    # Search in PRX
    print("\n[2a] PRX string search:")
    prx_patterns = [
        'PlayerLoop', 'PlayerLoopInternal', 'PlayerLoopSystem',
        'RuntimeInitializeOnLoad', 'RuntimeInitialize',
        'Initialize', 'Init', 'Setup',
        'RegisterCallback', 'AddCallback', 'SetCallback',
        'EarlyUpdate', 'LateUpdate', 'FixedUpdate', 'PostLateUpdate',
        'PreUpdate', 'TimeUpdate', 'Update',
        'Bootstrap', 'bootstrap',
        'il2cpp_runtime_invoke', 'il2cpp_init', 'il2cpp_runtime_init',
        'il2cpp_codegen_initialize', 'il2cpp_codegen_register',
        'g_CodeRegistration', 'g_MetadataRegistration',
        's_Il2CppCodegenRegistration',
        'CodeRegistration', 'MetadataRegistration',
        'InvokeMethod', 'Invoke',
        'UnityEngine', 'UnityEngine',
        'Baselib', 'baselib',
        'JobQueue', 'JobSystem', 'ScheduleJob',
        'WorkerThread', 'Worker',
        'MainLoop', 'main_loop',
    ]
    
    prx_results = search_strings(prx_data, prx_patterns, "PRX")
    for pat, hits in prx_results.items():
        print(f"  '{pat}': {len(hits)} hits")
        for h in hits[:3]:
            # Find runtime address
            for seg in prx_segs:
                if seg['offset'] <= h < seg['offset'] + seg['filesz']:
                    runtime = PRX_BASE + seg['vaddr'] + (h - seg['offset'])
                    print(f"    file:0x{h:X} -> runtime:0x{runtime:X}")
                    break
    
    # Search in eboot
    print("\n[2b] Eboot string search:")
    eboot_results = search_strings(eboot_data, prx_patterns, "eboot")
    for pat, hits in eboot_results.items():
        print(f"  '{pat}': {len(hits)} hits")
        for h in hits[:3]:
            for seg in eboot_segs:
                if seg['offset'] <= h < seg['offset'] + seg['filesz']:
                    runtime = EBOOT_BASE + seg['vaddr'] + (h - seg['offset'])
                    print(f"    file:0x{h:X} -> runtime:0x{runtime:X}")
                    break
    
    # ===== STEP 3: Find il2cpp_runtime_invoke and trace managed execution =====
    print("\n" + "=" * 80)
    print("STEP 3: Trace Managed Execution Path")
    print("=" * 80)
    
    # Find il2cpp_runtime_invoke string in PRX
    str_pat = b'il2cpp_runtime_invoke\x00'
    idx = prx_data.find(str_pat)
    if idx >= 0:
        print(f"\n'il2cpp_runtime_invoke' found in PRX at file offset 0x{idx:X}")
        for seg in prx_segs:
            if seg['offset'] <= idx < seg['offset'] + seg['filesz']:
                str_runtime = PRX_BASE + seg['vaddr'] + (idx - seg['offset'])
                print(f"  Runtime address: 0x{str_runtime:X}")
                break
        
        # Search for 64-bit refs to this string address
        str_ref = struct.pack('<Q', str_runtime)
        print(f"  Searching for 64-bit refs to 0x{str_runtime:X}...")
        for seg in prx_segs:
            if seg['type'] != 1:
                continue
            seg_data = prx_data[seg['offset']:seg['offset'] + seg['filesz']]
            ref_idx = 0
            while True:
                j = seg_data.find(str_ref, ref_idx)
                if j == -1:
                    break
                ref_runtime = PRX_BASE + seg['vaddr'] + j
                seg_type = 'CODE' if seg['flags'] & 1 else 'DATA'
                print(f"    Ref at 0x{ref_runtime:X} ({seg_type})")
                ref_idx = j + 1
        
        # Also search for LEA rip-relative to this string
        print(f"  Searching for LEA rip-relative to 0x{str_runtime:X}...")
        for seg in prx_segs:
            if seg['type'] != 1 or not (seg['flags'] & 1):
                continue
            seg_data = prx_data[seg['offset']:seg['offset'] + seg['filesz']]
            for i in range(len(seg_data) - 7):
                b0 = seg_data[i]
                b1 = seg_data[i + 1] if i + 1 < len(seg_data) else 0
                if b0 in (0x48, 0x4C) and b1 == 0x8D:
                    modrm = seg_data[i + 2]
                    mod = (modrm >> 6) & 3
                    rm = modrm & 7
                    if mod == 0 and rm == 5:
                        disp = struct.unpack_from('<i', seg_data, i + 3)[0]
                        lea_addr = PRX_BASE + seg['vaddr'] + i
                        computed = lea_addr + 7 + disp
                        if computed == str_runtime:
                            print(f"    LEA at 0x{lea_addr:X} -> 0x{computed:X}")
    else:
        print("\n'il2cpp_runtime_invoke' NOT FOUND in PRX")
    
    # Also search eboot
    idx2 = eboot_data.find(str_pat)
    if idx2 >= 0:
        print(f"\n'il2cpp_runtime_invoke' found in eboot at file offset 0x{idx2:X}")
        for seg in eboot_segs:
            if seg['offset'] <= idx2 < seg['offset'] + seg['filesz']:
                str_runtime = EBOOT_BASE + seg['vaddr'] + (idx2 - seg['offset'])
                print(f"  Runtime address: 0x{str_runtime:X}")
                break
    
    # ===== STEP 4: Search for function pointer tables =====
    print("\n" + "=" * 80)
    print("STEP 4: Function Pointer Table Search")
    print("=" * 80)
    
    # Search for arrays of 8+ consecutive 64-bit values that are all code pointers
    print("\n[4a] Searching for function pointer arrays in PRX data sections...")
    for seg in prx_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):  # Skip code segments
            continue
        seg_data = prx_data[seg['offset']:seg['offset'] + seg['filesz']]
        print(f"  Segment: vaddr=0x{seg['vaddr']:X} filesz=0x{seg['filesz']:X}")
        
        # Scan for arrays of code pointers
        consecutive_count = 0
        array_start = None
        for i in range(0, len(seg_data) - 8, 8):
            val = struct.unpack_from('<Q', seg_data, i)[0]
            # Check if this is a code pointer (PRX or eboot range)
            is_code_ptr = (0x804CD5000 <= val < 0x810000000) or (0x800000000 <= val < 0x802000000)
            if is_code_ptr:
                if consecutive_count == 0:
                    array_start = i
                consecutive_count += 1
            else:
                if consecutive_count >= 8:
                    # Found an array of 8+ code pointers
                    array_runtime = PRX_BASE + seg['vaddr'] + array_start
                    print(f"    ARRAY at 0x{array_runtime:X} ({consecutive_count} entries):")
                    for j in range(min(consecutive_count, 10)):
                        v = struct.unpack_from('<Q', seg_data, array_start + j * 8)[0]
                        print(f"      [{j}] = 0x{v:X}")
                consecutive_count = 0
                array_start = None
    
    # ===== STEP 5: Compare with Unity startup model =====
    print("\n" + "=" * 80)
    print("STEP 5: Unity Startup Model Comparison")
    print("=" * 80)
    
    # The standard Unity IL2CPP startup sequence is:
    # 1. il2cpp_init() — initializes IL2CPP runtime
    # 2. il2cpp_runtime_init() — initializes runtime metadata
    # 3. Assembly loading — loads IL2CPP assemblies
    # 4. Type initialization — runs .cctor (static constructors)
    # 5. PlayerLoop.Initialize() — registers update callbacks
    # 6. Bootstrap job submission — submits first job
    # 7. Main loop — processes jobs, renders frames
    
    # On PS5, the sequence is:
    # 1. dt_init (module_start) — runs IL2CPP init
    # 2. eboot entry — runs game code
    # 3. IL2CPP type init (38000+ mutex)
    # 4. [MISSING: PlayerLoop.Initialize]
    # 5. [MISSING: Bootstrap job]
    # 6. Dispatch loop — blocks
    
    # The key question: what calls PlayerLoop.Initialize()?
    # In standard Unity, it's called by:
    # - UnityEngine.PlayerLoop.Internal:Initialize()
    # - Which is called by the native Unity runtime
    # - Which is part of the IL2CPP init sequence
    
    # On PS5, the IL2CPP runtime is in Il2cppUserAssemblies.prx
    # The dt_init function should call PlayerLoop.Initialize()
    
    # Let's check if dt_init calls any function that could be PlayerLoop.Initialize
    print("\n[5a] dt_init call chain analysis:")
    dt_init = 0x804CD5010
    dt_foff = runtime_to_file(prx_segs, dt_init, PRX_BASE)
    if dt_foff:
        chunk = prx_data[dt_foff:dt_foff + 2048]
        print(f"  dt_init at 0x{dt_init:X}, analyzing first 2048 bytes")
        calls = []
        for i in range(len(chunk) - 5):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = dt_init + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:
                    # Follow JMP thunks
                    real_target = follow_jmp(prx_data, prx_segs, target, PRX_BASE)
                    if real_target != target:
                        calls.append((call_addr, target, real_target))
                    else:
                        calls.append((call_addr, target, None))
        
        print(f"  Found {len(calls)} CALL instructions:")
        for ca, ct, rt in calls[:30]:
            if rt:
                print(f"    0x{ca:X}: call 0x{ct:X} -> 0x{rt:X}")
            else:
                print(f"    0x{ca:X}: call 0x{ct:X}")
    
    # ===== Check the gate byte in RELA table =====
    print("\n" + "=" * 80)
    print("STEP 1b: Check RELA table for gate byte")
    print("=" * 80)
    
    # The gate byte is at 0x808D67B98
    # vaddr in PRX = 0x808D67B98 - 0x804CD5000 = 0x404EB98
    # Wait, let me recalculate
    gate_byte_vaddr = byte_addr - PRX_BASE
    print(f"\nGate byte runtime: 0x{byte_addr:X}")
    print(f"Gate byte vaddr in PRX: 0x{gate_byte_vaddr:X}")
    
    # Find RELA sections in PRX
    # Parse section headers
    e_shoff = struct.unpack_from('<Q', prx_data, 0x28)[0]
    e_shentsize = struct.unpack_from('<H', prx_data, 0x3A)[0]
    e_shnum = struct.unpack_from('<H', prx_data, 0x3C)[0]
    e_shstrndx = struct.unpack_from('<H', prx_data, 0x3E)[0]
    
    if e_shoff > 0 and e_shnum > 0 and e_shoff < len(prx_data):
        # Read section header string table
        shstr_off = e_shoff + e_shstrndx * e_shentsize
        if shstr_off + e_shentsize > len(prx_data):
            print(f"  Section header string table entry out of bounds")
        else:
            shstr_offset = struct.unpack_from('<Q', prx_data, shstr_off + 0x18)[0]
            shstr_size = struct.unpack_from('<Q', prx_data, shstr_off + 0x20)[0]
        
        print(f"\nPRX has {e_shnum} sections:")
        rela_sections = []
        for i in range(e_shnum):
            sh_off = e_shoff + i * e_shentsize
            sh_name = struct.unpack_from('<I', prx_data, sh_off)[0]
            sh_type = struct.unpack_from('<I', prx_data, sh_off + 4)[0]
            sh_offset = struct.unpack_from('<Q', prx_data, sh_off + 0x18)[0]
            sh_size = struct.unpack_from('<Q', prx_data, sh_off + 0x20)[0]
            sh_entsize = struct.unpack_from('<Q', prx_data, sh_off + 0x38)[0]
            
            # Read section name
            name_end = prx_data.find(b'\x00', shstr_offset + sh_name)
            name = prx_data[shstr_offset + sh_name:name_end].decode('ascii', errors='replace')
            
            if 'rela' in name.lower() or sh_type in (4, 7, 9):  # SHT_RELA, SHT_REL, SHT_RELR
                rela_sections.append((name, sh_type, sh_offset, sh_size, sh_entsize))
                print(f"  [{i}] {name}: type={sh_type} offset=0x{sh_offset:X} size=0x{sh_size:X} entsize=0x{sh_entsize:X}")
            elif i < 20 or 'init' in name.lower() or 'text' in name.lower() or 'data' in name.lower():
                print(f"  [{i}] {name}: type={sh_type} offset=0x{sh_offset:X} size=0x{sh_size:X}")
        
        # Search RELA entries for the gate byte address
        print(f"\nSearching RELA sections for r_offset = 0x{gate_byte_vaddr:X}...")
        for name, sh_type, sh_offset, sh_size, sh_entsize in rela_sections:
            if sh_type != 4:  # SHT_RELA
                continue
            entry_count = sh_size // 24  # RELA entry = 24 bytes
            print(f"  Section {name}: {entry_count} entries")
            for j in range(entry_count):
                entry_off = sh_offset + j * 24
                if entry_off + 24 > len(prx_data):
                    break
                r_offset = struct.unpack_from('<Q', prx_data, entry_off)[0]
                r_info = struct.unpack_from('<Q', prx_data, entry_off + 8)[0]
                r_addend = struct.unpack_from('<q', prx_data, entry_off + 16)[0]
                
                # Check if this relocation targets the gate byte
                if r_offset == gate_byte_vaddr:
                    r_type = r_info & 0xFFFFFFFF
                    r_sym = r_info >> 32
                    type_names = {1: 'R_X86_64_64', 7: 'JUMP_SLOT', 8: 'RELATIVE', 9: 'GLOB_DAT'}
                    type_name = type_names.get(r_type, f'type={r_type}')
                    print(f"  *** FOUND RELA ENTRY ***")
                    print(f"    Entry #{j}: r_offset=0x{r_offset:X} r_info=0x{r_info:X} r_addend=0x{r_addend:X}")
                    print(f"    Type: {type_name}, Symbol: {r_sym}")
                    print(f"    Addend: 0x{r_addend:X} ({r_addend})")
                    if r_addend != 0:
                        print(f"    *** ADDEND IS NON-ZERO — byte should be set to {r_addend} ***")
    
    print("\n" + "=" * 80)
    print("Analysis Complete")
    print("=" * 80)

if __name__ == '__main__':
    main()
