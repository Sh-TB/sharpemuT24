// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Diagnostics;
using System.Threading;

namespace SharpEmu.Libs.Kernel;

/// <summary>
/// Lightweight call-counter for the GPU/VideoOut render pipeline.
/// Goal: identify which step of Unity's render pipeline is missing.
///
/// Activated by env var SHARPEMU_PIPELINE_COUNTERS=1.
/// Prints a one-line snapshot every 2 seconds showing cumulative call counts
/// for each tracked function. Does NOT change any function's behavior.
///
/// Pattern:
///   - Increment counter when function is entered
///   - Background timer dumps cumulative counts
///
/// Use this to compare Dreaming Sarah (working) vs Yatzi (broken) to find
/// exactly which GPU/VideoOut function Unity is NOT calling.
/// </summary>
public static class PipelineCallCounters
{
    public enum Function
    {
        // === AGC lifecycle ===
        AgcInit,
        AgcCreateShader,
        AgcCreatePrimState,

        // === AGC submission ===
        AgcDriverSubmitDcb,
        AgcDriverSubmitAcb,
        AgcDriverSubmitMultiDcbs,

        // === AGC draw calls ===
        AgcDcbDrawIndex,
        AgcDcbDrawIndexAuto,
        AgcDcbDrawIndexOffset,
        AgcDcbDrawIndexIndirect,
        AgcDcbDispatchIndirect,

        // === VideoOut lifecycle ===
        VideoOutOpen,
        VideoOutRegisterBuffers,
        VideoOutRegisterBuffers2,
        VideoOutSubmitFlip,
        VideoOutWaitVblank,
        VideoOutGetFlipStatus,
        VideoOutAddFlipEvent,
        VideoOutAddVblankEvent,

        // === Diagnostics ===
        GfxFlipThread_Scheduled,        // Unity's graphics flip thread scheduled
        UnityGfxDeviceWorker_Scheduled, // Unity's main render worker scheduled
    }

    private static readonly long[] _counts = new long[32]; // indexed by (int)Function
    private static readonly string[] _names = new string[32];

    private static readonly Timer _dumpTimer = new(_ => DumpCounts(), null,
        dueTime: TimeSpan.FromSeconds(2),
        period: TimeSpan.FromSeconds(2));

    private static bool _enabled =
        Environment.GetEnvironmentVariable("SHARPEMU_PIPELINE_COUNTERS") == "1";
    private static long _lastDumpTicks;

    static PipelineCallCounters()
    {
        _names[(int)Function.AgcInit] = "AgcInit";
        _names[(int)Function.AgcCreateShader] = "AgcCreateShader";
        _names[(int)Function.AgcCreatePrimState] = "AgcCreatePrimState";
        _names[(int)Function.AgcDriverSubmitDcb] = "AgcDriverSubmitDcb";
        _names[(int)Function.AgcDriverSubmitAcb] = "AgcDriverSubmitAcb";
        _names[(int)Function.AgcDriverSubmitMultiDcbs] = "AgcDriverSubmitMultiDcbs";
        _names[(int)Function.AgcDcbDrawIndex] = "AgcDcbDrawIndex";
        _names[(int)Function.AgcDcbDrawIndexAuto] = "AgcDcbDrawIndexAuto";
        _names[(int)Function.AgcDcbDrawIndexOffset] = "AgcDcbDrawIndexOffset";
        _names[(int)Function.AgcDcbDrawIndexIndirect] = "AgcDcbDrawIndexIndirect";
        _names[(int)Function.AgcDcbDispatchIndirect] = "AgcDcbDispatchIndirect";
        _names[(int)Function.VideoOutOpen] = "VideoOutOpen";
        _names[(int)Function.VideoOutRegisterBuffers] = "VideoOutRegisterBuffers";
        _names[(int)Function.VideoOutRegisterBuffers2] = "VideoOutRegisterBuffers2";
        _names[(int)Function.VideoOutSubmitFlip] = "VideoOutSubmitFlip";
        _names[(int)Function.VideoOutWaitVblank] = "VideoOutWaitVblank";
        _names[(int)Function.VideoOutGetFlipStatus] = "VideoOutGetFlipStatus";
        _names[(int)Function.VideoOutAddFlipEvent] = "VideoOutAddFlipEvent";
        _names[(int)Function.VideoOutAddVblankEvent] = "VideoOutAddVblankEvent";
        _names[(int)Function.GfxFlipThread_Scheduled] = "GfxFlipThread_Sched";
        _names[(int)Function.UnityGfxDeviceWorker_Scheduled] = "UnityGfxWorker_Sched";
    }

    public static bool Enabled => _enabled;

    [Conditional("DEBUG")]
    public static void RecheckEnabled()
    {
        // allows tests to flip env vars and re-check, but only matters in DEBUG
        _enabled = Environment.GetEnvironmentVariable("SHARPEMU_PIPELINE_COUNTERS") == "1";
    }

    /// <summary>
    /// Increment the counter for the given function. Cheap: one Interlocked.Increment.
    /// </summary>
    public static void Increment(Function fn)
    {
        if (!_enabled)
        {
            return;
        }
        Interlocked.Increment(ref _counts[(int)fn]);
    }

    /// <summary>
    /// Take a snapshot of all counters and write a single line to stderr.
    /// </summary>
    public static void DumpCounts()
    {
        if (!_enabled)
        {
            return;
        }
        var now = DateTime.UtcNow.Ticks;
        // rate-limit by 1s minimum interval (in case timer fires early)
        if (now - _lastDumpTicks < TimeSpan.TicksPerSecond)
        {
            return;
        }
        _lastDumpTicks = now;

        var sb = new System.Text.StringBuilder(256);
        sb.Append("[PIPELINE-COUNTS] ");
        bool first = true;
        for (int i = 0; i < _counts.Length; i++)
        {
            var name = _names[i];
            if (name is null) continue;
            var count = Interlocked.Read(ref _counts[i]);
            // Only print non-zero counts after the first 2 seconds; print all in the first snapshot.
            // (Helps spot which functions have NEVER been called.)
            if (!first) sb.Append(' ');
            first = false;
            sb.Append(name).Append('=').Append(count);
        }
        Console.Error.WriteLine(sb.ToString());
    }
}
