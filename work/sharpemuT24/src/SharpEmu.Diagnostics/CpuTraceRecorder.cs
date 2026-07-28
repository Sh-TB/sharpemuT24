// Copyright (C) 2026 SharpEmu Emulator Project
using SharpEmu.Logging;
// SPDX-License-Identifier: GPL-2.0-or-later

// ============================================================================
// CPU TRACE RECORDER - Records instruction checkpoints at import dispatch.
// Uses a RingBuffer to bound memory usage.
// ============================================================================

using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using SharpEmu.Diagnostics.Contracts;

namespace SharpEmu.Diagnostics;

/// <summary>
/// Records CPU instruction checkpoints (RIP + opcode + registers) at import
/// dispatch points. Uses a ring buffer to bound memory usage.
/// </summary>
public sealed partial class CpuTraceRecorder
{
    private readonly DiagnosticProfile _profile;
    private readonly int _sampleRate;
    private long _instructionCount;
    private long _sampleCounter;
    
    // Ring buffer of last N instructions
    private readonly InstructionRecord[] _ringBuffer;
    private int _ringWriteIndex;
    private readonly object _ringLock = new();
    
    public int InstructionCount => (int)Interlocked.Read(ref _instructionCount);
    
    public CpuTraceRecorder(DiagnosticProfile profile)
    {
        _profile = profile;
        _sampleRate = profile switch
        {
            DiagnosticProfile.Normal => 100,        // 1% sampling
            DiagnosticProfile.Compatibility => 10,   // 10% sampling
            DiagnosticProfile.DeepDebug => 1,        // 100%
            DiagnosticProfile.Developer => 1,        // 100%
            DiagnosticProfile.Forensic => 1,         // 100%
            _ => 100
        };
        _ringBuffer = new InstructionRecord[1000];
    }
    
    /// <summary>
    /// Records an instruction checkpoint. Called from ICpuDiagnosticSource.RecordInstruction.
    /// </summary>
    public void RecordInstruction(
        ulong rip,
        ReadOnlySpan<byte> opcode,
        ReadOnlySpan<byte> registers,
        ulong memoryAddress,
        int memoryAccess,
        ulong memoryValue)
    {
        // Sample to reduce overhead
        var count = Interlocked.Increment(ref _sampleCounter);
        if (_sampleRate > 1 && count % _sampleRate != 0) return;
        
        Interlocked.Increment(ref _instructionCount);
        
        // Copy opcode (up to 16 bytes)
        Span<byte> opBytes = stackalloc byte[16];
        var opLen = Math.Min(opcode.Length, 16);
        opcode.Slice(0, opLen).CopyTo(opBytes);
        
        var record = new InstructionRecord
        {
            Rip = rip,
            Opcode = opBytes.ToArray(),
            MemoryAddress = memoryAddress,
            MemoryAccess = memoryAccess,
            MemoryValue = memoryValue,
            TimestampMs = DiagStopwatch.GetElapsedTimeMs()
        };
        
        // Add to ring buffer
        lock (_ringLock)
        {
            _ringBuffer[_ringWriteIndex] = record;
            _ringWriteIndex = (_ringWriteIndex + 1) % _ringBuffer.Length;
        }
    }
    
    /// <summary>
    /// Records a lightweight RIP-only checkpoint.
    /// </summary>
    public void RecordInstructionLightweight(ulong rip)
    {
        // For now, just increment the counter (full trace would be too expensive)
        Interlocked.Increment(ref _instructionCount);
    }
    
    /// <summary>
    /// Exports the trace as human-readable text.
    /// </summary>
    public string ExportText()
    {
        var sb = new StringBuilder();
        sb.AppendLine("==============================================");
        sb.AppendLine("CPU INSTRUCTION TRACE");
        sb.AppendLine("==============================================");
        sb.AppendLine($"Total Instructions Recorded: {InstructionCount:N0}");
        sb.AppendLine($"Profile: {_profile}");
        sb.AppendLine($"Sample Rate: 1/{_sampleRate}");
        sb.AppendLine();
        
        lock (_ringLock)
        {
            // Read in order (oldest first)
            var start = _ringWriteIndex;
            var count = 0;
            sb.AppendLine("Last recorded instructions (newest last):");
            for (var i = 0; i < _ringBuffer.Length; i++)
            {
                var idx = (start + i) % _ringBuffer.Length;
                var rec = _ringBuffer[idx];
                if (rec.Rip == 0) continue;
                
                count++;
                var opHex = BitConverter.ToString(rec.Opcode).Replace("-", " ");
                sb.AppendLine($"  #{count,4} RIP=0x{rec.Rip:X16} op={opHex}");
                if (rec.MemoryAddress != 0)
                {
                    var access = rec.MemoryAccess switch
                    {
                        1 => "READ",
                        2 => "WRITE",
                        4 => "EXEC",
                        _ => "?"
                    };
                    sb.AppendLine($"        mem[{access}] 0x{rec.MemoryAddress:X16} = 0x{rec.MemoryValue:X16}");
                }
                if (count >= 50) break;  // Limit output
            }
            if (count == 0)
            {
                sb.AppendLine("  (no instruction records)");
            }
        }
        
        return sb.ToString();
    }
    
    /// <summary>
    /// Exports the trace as JSON.
    /// </summary>
    public string ExportJson()
    {
        lock (_ringLock)
        {
            var records = new List<object>();
            var start = _ringWriteIndex;
            for (var i = 0; i < _ringBuffer.Length; i++)
            {
                var idx = (start + i) % _ringBuffer.Length;
                var rec = _ringBuffer[idx];
                if (rec.Rip == 0) continue;
                
                records.Add(new
                {
                    rip = $"0x{rec.Rip:X16}",
                    opcode = BitConverter.ToString(rec.Opcode).Replace("-", " "),
                    memory_address = rec.MemoryAddress != 0 ? $"0x{rec.MemoryAddress:X16}" : null,
                    memory_access = rec.MemoryAccess,
                    memory_value = rec.MemoryValue != 0 ? $"0x{rec.MemoryValue:X16}" : null,
                    timestamp_ms = rec.TimestampMs
                });
            }
            
            var obj = new
            {
                total_instructions = InstructionCount,
                profile = _profile.ToString(),
                sample_rate = _sampleRate,
                records = records
            };
            
            return JsonSerializer.Serialize(obj, new JsonSerializerOptions { WriteIndented = true });
        }
    }
    
    private struct InstructionRecord
    {
        public ulong Rip;
        public byte[] Opcode;
        public ulong MemoryAddress;
        public int MemoryAccess;
        public ulong MemoryValue;
        public double TimestampMs;
    }
}
