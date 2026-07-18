// Copyright (C) 2026 SharpEmu Emulator Project
using SharpEmu.Logging;
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;

namespace SharpEmu.Diagnostics;

// ============================================================================
// GPU COMMAND STATE RECORDER
// ============================================================================

public sealed class GpuCommandStateRecorder
{
    private long _submitCount;
    private long _drawCount;
    private long _dispatchCount;
    private int _currentFrame;
    
    private readonly ConcurrentDictionary<ulong, GpuResource> _resources = new();
    
    public long SubmitCount => Interlocked.Read(ref _submitCount);
    public long DrawCount => Interlocked.Read(ref _drawCount);
    public long DispatchCount => Interlocked.Read(ref _dispatchCount);
    public int CurrentFrame => _currentFrame;
    public int ResourceCount => _resources.Count;
    
    public void RecordSubmit(ulong commandBufferAddress, uint commandCount)
    {
        Interlocked.Increment(ref _submitCount);
    }
    
    public void RecordDraw(uint vertexCount, uint instanceCount, ulong shaderId)
    {
        Interlocked.Increment(ref _drawCount);
    }
    
    public void RecordDispatch(uint x, uint y, uint z)
    {
        Interlocked.Increment(ref _dispatchCount);
    }
    
    public void RecordFlip(int bufferIndex)
    {
        Interlocked.Increment(ref _currentFrame);
    }
    
    public void RecordResourceCreated(ulong address, string type, ulong size, string format)
    {
        _resources[address] = new GpuResource
        {
            Address = address,
            Type = type,
            Size = size,
            Format = format,
            CreatedAtMs = DiagStopwatch.GetElapsedTimeMs()
        };
    }
    
    public void RecordResourceDestroyed(ulong address)
    {
        _resources.TryRemove(address, out _);
    }
    
    public string ExportJson()
    {
        var obj = new
        {
            submit_count = SubmitCount,
            draw_count = DrawCount,
            dispatch_count = DispatchCount,
            current_frame = CurrentFrame,
            resource_count = ResourceCount,
            resources = _resources.Values.Select(r => new
            {
                address = $"0x{r.Address:X16}",
                type = r.Type,
                size = r.Size,
                format = r.Format,
                created_at_ms = r.CreatedAtMs
            }).ToArray()
        };
        return JsonSerializer.Serialize(obj, new JsonSerializerOptions { WriteIndented = true });
    }
    
    private struct GpuResource
    {
        public ulong Address;
        public string Type;
        public ulong Size;
        public string Format;
        public double CreatedAtMs;
    }
}

// ============================================================================
// MEMORY MAP DEBUGGER
// ============================================================================

public sealed class MemoryMapDebugger
{
    private readonly ConcurrentDictionary<ulong, MemoryRegion> _regions = new();
    private long _allocationCount;
    
    public int RegionCount => _regions.Count;
    public long AllocationCount => Interlocked.Read(ref _allocationCount);
    
    public void RecordAllocation(ulong address, ulong size, string allocator, ulong callerAddress)
    {
        Interlocked.Increment(ref _allocationCount);
        _regions[address] = new MemoryRegion
        {
            Start = address,
            End = address + size,
            Size = size,
            Allocator = allocator,
            CallerAddress = callerAddress,
            AllocatedAtMs = DiagStopwatch.GetElapsedTimeMs()
        };
    }
    
    public void RecordFree(ulong address)
    {
        _regions.TryRemove(address, out _);
    }
    
    public string ExportJson()
    {
        var obj = new
        {
            total_regions = RegionCount,
            total_allocations = AllocationCount,
            regions = _regions.Values.Select(r => new
            {
                start = $"0x{r.Start:X16}",
                end = $"0x{r.End:X16}",
                size = r.Size,
                allocator = r.Allocator,
                caller = $"0x{r.CallerAddress:X16}",
                allocated_at_ms = r.AllocatedAtMs
            }).ToArray()
        };
        return JsonSerializer.Serialize(obj, new JsonSerializerOptions { WriteIndented = true });
    }
    
    private struct MemoryRegion
    {
        public ulong Start;
        public ulong End;
        public ulong Size;
        public string Allocator;
        public ulong CallerAddress;
        public double AllocatedAtMs;
    }
}

// ============================================================================
// THREAD TIMELINE DEBUGGER
// ============================================================================

public sealed class ThreadTimelineDebugger
{
    private readonly ConcurrentDictionary<int, ThreadState> _threads = new();
    private long _totalTransitions;
    
    public int ThreadCount => _threads.Count;
    public long TotalTransitions => Interlocked.Read(ref _totalTransitions);
    
    public void RecordStateChange(int threadId, string newState, string? reason)
    {
        Interlocked.Increment(ref _totalTransitions);
        _threads.AddOrUpdate(
            threadId,
            id => new ThreadState
            {
                ThreadId = id,
                Name = $"Thread-{id}",
                CurrentState = newState,
                StateReason = reason ?? "",
                LastChangeMs = DiagStopwatch.GetElapsedTimeMs()
            },
            (_, existing) =>
            {
                existing.CurrentState = newState;
                existing.StateReason = reason ?? "";
                existing.LastChangeMs = DiagStopwatch.GetElapsedTimeMs();
                return existing;
            });
    }
    
    public void RecordMutexAcquire(int threadId, ulong mutexAddress) { /* TODO */ }
    public void RecordMutexRelease(int threadId, ulong mutexAddress) { /* TODO */ }
    
    public string ExportJson()
    {
        var obj = new
        {
            total_threads = ThreadCount,
            total_transitions = TotalTransitions,
            threads = _threads.Values.Select(t => new
            {
                id = t.ThreadId,
                name = t.Name,
                state = t.CurrentState,
                reason = t.StateReason,
                last_change_ms = t.LastChangeMs
            }).ToArray()
        };
        return JsonSerializer.Serialize(obj, new JsonSerializerOptions { WriteIndented = true });
    }
    
    private class ThreadState
    {
        public int ThreadId;
        public string Name = "";
        public string CurrentState = "";
        public string StateReason = "";
        public double LastChangeMs;
    }
}

// ============================================================================
// SYSCALL TRACER
// ============================================================================

public sealed class SyscallTracer
{
    private long _totalCalls;
    private long _failedCalls;
    private readonly ConcurrentDictionary<string, CallAggregate> _aggregates = new();
    
    public long TotalCalls => Interlocked.Read(ref _totalCalls);
    public long FailedCalls => Interlocked.Read(ref _failedCalls);
    public int DistinctApis => _aggregates.Count;
    
    public void RecordCall(
        string library,
        string name,
        string nid,
        long returnValue,
        long durationMicros,
        int threadId,
        ulong[]? args = null)
    {
        Interlocked.Increment(ref _totalCalls);
        if (returnValue < 0 && returnValue > -0x80000000L)
        {
            Interlocked.Increment(ref _failedCalls);
        }
        
        var key = $"{library}:{name}";
        _aggregates.AddOrUpdate(
            key,
            _ => new CallAggregate { Library = library, Name = name, Nid = nid, CallCount = 1, LastReturn = returnValue },
            (_, existing) =>
            {
                existing.CallCount++;
                existing.LastReturn = returnValue;
                return existing;
            });
    }
    
    public string ExportJson()
    {
        var top = _aggregates.Values.OrderByDescending(a => a.CallCount).Take(50);
        var obj = new
        {
            total_calls = TotalCalls,
            failed_calls = FailedCalls,
            distinct_apis = DistinctApis,
            top_calls = top.Select(a => new
            {
                api = $"{a.Library}:{a.Name}",
                nid = a.Nid,
                count = a.CallCount,
                last_return = $"0x{a.LastReturn:X16}"
            }).ToArray()
        };
        return JsonSerializer.Serialize(obj, new JsonSerializerOptions { WriteIndented = true });
    }
    
    public string ExportText()
    {
        var sb = new StringBuilder();
        sb.AppendLine("==============================================");
        sb.AppendLine("SYSCALL TRACE SUMMARY");
        sb.AppendLine("==============================================");
        sb.AppendLine($"Total Calls: {TotalCalls:N0}");
        sb.AppendLine($"Failed Calls: {FailedCalls:N0}");
        sb.AppendLine($"Distinct APIs: {DistinctApis}");
        sb.AppendLine();
        sb.AppendLine("--- TOP 20 MOST-CALLED APIs ---");
        foreach (var a in _aggregates.Values.OrderByDescending(x => x.CallCount).Take(20))
        {
            sb.AppendLine($"  {a.CallCount,12:N0}  {a.Library}:{a.Name}");
        }
        return sb.ToString();
    }
    
    private class CallAggregate
    {
        public string Library = "";
        public string Name = "";
        public string Nid = "";
        public long CallCount;
        public long LastReturn;
    }
}

// ============================================================================
// FILE I/O TRACER
// ============================================================================

public sealed class FileIoTracer
{
    private long _totalOpens;
    private long _totalReads;
    private long _totalWrites;
    private long _totalStats;
    private long _totalBytesRead;
    private long _totalBytesWritten;
    private long _missingFileCount;
    
    private readonly ConcurrentDictionary<string, int> _openedFiles = new();
    private readonly ConcurrentDictionary<string, int> _missingFiles = new();
    
    public long TotalOps => Interlocked.Read(ref _totalOpens) + Interlocked.Read(ref _totalReads) + Interlocked.Read(ref _totalWrites) + Interlocked.Read(ref _totalStats);
    public long TotalOpens => Interlocked.Read(ref _totalOpens);
    public long TotalReads => Interlocked.Read(ref _totalReads);
    public long TotalWrites => Interlocked.Read(ref _totalWrites);
    public long TotalStats => Interlocked.Read(ref _totalStats);
    public long TotalBytesRead => Interlocked.Read(ref _totalBytesRead);
    public long TotalBytesWritten => Interlocked.Read(ref _totalBytesWritten);
    public long MissingFileCount => Interlocked.Read(ref _missingFileCount);
    
    public void RecordOpen(string path, string mode, bool success)
    {
        Interlocked.Increment(ref _totalOpens);
        if (success)
        {
            _openedFiles.AddOrUpdate(path, 1, (_, c) => c + 1);
        }
        else
        {
            Interlocked.Increment(ref _missingFileCount);
            _missingFiles.AddOrUpdate(path, 1, (_, c) => c + 1);
        }
    }
    
    public void RecordRead(string path, ulong offset, ulong size, double durationMs)
    {
        Interlocked.Increment(ref _totalReads);
        Interlocked.Add(ref _totalBytesRead, (long)size);
    }
    
    public void RecordWrite(string path, ulong offset, ulong size, double durationMs)
    {
        Interlocked.Increment(ref _totalWrites);
        Interlocked.Add(ref _totalBytesWritten, (long)size);
    }
    
    public void RecordStat(string path, bool success)
    {
        Interlocked.Increment(ref _totalStats);
        if (!success)
        {
            Interlocked.Increment(ref _missingFileCount);
        }
    }
    
    public string ExportJson()
    {
        var obj = new
        {
            total_opens = TotalOpens,
            total_reads = TotalReads,
            total_writes = TotalWrites,
            total_stats = TotalStats,
            bytes_read = TotalBytesRead,
            bytes_written = TotalBytesWritten,
            missing_files_count = MissingFileCount,
            unique_files_opened = _openedFiles.Count,
            missing_files = _missingFiles.Keys.ToArray(),
            opened_files = _openedFiles.Keys.Take(50).ToArray()
        };
        return JsonSerializer.Serialize(obj, new JsonSerializerOptions { WriteIndented = true });
    }
}

// ============================================================================
// HLE QUALITY DATABASE
// ============================================================================

public sealed class HleQualityDatabase
{
    private readonly ConcurrentDictionary<string, ExportQualityEntry> _exports = new();
    
    public int TotalExports => _exports.Count;
    
    public void RecordCall(string library, string exportName, string nid, long returnValue)
    {
        var key = $"{library}:{exportName}";
        _exports.AddOrUpdate(
            key,
            _ => new ExportQualityEntry
            {
                Library = library,
                Export = exportName,
                Nid = nid,
                CallCount = 1,
                LastReturn = returnValue,
                Status = returnValue < 0 && returnValue > -0x80000000L ? ExportStatus.Error : ExportStatus.Implemented
            },
            (_, existing) =>
            {
                existing.CallCount++;
                existing.LastReturn = returnValue;
                return existing;
            });
    }
    
    public string ExportJson()
    {
        var obj = new
        {
            total_exports = TotalExports,
            exports = _exports.Values.OrderByDescending(e => e.CallCount).Select(e => new
            {
                library = e.Library,
                export = e.Export,
                nid = e.Nid,
                call_count = e.CallCount,
                last_return = $"0x{e.LastReturn:X16}",
                status = e.Status.ToString()
            }).ToArray()
        };
        return JsonSerializer.Serialize(obj, new JsonSerializerOptions { WriteIndented = true });
    }
    
    public enum ExportStatus
    {
        Implemented,
        Partial,
        Stub,
        Error
    }
    
    private class ExportQualityEntry
    {
        public string Library = "";
        public string Export = "";
        public string Nid = "";
        public long CallCount;
        public long LastReturn;
        public ExportStatus Status;
    }
}
