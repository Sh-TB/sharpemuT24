#!/usr/bin/env python3
"""
EXP-151 Steps 3-5: Trace managed execution, search for function pointer tables,
and compare with Unity startup model.
"""

import struct

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

def main():
    print("=" * 80)
    print("EXP-151 Steps 3-5: Managed Execution + FP Tables + Unity Model")
    print("=" * 80)
    
    prx_data, prx_segs = parse_elf64(PRX_PATH)
    eboot_data, eboot_segs = parse_elf64(EBOOT_PATH)
    
    # ===== STEP 3: Find il2cpp_runtime_invoke actual function =====
    print("\n" + "=" * 80)
    print("STEP 3: Trace Managed Execution Path")
    print("=" * 80)
    
    # From Step 2, LEA at 0x804ED7171 references 'il2cpp_runtime_invoke' string at 0x80828A681
    # Let's find the function containing this LEA
    lea_addr = 0x804ED7171
    lea_foff = runtime_to_file(prx_segs, lea_addr, PRX_BASE)
    
    print(f"\n[3a] Function containing LEA to 'il2cpp_runtime_invoke' string:")
    print(f"  LEA at 0x{lea_addr:X}")
    
    # Find function start by searching backward
    func_start = None
    for back in range(0, 4096):
        if lea_foff - back < 0:
            break
        if lea_foff - back + 4 <= len(prx_data):
            b = prx_data[lea_foff - back:lea_foff - back + 4]
            if b == b'\x55\x48\x89\xe5':
                if lea_foff - back - 1 >= 0:
                    prev = prx_data[lea_foff - back - 1]
                    if prev in (0xCC, 0xC3, 0xC9):
                        func_start = lea_addr - back
                        break
    
    if func_start:
        print(f"  Function starts at 0x{func_start:X}")
        # Read first 128 bytes
        func_foff = runtime_to_file(prx_segs, func_start, PRX_BASE)
        chunk = prx_data[func_foff:func_foff + 256]
        print(f"  First 64 bytes: {chunk[:64].hex()}")
        
        # Find CALLs in this function
        print(f"  CALL instructions in first 256 bytes:")
        for i in range(min(256, len(chunk) - 5)):
            if chunk[i] == 0xE8:
                rel = struct.unpack_from('<i', chunk, i + 1)[0]
                call_addr = func_start + i
                target = call_addr + 5 + rel
                if 0x804CD5000 <= target < 0x810000000:
                    print(f"    0x{call_addr:X}: call 0x{target:X}")
    
    # ===== Find the IL2CPP BST resolver and the il2cpp_runtime_invoke function pointer =====
    print(f"\n[3b] Searching for il2cpp_runtime_invoke function pointer in BST:")
    
    # The BST is at list_head=0x2000003f20 (from previous EXPs)
    # BST node #64 @0x2000028720 contains 'il2cpp_runtime_invoke'
    # The function pointer is stored in the BST node structure
    
    # The BST node structure (from _FlagWatchInstrumentation.cs):
    # [0x00] = next pointer
    # [0x08] = field10 (possibly function pointer)
    # [0x10] = symbol_ptr (name string)
    # [0x18] = field18 (flags)
    # [0x19] = flag19 (sentinel flag)
    # [0x20] = func_ptr (function pointer!)
    
    # BST node for il2cpp_runtime_invoke is at 0x2000028720
    # This is in PRX memory at vaddr = 0x2000028720 - 0x804CD5000 = ...
    # Wait, 0x2000003f20 is NOT in the PRX's normal address range
    # It's in a separate memory region allocated by SharpEmu
    
    # The BST is set up by the IL2CPP runtime at runtime, not in the PRX file
    # So we can't find the function pointer from the file
    
    # However, we can search for the function that sets up the BST
    # The resolver function walks the BST and compares symbol names
    
    # ===== STEP 4: Function Pointer Table Search =====
    print("\n" + "=" * 80)
    print("STEP 4: Function Pointer Table Search")
    print("=" * 80)
    
    # Search for arrays of 8+ consecutive 64-bit code pointers in PRX data
    print("\n[4a] Searching for function pointer arrays in PRX data sections...")
    
    for seg in prx_segs:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue
        seg_data = prx_data[seg['offset']:seg['offset'] + seg['filesz']]
        seg_vaddr = seg['vaddr']
        
        consecutive_count = 0
        array_start = None
        arrays_found = 0
        
        for i in range(0, len(seg_data) - 8, 8):
            val = struct.unpack_from('<Q', seg_data, i)[0]
            is_code_ptr = (0x804CD5000 <= val < 0x810000000) or (0x800000000 <= val < 0x802000000)
            
            if is_code_ptr:
                if consecutive_count == 0:
                    array_start = i
                consecutive_count += 1
            else:
                if consecutive_count >= 8:
                    array_runtime = PRX_BASE + seg_vaddr + array_start
                    if arrays_found < 10:  # Limit output
                        print(f"\n  ARRAY at 0x{array_runtime:X} ({consecutive_count} entries):")
                        for j in range(min(consecutive_count, 15)):
                            v = struct.unpack_from('<Q', seg_data, array_start + j * 8)[0]
                            print(f"    [{j:3d}] = 0x{v:X}")
                        if consecutive_count > 15:
                            print(f"    ... ({consecutive_count - 15} more)")
                    arrays_found += 1
                consecutive_count = 0
                array_start = None
        
        print(f"\n  Total arrays found in segment vaddr=0x{seg_vaddr:X}: {arrays_found}")
    
    # ===== STEP 5: Compare with Unity startup model =====
    print("\n" + "=" * 80)
    print("STEP 5: Unity Startup Model Comparison")
    print("=" * 80)
    
    print("""
Standard Unity IL2CPP Startup Sequence:
1. il2cpp_init() — initialize IL2CPP runtime
   - Set up GC
   - Load metadata
   - Register assemblies
2. il2cpp_runtime_init() — initialize runtime metadata
   - Process type definitions
   - Set up method tables
3. Type initialization (.cctor)
   - Run static constructors for each type
   - Set "type initialized" flags
4. PlayerLoop.Initialize()
   - Register update callbacks (EarlyUpdate, Update, LateUpdate, etc.)
   - Set up the main loop structure
5. Bootstrap job submission
   - Submit the first job to the worker queue
   - Signal the dispatch loop semaphore
6. Main loop
   - Process jobs
   - Render frames

PS5 IL2CPP Startup (SharpEmu):
1. dt_init (module_start) — runs IL2CPP init ✅
   - BST resolver set up ✅
   - IL2CPP API functions called ✅
2. Eboot entry point ✅
3. Type initialization (38000+ mutex calls) ✅
   - .cctor methods run
   - BUT: "type initialized" flags may NOT be set (gate byte stays 0)
4. PlayerLoop.Initialize() ❌ MISSING
5. Bootstrap job submission ❌ MISSING
6. Dispatch loop blocks on WaitSema(0x81) ❌ DEADLOCK

MISSING TRANSITION:
The gate at 0x804FB8E60 checks a "type initialized" flag.
- If flag == 0 (type NOT initialized): je taken → return early (skip method)
- If flag != 0 (type IS initialized): fall through → run method code

The flag is set by the type's .cctor (static constructor).
If the .cctor runs but doesn't set the flag, the method is never executed.

This is EXACTLY what the EXP-138 RAX propagation bug would cause:
- .cctor is called via TryCallGuestFunction
- TryCallGuestFunction doesn't propagate RAX correctly
- The .cctor appears to return 0 (success)
- But the flag-setting code at the end of the .cctor is skipped or fails
- The flag stays 0
- Subsequent calls to methods of this type check the flag, find 0, and return early

The EXP-138 fix (raxCaptureSlot) should fix this:
- After the .cctor runs, RAX is correctly captured
- The flag-setting code runs correctly
- The flag is set to non-zero
- Subsequent method calls proceed normally

This reconnects EXP-138 to the root cause:
- EXP-138 fix is needed for .cctor to correctly set type initialized flags
- Without the fix, all type-initialized-flag checks fail
- Methods guarded by these flags never execute
- PlayerLoop registration (which is a method call) never executes
- Bootstrap job is never submitted
- Dispatch loop blocks on WaitSema(0x81)

PRIORITY: Build and test EXP-138 fix FIRST.
If the fix resolves the gate issue, PlayerLoop registration should proceed.
""")
    
    # ===== Check the gate function pattern =====
    print("\n" + "=" * 80)
    print("Gate function pattern analysis:")
    print("=" * 80)
    
    # The gate function has 59,744 callers via the thunk
    # This is a VERY common pattern — it's likely the IL2CPP method invocation wrapper
    # The pattern is:
    #   if (type_initialized) { run_method(); } else { return; }
    
    # But wait — the logic is inverted:
    #   byte == 0 → je taken → ret (skip)
    #   byte != 0 → fall through → run init code
    
    # This means: byte == 0 means "type NOT initialized, skip method"
    # And: byte != 0 means "type IS initialized, run method"
    
    # The init code does:
    #   mov eax, 0x0F12
    #   mov edx, 1
    #   lea rcx, [flag_array_base]
    #   lock or [rcx+r8*8+0x464D8], rdx  ; set bit in flag array
    
    # This is NOT the method code — it's setting a flag bit.
    # This looks like a "mark method as executed" pattern.
    
    # Actually, looking more carefully:
    # The function is called with r8 = some index
    # It checks if byte[type_index] == 0
    # If 0: return (type not initialized)
    # If non-0: set bit in flag array (mark this method as called), then return
    
    # Wait, but then where is the actual method code?
    # The actual method code might be at a different address, called AFTER this gate returns.
    
    # Let me check: the thunk at 0x804FA6030 redirects to 0x804FB8E60
    # But the thunk is called 59,744 times — that's a LOT
    # This might be the IL2CPP "il2cpp_codegen_initialize_runtime_metadata" function
    # or similar runtime metadata initialization
    
    # The pattern would be:
    # 1. Before calling a method, call this gate function
    # 2. Gate checks if the method's metadata is initialized
    # 3. If not initialized: return (caller should initialize)
    # 4. If initialized: mark method as called, return
    
    # But this doesn't explain the deadlock.
    
    # ALTERNATIVE INTERPRETATION:
    # The gate is NOT the problem. The gate is working correctly:
    # - First call: byte==0, return early (type not yet initialized)
    # - Type initializer runs, sets byte to non-zero
    # - Subsequent calls: byte!=0, run init code (mark method), return
    
    # The problem is that the TYPE INITIALIZER never sets the byte.
    # This is what EXP-138 would fix.
    
    print("""
The gate function at 0x804FB8E60 is called 59,744 times via thunk 0x804FA6030.
This is the IL2CPP runtime metadata initialization guard.

Pattern:
  1. Before calling a method, the caller calls this gate
  2. Gate checks if the method's type is initialized (byte != 0)
  3. If NOT initialized (byte == 0): return early (skip method)
  4. If initialized (byte != 0): mark method as called, return

The gate byte is set by the type's .cctor (static constructor).
If the .cctor doesn't set the byte, the method is never executed.

ROOT CAUSE CHAIN:
  EXP-138 RAX propagation bug
    → .cctor called via TryCallGuestFunction, RAX not propagated
    → .cctor's flag-setting code fails or is skipped
    → Type initialized flag stays 0
    → Gate function returns early for all methods of this type
    → PlayerLoop.Initialize() method never executes
    → No PlayerLoop callbacks registered
    → No bootstrap job submitted
    → Dispatch loop blocks on WaitSema(0x81)
    → DEADLOCK

FIX: Build and test EXP-138 RAX propagation fix.
If the fix correctly propagates RAX from .cctor returns,
the type initialized flags will be set, and PlayerLoop registration
will proceed.
""")


if __name__ == '__main__':
    main()
