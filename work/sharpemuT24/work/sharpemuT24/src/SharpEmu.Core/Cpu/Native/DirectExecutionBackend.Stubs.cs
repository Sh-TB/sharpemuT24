// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

// ============================================================================
// DirectExecutionBackend - Missing Method Stubs (Combined)
//
// These methods are referenced by DirectExecutionBackend.Imports.cs and other
// partial class files but were not defined in this source snapshot.
//
// All methods are stubbed with conservative behavior that will not crash
// the emulator but may cause some diagnostic paths to produce less data.
// ============================================================================

using SharpEmu.HLE;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ========================================================================
    // Missing Fields
    // ========================================================================

    /// <summary>
    /// Stub: Flag for whether HLE performance histogram is enabled.
    /// Originally a Dictionary for accumulating timings, but DirectExecutionBackend.Imports.cs
    /// uses it as a bool flag ("if (_perfHleHistogram) { ... }").
    /// </summary>
    private static readonly bool _perfHleHistogram = false;

    // ========================================================================
    // Missing Methods (all made STATIC so they can be called from both
    // static and instance contexts via DirectExecutionBackend.MethodName)
    // ========================================================================

    /// <summary>
    /// Stub: Returns true if the given address is the "unresolved sentinel".
    /// </summary>
    private static bool IsUnresolvedSentinel(ulong address)
    {
        // Conservative stub: never treat anything as the sentinel.
        return false;
    }

    /// <summary>
    /// Stub: Dumps the recent import trace to stderr.
    /// </summary>
    private static void DumpRecentImportTrace()
    {
        try
        {
            Console.Error.WriteLine("[LOADER][STUB] DumpRecentImportTrace() called");
        }
        catch { }
    }

    /// <summary>
    /// Stub: Records a recent import trace entry.
    /// Accepts the 6-argument form used by DirectExecutionBackend.Imports.cs.
    /// First parameter is `long` (sequence number) to match upstream usage.
    /// </summary>
    private static void RecordRecentImportTrace(
        long importSequence,
        string nid,
        ulong retRip,
        ulong arg1,
        ulong arg2,
        ulong arg3)
    {
        // No-op stub.
    }

    /// <summary>
    /// Stub: Records HLE performance metrics.
    /// Accepts a single nid argument (the upstream form, no timing).
    /// </summary>
    private static void RecordPerfHleCall(string nid)
    {
        // No-op stub.
    }

    /// <summary>
    /// Stub: Overload that accepts timing.
    /// </summary>
    private static void RecordPerfHleCall(string nid, long durationTicks)
    {
        // No-op stub.
    }

    /// <summary>
    /// Stub: Reads a 64-bit value from the guest stack.
    /// </summary>
    private static bool TryReadStackU64(ulong stackAddress, out ulong value)
    {
        value = 0;
        return false;
    }

    /// <summary>
    /// Stub: Heuristic for determining if an address is a valid return address.
    /// </summary>
    private static bool IsLikelyReturnAddress(ulong address)
    {
        return address > 0x1000 && address != 0xFFFFFFFFFFFFFFFF;
    }

    /// <summary>
    /// Stub: Tries to get a plausible return address from the stack.
    /// </summary>
    private static bool TryGetPlausibleReturnFromStack(ulong rsp, out ulong retRip)
    {
        retRip = 0;
        return false;
    }

    /// <summary>
    /// Stub: Probes a return RIP for validity.
    /// Accepts 2 arguments (rip and an optional context/state).
    /// </summary>
    private static bool ProbeReturnRip(ulong rip, object? context = null)
    {
        return rip > 0x1000;
    }

    // ========================================================================
    // Additional stubs for methods used by DirectExecutionBackend.Exceptions.cs
    // and DirectExecutionBackend.Imports.cs
    // ========================================================================

    /// <summary>
    /// Stub: Records HLE dispatch timing (used by perf-histogram path).
    /// </summary>
    private static void RecordPerfHleDispatchTime(long elapsedTicks)
    {
        // No-op stub.
    }

    /// <summary>
    /// Stub: Tries to get a plausible return address from the stack.
    /// Accepts the 3-argument form: (rsp, out retRip, out nextRsp).
    /// </summary>
    private static bool TryGetPlausibleReturnFromStack(ulong rsp, out ulong retRip, out ulong nextRsp)
    {
        retRip = 0;
        nextRsp = rsp + 8;  // Conservative: assume standard 8-byte stack slot.
        return false;
    }

    /// <summary>
    /// Stub: Returns true if memory protection allows reads.
    /// </summary>
    private static bool IsReadableProtection(uint protection)
    {
        // Conservative stub: assume readable.
        return true;
    }

    /// <summary>
    /// Stub: Returns true if memory protection allows execution.
    /// </summary>
    private static bool IsExecutableProtection(uint protection)
    {
        // Conservative stub: assume executable.
        return true;
    }

    /// <summary>
    /// Stub: Scans memory for suspicious resolver pointers (crash debugging).
    /// Accepts ulong size for compatibility with callers that pass ulong.
    /// Returns a List<ulong> of suspicious pointers found.
    /// </summary>
    private static List<ulong> ScanSuspiciousResolverPointers(ulong address, ulong size)
    {
        // Stub: return empty list — no suspicious pointers found.
        return new List<ulong>();
    }

    /// <summary>
    /// Stub: Parses an optional hex address from an environment variable.
    /// </summary>
    private static ulong ParseOptionalHexAddress(string? value)
    {
        if (string.IsNullOrEmpty(value)) return 0;
        try
        {
            // Strip optional 0x prefix
            var v = value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
                ? value[2..]
                : value;
            return ulong.Parse(v, System.Globalization.NumberStyles.HexNumber);
        }
        catch
        {
            return 0;
        }
    }
}
