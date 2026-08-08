// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;

namespace SharpEmu.HLE;

/// <summary>
/// Lightweight semaphore lifecycle tracker for IL2CPP bootstrap investigation.
/// Tracks create/wait/signal/delete events for all semaphores.
/// Enabled via SHARPEMU_SEMA_LIFECYCLE=1 environment variable.
/// </summary>
public static class SemaphoreLifecycleTracker
{
    private static readonly bool s_enabled =
        Environment.GetEnvironmentVariable("SHARPEMU_SEMA_LIFECYCLE") == "1";

    private readonly struct SemaEvent
    {
        public readonly long Timestamp;
        public readonly string EventType; // create, wait, signal, delete
        public readonly ulong ThreadHandle;
        public readonly string? ThreadName;

        public SemaEvent(string eventType, ulong threadHandle, string? threadName)
        {
            Timestamp = Environment.TickCount64;
            EventType = eventType;
            ThreadHandle = threadHandle;
            ThreadName = threadName;
        }
    }

    private sealed class SemaState
    {
        public uint Handle;
        public string Name = "";
        public ulong CreatorThread;
        public string? CreatorName;
        public int InitialCount;
        public int MaxCount;
        public int CurrentWaiters;
        public int SignalCount;
        public int WaitCount;
        public readonly List<SemaEvent> Events = new();
    }

    private static readonly ConcurrentDictionary<uint, SemaState> s_semaphores = new();

    public static void OnCreate(uint handle, string name, int initialCount, int maxCount,
        ulong threadHandle, string? threadName)
    {
        if (!s_enabled) return;
        var state = new SemaState
        {
            Handle = handle,
            Name = name,
            CreatorThread = threadHandle,
            CreatorName = threadName,
            InitialCount = initialCount,
            MaxCount = maxCount
        };
        state.Events.Add(new SemaEvent("create", threadHandle, threadName));
        s_semaphores[handle] = state;
        Console.Error.WriteLine(
            $"[SEMA-LIFE] create handle=0x{handle:X8} name='{name}' init={initialCount} max={maxCount} " +
            $"thread=0x{threadHandle:X16} ({threadName ?? "?"})");
    }

    public static void OnWait(uint handle, int needCount, ulong threadHandle, string? threadName, bool blocked)
    {
        if (!s_enabled) return;
        if (s_semaphores.TryGetValue(handle, out var state))
        {
            state.WaitCount++;
            if (blocked) state.CurrentWaiters++;
            state.Events.Add(new SemaEvent("wait", threadHandle, threadName));
            if (state.Events.Count <= 20)
            {
                Console.Error.WriteLine(
                    $"[SEMA-LIFE] wait handle=0x{handle:X8} need={needCount} waiters={state.CurrentWaiters} " +
                    $"thread=0x{threadHandle:X16} ({threadName ?? "?"})");
            }
        }
    }

    public static void OnWake(uint handle, ulong threadHandle, string? threadName)
    {
        if (!s_enabled) return;
        if (s_semaphores.TryGetValue(handle, out var state))
        {
            if (state.CurrentWaiters > 0) state.CurrentWaiters--;
            state.Events.Add(new SemaEvent("wake", threadHandle, threadName));
            Console.Error.WriteLine(
                $"[SEMA-LIFE] wake handle=0x{handle:X8} waiters={state.CurrentWaiters} " +
                $"thread=0x{threadHandle:X16} ({threadName ?? "?"})");
        }
    }

    public static void OnSignal(uint handle, int signalCount, ulong threadHandle, string? threadName)
    {
        if (!s_enabled) return;
        if (s_semaphores.TryGetValue(handle, out var state))
        {
            state.SignalCount++;
            state.Events.Add(new SemaEvent("signal", threadHandle, threadName));
            Console.Error.WriteLine(
                $"[SEMA-LIFE] signal handle=0x{handle:X8} count={signalCount} signals={state.SignalCount} " +
                $"thread=0x{threadHandle:X16} ({threadName ?? "?"})");
        }
    }

    public static void OnDelete(uint handle, ulong threadHandle, string? threadName)
    {
        if (!s_enabled) return;
        if (s_semaphores.TryGetValue(handle, out var state))
        {
            state.Events.Add(new SemaEvent("delete", threadHandle, threadName));
            Console.Error.WriteLine(
                $"[SEMA-LIFE] delete handle=0x{handle:X8} name='{state.Name}' " +
                $"thread=0x{threadHandle:X16} ({threadName ?? "?"})");
        }
    }

    public static void DumpReport()
    {
        if (!s_enabled) return;

        Console.Error.WriteLine();
        Console.Error.WriteLine("========== Semaphore Lifecycle Report ==========");
        Console.Error.WriteLine($"Total semaphores: {s_semaphores.Count}");
        var deadlocked = s_semaphores.Values
            .Where(s => s.CurrentWaiters > 0 && s.SignalCount == 0)
            .ToList();
        Console.Error.WriteLine($"Deadlocked (waiters > 0, signals = 0): {deadlocked.Count}");
        Console.Error.WriteLine();

        foreach (var state in s_semaphores.Values.OrderBy(s => s.Handle))
        {
            var status = state.SignalCount == 0 && state.CurrentWaiters > 0 ? "❌ DEADLOCKED" : "✅ ok";
            Console.Error.WriteLine(
                $"  Sema 0x{state.Handle:X8} '{state.Name}' {status}");
            Console.Error.WriteLine(
                $"    Creator: 0x{state.CreatorThread:X16} ({state.CreatorName ?? "?"})");
            Console.Error.WriteLine(
                $"    Init={state.InitialCount} Max={state.MaxCount} " +
                $"Waits={state.WaitCount} Signals={state.SignalCount} " +
                $"CurrentWaiters={state.CurrentWaiters}");

            if (state.SignalCount == 0 && state.CurrentWaiters > 0)
            {
                Console.Error.WriteLine("    Events:");
                foreach (var ev in state.Events.Take(10))
                {
                    Console.Error.WriteLine(
                        $"      +{ev.Timestamp}ms {ev.EventType} " +
                        $"thread=0x{ev.ThreadHandle:X16} ({ev.ThreadName ?? "?"})");
                }
                if (state.Events.Count > 10)
                    Console.Error.WriteLine($"      ... ({state.Events.Count} total events)");
            }
            Console.Error.WriteLine();
        }
        Console.Error.WriteLine("================================================");
    }
}
