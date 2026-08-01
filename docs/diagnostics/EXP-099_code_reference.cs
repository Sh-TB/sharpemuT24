// EXP-099: Once-init primitive tracer.
// Purpose: Verify whether 0x804FC33B0 (once-init primitive called by registration
// helper 0x804F889D0) succeeds or fails. If it fails, callback registration is skipped.
//
// Hypothesis: 0x804FC33B0 returns failure (non-zero), causing registration to be skipped.
// If eax==0 at return: hypothesis REJECTED — registration succeeds, issue is downstream.
// If eax!=0 at return: hypothesis CONFIRMED — registration fails.
//
// Also traces the working path's once-init (0x804FC3750 at 0x804FBF799) for comparison.
//
// Addresses monitored:
//   Dead path: call at 0x804F88A00, return at 0x804F88A05
//   Working path: call at 0x804FBF799, return at 0x804FBF79E
//
// EXP-099 introduced this tracer.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // (Full implementation in the file already created — this is the documented version)
}
