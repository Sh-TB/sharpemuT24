// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.HLE;

namespace SharpEmu.Core.Cpu;

public sealed class TrackedCpuMemory : ICpuMemory, ITrackedCpuMemory, IGuestMemoryAllocator, ICpuMemoryWrapper
{
    private readonly ICpuMemory _inner;
    
    // TASK: Wire OnMemoryAccess hook — sampled to avoid overhead in hot path.
    // (We only sample 1/256 accesses to keep overhead negligible.)
    private static long _memoryAccessCounter;

    public TrackedCpuMemory(ICpuMemory inner)
    {
        _inner = inner ?? throw new ArgumentNullException(nameof(inner));
    }

    public CpuMemoryAccessFailure? LastFailure { get; private set; }

    public ICpuMemory Inner => _inner;

    public bool TryRead(ulong virtualAddress, Span<byte> destination)
    {
        var result = _inner.TryRead(virtualAddress, destination);
        if (!result)
        {
            LastFailure = new CpuMemoryAccessFailure(virtualAddress, destination.Length, isWrite: false);
        }

        // Memory-access hook (sampled — only every 256th access goes through).
        // This is the only place where we can wire watchpoints without slowing
        // down the entire emulator.
        try
        {
            if (SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.IsActive &&
                (System.Threading.Interlocked.Increment(ref _memoryAccessCounter) & 0xFF) == 0)
            {
                SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyMemoryAccess(
                    virtualAddress,
                    (ulong)destination.Length,
                    accessType: 1,  // 1 = read
                    rip: 0);  // RIP unknown at this layer
            }
        }
        catch { /* diagnostics must never crash emulator */ }

        return result;
    }

    public bool TryWrite(ulong virtualAddress, ReadOnlySpan<byte> source)
    {
        var result = _inner.TryWrite(virtualAddress, source);
        if (!result)
        {
            LastFailure = new CpuMemoryAccessFailure(virtualAddress, source.Length, isWrite: true);
        }

        // Memory-access hook (sampled).
        try
        {
            if (SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.IsActive &&
                (System.Threading.Interlocked.Increment(ref _memoryAccessCounter) & 0xFF) == 0)
            {
                SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyMemoryAccess(
                    virtualAddress,
                    (ulong)source.Length,
                    accessType: 2,  // 2 = write
                    rip: 0);
            }
        }
        catch { /* diagnostics must never crash emulator */ }

        return result;
    }

    public bool TryAllocateGuestMemory(ulong size, ulong alignment, out ulong address)
    {
        if (_inner is IGuestMemoryAllocator allocator)
        {
            return allocator.TryAllocateGuestMemory(size, alignment, out address);
        }

        address = 0;
        return false;
    }

    public bool TryFreeGuestMemory(ulong address)
    {
        return _inner is IGuestMemoryAllocator allocator && allocator.TryFreeGuestMemory(address);
    }
}
