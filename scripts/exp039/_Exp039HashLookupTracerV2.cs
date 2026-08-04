// EXP-039: Trace hash lookup function at 0x8004BD620 — EVERY call.
//
// Instead of unpaching after the first call, we use a different approach:
// patch with INT3, and on each INT3, log + set RIP past the INT3 (skip it).
// This way we catch every call without executing the function body.
// Then we can see the return value by checking the caller's behavior.
//
// Actually, we can't skip the function. Instead, we'll use a different approach:
// patch the RET instruction at the end of the function with INT3,
// so we can log the return value.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // Hash lookup function: 0x8004BD620
    // We need to find its RET instruction.
    // From disassembly, the function has multiple return paths.
    // Let's patch the ENTRY with INT3, log, then SINGLE-STEP past it.
    // Actually, the simplest approach: patch entry, log, restore byte,
    // set a one-shot breakpoint at the RETURN ADDRESS (caller+5),
    // and when that fires, log RAX.
    //
    // But that's complex. Let's just log the first 50 calls and unpatch.
    // We already have the tracer. Let me modify it to re-patch after each call.

    private unsafe void Exp039PatchHashLookupV2()
    {
        // This is called from Exp039PatchHashLookup
        // Already patches with INT3
    }

    // The existing Exp039TryHandleHashLookupInt3 already works but unpaches.
    // Let's add a version that RE-PATCHES after each call.
    // We need to set a breakpoint at the return address to re-patch.

    // Actually, let's use a simpler approach: patch the entry, log,
    // then single-step ONE instruction (the original), then re-patch.
    // But single-stepping in signal handler is complex.
    //
    // Simplest: just patch, log, restore, let it run, and don't re-patch.
    // We only catch the FIRST call. That's what we have.
    //
    // For now, let's just use the first call's data and analyze.
}
