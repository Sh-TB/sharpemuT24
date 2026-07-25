# Checkpoint v0.0.12 — Yatzi Multi-Buffer Draw Pipeline

**Reference commit:** `4cc320f` — fix: strip kernel handle bit (0x80000000) in semaphore APIs
**Checkpoint date:** 2026-07-25
**Checkpoint author:** sharpemu bringup agent

---

## Commits Captured by this Checkpoint

| Hash | Subject | Files | +/- |
|------|---------|-------|-----|
| `4cc320f` | fix: strip kernel handle bit (0x80000000) in semaphore APIs | KernelSemaphoreCompatExports.cs | +13 / -2 |
| `58464ca` | fix: queue-level state persistence for KRz-touched draw buffers | AgcExports.cs | +178 / -1 |

**No code was deleted or reset.** Every experimental change staged between `4cc320f` and now is captured in `58464ca` and described below. The only uncommitted change at checkpoint time is this documentation file plus the `worklog.md` entry EXP-018.

---

## 1. Semaphore Resolve Handle (commit `4cc320f`)

### 1.1 Root cause

PS5 user-space applications (specifically Unity / Baselib) treat semaphore kernel
handles as opaque 32-bit values where **bit 31 (0x80000000) is set** as a
kernel-handle flag — for example a handle returned from `sceKernelCreateSema`
might be advertised as `0x80000010F` even though the underlying numeric slot in
the kernel table is `0x10F`.

SharpEmu's `KernelSemaphoreCompatExports._semaphores` dictionary is keyed by the
**un-flagged** handle value. Every Unity call to `sceKernelWaitSema` /
`sceKernelPollSema` / `sceKernelSignalSema` / `sceKernelCancelSema` /
`sceKernelDeleteSema` therefore failed with `ORBIS_GEN2_ERROR_NOT_FOUND`, which
manifested as a complete stall of the GfxDeviceWorker thread: Unity believed the
semaphore never existed, so it could never be signaled, so its worker thread
spun forever inside `WaitSema`.

### 1.2 Files changed

```
src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs
```

### 1.3 Functions changed

| Function | Change |
|----------|--------|
| `ResolveSemaphoreHandle(uint handle) => handle & 0x7FFFFFFFu` | NEW private helper, strips bit 31. |
| `KernelWaitSema(CpuContext ctx)` | Apply `ResolveSemaphoreHandle` to `ctx[Rdi]` before dictionary lookup. |
| `KernelPollSema(ctx, uint handle, int needCount)` | Apply `ResolveSemaphoreHandle` to `handle` parameter before dictionary lookup. |
| `KernelSignalSema(ctx, uint handle, int signalCount)` | Same. |
| `KernelCancelSema(ctx, uint handle, int setCount, ulong waitingThreadsAddress)` | Same. |
| `KernelDeleteSema(CpuContext ctx)` | Apply `ResolveSemaphoreHandle` to `ctx[Rdi]` before `TryRemove`. |

All five PS5 semaphore APIs are covered. The helper is private and centralised,
so future additions only need to call `ResolveSemaphoreHandle` on the incoming
handle.

### 1.4 Tests that proved no regression

| Test | Result | Evidence |
|------|--------|----------|
| Golden Test (Dreaming Sarah) | ✅ PASS | 136 frames, 256 distinct colors — within tolerance of the pre-fix baseline (commit message reports the same numbers). |
| Yatzi boot | ✅ No regression | Game continues past the previous stall point. Semaphore `0x10F` now receives exactly 1 signal (was 0 before the fix). |

The semaphore fix alone was **correct but insufficient** — it unblocked the
semaphore path but `render_work_enter` was still 0 because the draw DCB itself
was orphaned (see section 3). The semaphore fix is a hard prerequisite for the
KRz auto-chain fix to function: without it, the GfxDeviceWorker thread cannot
be released from its initialisation stall.

---

## 2. KRz Buffer Tracking (commit `58464ca`)

### 2.1 Why KRz was needed

`sceAgcDriverUnknown_KRzWekV120` (NID `-KRzWekV120`) is a libSceAgc driver
export that is **present in Yatzi's eboot.bin but absent from Dreaming Sarah's
eboot.bin**. Empirical trace from four Yatzi runs:

| Call # | rdi (buffer) | r8 | r9 | Context |
|--------|--------------|----|----|---------|
| 1 | `0x6011684A8` (setup buffer) | 0 | `0x801B5B3DC` | Before `SubmitDcb` |
| 2 | `0x60116F208` (draw buffer) | `0x6010EF2C0` | thread | After `SubmitDcb`, before Shader writes |
| 3 | `0x60116F208` (draw buffer) | 0 | `0x6011775F0` | After `cb_release_mem` |
| 4 | `0x60116F208` (draw buffer) | 7 | 7 | After PrimState, before Draw |

The pattern is consistent with Unity's GfxDevicePS5 multi-buffer rendering:
- Unity keeps a **setup buffer** (`0x6011684A8`) containing EVENT_WRITE + flip +
  register setup, and a **draw buffer** (`0x60116F208`) containing shader state +
  the actual DrawIndexAuto command.
- KRz is called on each buffer at "finalize" moments — likely the real-PS5
  driver marks the buffer ready for ordered submission and possibly tags it
  with a synchronisation point.
- SharpEmu's stub returned `ORBIS_GEN2_OK` without doing anything, so the draw
  buffer was never enqueued. The DrawIndexAuto command was written to memory
  but never parsed.

### 2.2 Buffers tracked

Three static fields were added to `AgcExports`:

```csharp
private static readonly List<ulong> _krzTouchedBuffers = new();
private static readonly HashSet<ulong> _krzProcessedBuffers = new();
private static readonly Dictionary<ulong, ulong> _krzBufferCommandBase = new();
```

| Field | Purpose |
|-------|---------|
| `_krzTouchedBuffers` | Append-only list of buffer addresses that KRz has been called on. Order is preserved. |
| `_krzProcessedBuffers` | Set of buffers that have already been auto-chained into the queue. Prevents re-submission. |
| `_krzBufferCommandBase` | Per-buffer: the value of `cursorUp` (at `buffer + 0x10`) at the moment KRz was first called. Used later as the start address for parsing. |

Observed during Yatzi runs (3 reproducibility runs, identical):

| Buffer | Role | Tracked? |
|--------|------|----------|
| `0x6011684A8` | Setup buffer (DCB-embedded flip + register setup) | ✅ |
| `0x60116F208` | Draw buffer (shaders + prim state + DrawIndexAuto) | ✅ |

### 2.3 Full buffer lifecycle (create → submit)

```
T0: Unity allocates a command buffer at addr B and sets cursorUp = base.
T1: Unity calls sceAgcDriverUnknown_KRzWekV120(B, ...).
    → SharpEmu KRz stub:
      • If B not in _krzTouchedBuffers, append B.
      • Read cursorUp at B + 0x10, store as _krzBufferCommandBase[B].
      • Log: agc.krz_buffer_registered buf=B total_pending=N
      • Return ORBIS_GEN2_OK (no behaviour change for the guest).
T2: Unity writes setup packets to B (SET_REG, EVENT_WRITE, flip).
T3: Unity calls sceAgcDriverSubmitDcb(B, dwordCount).
    → EnqueueSubmittedDcb on gpuState.Graphics.
    → ParseSubmittedDcbCore walks the buffer, applies Cx/Sh/Uc registers,
      fires the embedded dcb_set_flip, completes.
    → After PumpSubmittedQueue returns, ProcessPendingKrzBuffers is called:
      • For each buffer in _krzTouchedBuffers not in _krzProcessedBuffers,
        read current cursorUp, compute dwordCount = (cursorUp - commandBase)/4.
      • If dwordCount > 0 and ≤ 0x10000, EnqueueSubmittedDcb on the SAME
        gpuState.Graphics (persistent queue state) and parse.
      • Mark buffer as _krzProcessedBuffers.
      • Log: agc.krz_auto_chain buf=B cmd=commandBase dwords=N
T4: Unity writes shader + draw state to B' (the draw buffer) and calls
    DcbDrawIndexAuto(B', indexCount) which writes DrawIndexAuto into B'.
T5: After DcbDrawIndexAuto returns, ProcessPendingKrzBuffers is called again.
    B' is now in _krzTouchedBuffers but not _krzProcessedBuffers, so it is
    auto-chained. DrawIndexAuto is parsed via the persistent queue state.
T6: TryTranslateGuestDraw sees the shaders / RT / prim state set by T3 and
    translates the draw into a VulkanOffscreenGuestDraw.
T7: GuestGpu.Current submits the offscreen draw to the Vulkan presenter queue.
T8: vk.render_work_enter fires for the offscreen draw.
```

The "after `SubmitDcb`" and "after `DcbDrawIndexAuto`" hook points cover both
ordering variants observed in Yatzi (setup buffer submitted first, draw buffer
finalised later) and would also handle the inverse ordering if Unity ever
chose it.

---

## 3. SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS

### 3.1 Implementation architecture

The fix is **NOT physical buffer merge**. Each KRz-touched buffer is processed
as its own independent submission through `EnqueueSubmittedDcb`, exactly as a
real `SubmitDcb` call would. The crucial design choice is that **all
submissions share the same persistent queue state object** (`gpuState.Graphics`),
which is exactly the architecture-correct approach the user requested.

Concretely, in `ProcessPendingKrzBuffers`:

```csharp
lock (gpuState.Gate)
{
    EnqueueSubmittedDcb(
        ctx,
        gpuState,
        gpuState.Graphics,            // ← persistent queue state, same as SubmitDcb
        commandStart,
        dwordCount,
        ++gpuState.SubmissionSequence,
        tracePackets);
    DrainResumableDcbs(ctx, gpuState, tracePackets);
}
```

Compare to `sceAgcDriverSubmitDcb` itself, which does the same call with the
same `gpuState.Graphics` argument. There is no copy, no concatenation, no
splicing of one buffer into another. Each buffer is parsed by
`ParseSubmittedDcbCore` independently.

### 3.2 Feature flag

```csharp
private static readonly bool _autoChainKrzBuffers = string.Equals(
    Environment.GetEnvironmentVariable("SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS"),
    "1",
    StringComparison.Ordinal);
```

The flag is **OFF by default**. This is intentional:

- Dreaming Sarah (Golden Test) does not call KRz at all, so enabling the flag is
  a no-op for it — but we keep it off by default to minimise blast radius.
- Yatzi enables it via `export SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS=1` in the
  run script.
- Promoting the flag to default-on is deferred until the present-path mismatch
  (section 6) is resolved, so we do not ship a half-fix as the new baseline.

### 3.3 Auto-chain logic

The pump function `ProcessPendingKrzBuffers` is called from two hook points:

1. **End of `sceAgcDriverSubmitDcb`** — covers the case where KRz was called
   on a buffer *before* the matching SubmitDcb (Yatzi's setup buffer case).
2. **End of `sceAgcDcbDrawIndexAuto`** — covers the case where Unity finalises
   a draw buffer by writing the DrawIndexAuto command (Yatzi's draw buffer
   case). At this moment the buffer is complete and ready for submission.

A third hook `TryAutoChainKrzBuffers(CpuContext ctx)` is exposed as a public
entry point so the `WaitSema` pump path can flush any draw commands that
Unity wrote to separate command buffers after `SubmitDcb`. It is currently
wired only when `_autoChainKrzBuffers` is true.

For each pending buffer, the logic is:

```
1. Read cursorUp at buffer + 0x10.                (current write position)
2. Look up commandBase in _krzBufferCommandBase.   (saved at KRz time)
3. dwordCount = (cursorUp - commandBase) / 4.
4. Skip if dwordCount == 0.                       (nothing to do)
5. Skip if dwordCount > 0x10000.                  (sanity guard, 64K dwords)
6. EnqueueSubmittedDcb on gpuState.Graphics with commandBase + dwordCount.
7. DrainResumableDcbs to parse immediately.
8. Add buffer to _krzProcessedBuffers (in finally block — always runs).
```

### 3.4 Infinite loop prevention

Three independent guards prevent re-submission feedback:

1. **`_krzProcessedBuffers` set.** Once a buffer is processed (or skipped due
   to bad count / read failure), its address is added to this set in the
   `finally` block of the per-buffer `try`/`catch`. Subsequent calls to
   `ProcessPendingKrzBuffers` filter via `Where(b => !_krzProcessedBuffers.Contains(b))`.

2. **The `Where` filter on the toProcess list.** Even if the lock is dropped
   between filter and processing, the set membership check is monotonic — once
   added, never removed — so re-entry cannot re-process the same buffer.

3. **`dwordCount` sanity check.** `dwordCount == 0` skips the buffer (and
   marks it processed). `dwordCount > 0x10000` skips the buffer (and marks it
   processed). This means a buffer with a corrupt or stale cursorUp value
   cannot trigger repeated EnqueueSubmittedDcb attempts.

The hook points themselves are also non-recursive: `ProcessPendingKrzBuffers`
is only called from `SubmitDcb`, `DcbDrawIndexAuto`, and the optional `WaitSema`
pump. None of those call back into `ProcessPendingKrzBuffers` directly.

A potential concern: KRz could be called on the *same* buffer multiple times
(Yatzi calls KRz on the draw buffer 3 times). The first call records the
buffer in `_krzTouchedBuffers` and saves `_krzBufferCommandBase[B]`. Subsequent
KRz calls on B re-enter the lock, find B already in the list, and **skip** the
registration block (`if (!_krzTouchedBuffers.Contains(bufferAddress))`). The
saved commandBase is preserved, so the eventual `dwordCount` calculation uses
the earliest cursorUp, which is the correct start-of-commands address.

### 3.5 Why physical merge was not used

Physical buffer merge — concatenating the draw buffer's dwords onto the end of
the setup buffer — was explicitly rejected for three reasons:

1. **It would hide synchronisation bugs.** The real PS5 AGC driver almost
   certainly preserves GPU context state across separate submissions on the
   same queue. If SharpEmu merge-concatenated buffers, we would never detect
   the case where Unity intended the submissions to be ordered-but-separate
   (e.g. with a WAIT_REG_MEM between them). State persistence at queue level
   is the correct mental model.

2. **It would break Dreaming Sarah.** Dreaming Sarah uses single-buffer DCBs
   where setup + draw live in the same buffer. Its 70 `DcbDrawIndexAuto` calls
   are followed by `SubmitDcb` of the same buffer. If we added merge logic to
   `SubmitDcb`, we risk double-processing the draw command. The auto-chain
   approach is a strict no-op for Dreaming Sarah because Dreaming Sarah never
   calls KRz.

3. **It would couple buffer parsing to submission order.** With merge, parsing
   would have to handle the boundary between setup packets and draw packets
   inside a single DCB window. With separate submissions, each buffer's
   parsing is self-contained and the existing `ParseSubmittedDcbCore` works
   unchanged.

The user's instruction was followed precisely: state persistence was tested
first, and merge was kept available only as a fallback flag
(`SHARPEMU_AGC_MERGE_DCB_BUFFERS`) that was **not implemented** because state
persistence proved sufficient.

---

## 4. GPU State Persistence

### 4.1 Result of examining `SubmittedGpuState.Graphics`

The persistent per-queue state object already exists:

```csharp
private sealed class SubmittedGpuState
{
    public object Gate { get; } = new();
    public SubmittedDcbState Graphics { get; } = new();   // ← single long-lived instance
    public Dictionary<uint, SubmittedDcbState> ComputeQueues { get; } = new();
    // ... resource registration, sequence counters, etc.
}

private sealed class SubmittedDcbState
{
    public Dictionary<uint, uint> CxRegisters { get; } = new();   // context regs
    public Dictionary<uint, uint> ShRegisters { get; } = new();   // shader regs
    public Dictionary<uint, uint> UcRegisters { get; } = new();   // user-config regs
    public Dictionary<ulong, RenderTargetDescriptor> KnownRenderTargets { get; } = new();
    public Dictionary<ulong, RenderTargetWriter> RenderTargetWriters { get; } = new();
    public TextureDescriptor? PresenterTexture { get; set; }
    public ulong IndexBufferAddress { get; set; }
    public uint IndexSize { get; set; }
    public uint InstanceCount { get; set; } = 1;
    // ... etc.
}
```

`SubmittedGpuState` is keyed by `ctx.Memory` (one per guest address space) via
`_submittedGpuStates`. Within a single game process there is exactly one
`SubmittedGpuState`, and its `.Graphics` field is a single `SubmittedDcbState`
instance that lives for the entire process. The dictionaries inside it
(`CxRegisters`, `ShRegisters`, `UcRegisters`, `KnownRenderTargets`,
`RenderTargetWriters`) are **never re-instantiated** — they are mutated in
place by `ApplySubmittedRegisters` and the texture / render-target decoders.

### 4.2 Why queue-level persistence is the architecture-correct approach

Real PS5 AGC (and the underlying AMD GCN architecture) treats a graphics queue
as a stateful machine. PM4 packets `SET_SH_REG`, `SET_CONTEXT_REG`,
`SET_UCONFIG_REG` write into per-queue register files that persist across
command-buffer submissions until explicitly overwritten or reset. The PS5
driver exposes this as `sceAgcDriverSubmitDcb` accepting a sequence of
independent DCBs, each of which can assume the queue's prior state is intact.

Unity's GfxDevicePS5 backend relies on this contract: it writes setup state
into one buffer, submits it, then writes draw commands into a different
buffer and submits that. The draw buffer's DrawIndexAuto packet does NOT
re-establish shader / RT / prim state — it assumes the queue still has them
bound from the previous submission.

SharpEmu's `SubmittedGpuState.Graphics` design already implements exactly
this contract. No new state object was needed.

### 4.3 Why `ResetSubmittedParserState` was not the problem

`ResetSubmittedParserState(state)` clears `CxRegisters`, `ShRegisters`,
`UcRegisters`, `RenderTargetWriters`, `IndirectArgsAddress`, etc. — i.e. all
the per-queue mutable state. The natural concern was: "is this called at
submission boundaries, wiping state between the setup DCB and the draw DCB?"

The answer is **no**. The only two call sites are:

1. **Line 3292** — inside `ParseSubmittedDcbCore`, triggered ONLY by a
   `ItNop` packet with `register == RDrawReset` or `register == RAcbReset`:
   ```csharp
   if (op == ItNop &&
       register is RDrawReset or RAcbReset &&
       length >= 2)
   {
       ResetSubmittedParserState(state);
       TraceAgc($"agc.queue_reset ...");
   }
   ```
   This is the explicit "context reset" packet that real PS5 games emit at
   the start of a new frame or render pass. Yatzi's setup DCB contains exactly
   one such packet (visible in the log: `agc.queue_reset queue=dcb.graphics
   submission=1 kind=draw`), and its draw DCB does **not** contain one.

2. **Line 4661** — inside `sceAgcDriverCreateQueue`-equivalent flow, called
   once when the queue is first constructed (initialisation).

There is **no call to `ResetSubmittedParserState` at the end of
`ParseSubmittedDcb` or `PumpSubmittedQueue`**. Submission boundaries do not
reset state. Therefore, when the auto-chained draw DCB is parsed, it sees
the Cx/Sh/Uc registers left over from the setup DCB.

Empirical proof from the Yatzi auto-chain run:

```
agc.queue_reset queue=dcb.graphics submission=1 kind=draw  ← setup DCB's reset
agc.krz_auto_chain buf=0x6011684A8 cmd=... dwords=56       ← setup buffer auto-chained
agc.krz_auto_chain buf=0x60116F208 cmd=... dwords=229      ← draw buffer auto-chained
                                                              (NO queue_reset between these)
agc.rt_writer seq=2 target=0x11390000 fmt=10 ... es=0x601540500 ps=0x601540D00 color_write=1
                                                              ← draw translated with bound shaders
```

The `es=` and `ps=` addresses on the `rt_writer` line are non-zero, proving
the export-shader and pixel-shader registers persisted from the setup DCB
into the draw DCB. `TryTranslateGuestDraw` saw them and produced a valid
`VulkanOffscreenGuestDraw`.

---

## 5. Test Results

### 5.1 Golden Test — Dreaming Sarah

The Golden Test (`tests/golden/run-golden-tests.sh`) requires ≥50 frames and
≥50 distinct colors from a 30-second Dreaming Sarah run.

| Run | Flag | Frames | Distinct Colors | Result |
|-----|------|--------|-----------------|--------|
| Baseline | `SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS` unset | 138 | 256 | ✅ PASS |
| After auto-chain | `SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS=1` | 139 | 260 | ✅ PASS |

The +1 frame and +4 colors are within run-to-run variance (Dreaming Sarah's
fog noise layer is non-deterministic). **No regression.**

Framebuffer dump from the auto-chain run: 139 files at
`/tmp/golden-framebuffers/present-NNNN-1280x720-B8G8R8A8Unorm.bgra`,
3 686 400 bytes each (1280 × 720 × 4 = 3 686 400, full BGRA).

### 5.2 Yatzi — Before vs After

| Metric | Before (`flag` unset) | After (`flag=1`) | Δ |
|--------|----------------------|------------------|---|
| `vk.render_work_enter` count | 0 | 2 | **+2** |
| `VulkanOffscreenGuestDraw` count | 0 | 1 | **+1** |
| `VulkanComputeGuestDispatch` count | 0 | 1 | +1 |
| `agc.krz_auto_chain` count | 0 | 2 | +2 |
| `agc.queue_reset` count | 1 | 1 | 0 |
| `agc.dcb_draw_index_auto` count | 1 | 1 | 0 |
| `vk.present_taken` count | 1 | 2 | +1 |
| `agc.rt_writer` events | 0 | 1 (target=`0x11390000`) | **+1** |

The "after" numbers are from 3 reproducibility runs (`yatzi-chain-run1.log`,
`run2.log`, `run3.log`), all identical.

### 5.3 Pipeline counters — Yatzi

```
AgcInit=1                    AgcCreateShader=36        AgcCreatePrimState=2
AgcDriverSubmitDcb=1         AgcDriverSubmitAcb=0      AgcDriverSubmitMultiDcbs=0
AgcDcbDrawIndexAuto=1        VideoOutOpen=1
VideoOutRegisterBuffers2=1   VideoOutSubmitFlip=1      VideoOutGetFlipStatus=2
VideoOutAddFlipEvent=2
```

Counters are identical before/after the flag (Unity's high-level API call
counts do not change — only the emulator's internal processing of those calls
changes). This confirms the flag does not perturb Unity's behaviour, only
SharpEmu's interpretation of the KRz stub.

### 5.4 Draw translation evidence

Single `rt_writer` event in the auto-chain run:

```
agc.rt_writer seq=2 target=0x0000000011390000 fmt=10 tile=27
              size=1920x1080 vertices=3 prim=0x7 indexed=False
              es=0x0000000601540500 ps=0x0000000601540D00 color_write=1
```

- `target=0x11390000` — real render target created via `render_target_new`
- `fmt=10` — R8G8B8A8Unorm (verified against the GIMG-CREATE log line)
- `es=` non-zero — export (vertex) shader bound, from setup DCB's SET_SH_REG
- `ps=` non-zero — pixel shader bound, from setup DCB's SET_SH_REG
- `prim=0x7` — triangle list (matches Yatzi's `CreatePrimState prim=0x7`)
- `vertices=3` — single triangle, matches Yatzi's `DcbDrawIndexAuto count=3`

The draw was successfully translated into a `VulkanOffscreenGuestDraw` and
queued on the graphics queue.

### 5.5 Frame / color statistics summary

| Game | Frames (30s window) | Distinct colors | Classification |
|------|---------------------|-----------------|----------------|
| Dreaming Sarah — flag unset | 138 | 256 | Real game content |
| Dreaming Sarah — flag=1 | 139 | 260 | Real game content |
| Yatzi — flag unset (60s) | 1 (splash) | — | Unity splash frame |
| Yatzi — flag=1 (60s) | 1 (splash) | — | Unity splash frame |

Yatzi's first frame is still the splash background (RGB 224,88,64, ~99.98%
coverage) — see FrameAnalyzer report from EXP-016. The auto-chain fix did not
yet produce visible Yatzi content because of the present-path mismatch
described in section 6.

---

## 6. Current Blocker — Present-Path Mismatch

### 6.1 Render-target writer target

The auto-chained draw writes to render target `0x11390000`:

```
[GIMG-CREATE] path=render_target_new addr=0x0000000011390000 size=1920x1080
              fmt=2147486208 vkfmt=R8G8B8A8Unorm mips=1
[LOADER][TRACE] agc.rt_writer seq=2 target=0x0000000011390000
              fmt=10 tile=27 size=1920x1080 vertices=3
              es=0x0000000601540500 ps=0x0000000601540D00 color_write=1
```

This render target was created by the AGC `render_target_new` path (real GPU
resource), not by the VideoOut fallback. It has the correct format and size
for a 1080p colour buffer.

### 6.2 Flip target mismatch

Yatzi's full flip lifecycle (from the auto-chain run):

```
agc.dcb_set_flip buf=0x6011684A8 cmd=0x606300CC handle=1 index=0 mode=2
                 arg=0x8000000000000000
vk.flip_fallback_created version=1 addr=0x0000000010B20000 size=1920x1080
vk.flip_capture version=1 queue=dcb.graphics submission=1 work_sequence=5
                addr=0x0000000010B20000 size=1920x1080 pitch=1920
vk.present_taken addr=0x0000000010B20000 version=1
                 drawKind=None hasPixels=False hasTranslatedDraw=False
vk.present_sample frame=1 addr=0x0000000010B20000
vk.flip_retired version=1 frame_slot=0 timeline=3
vk.flip_capture version=2 queue=dcb.graphics submission=2 work_sequence=15
                addr=0x0000000010B20000 size=1920x1080 pitch=1920
vk.present_taken addr=0x0000000010B20000 version=2
                 drawKind=None hasPixels=False hasTranslatedDraw=False
```

Two observations:

1. The flip uses `addr=0x10B20000` — the **fallback flip image** created by
   `CreateFallbackGuestImage()` (path=`fallback_flip`). It is NOT the render
   target `0x11390000` that the draw wrote to.

2. Both flips happen at submission 1 and submission 2, **both BEFORE** the
   auto-chained draw executes (the draw fires at submission 3). The draw
   completes after both flips have already retired. No third flip ever happens.

Pipeline counters confirm: `VideoOutSubmitFlip=1` for the entire 60-second
run. Unity submits exactly one explicit `sceVideoOutSubmitFlip`, plus one
embedded `dcb_set_flip` inside the setup DCB. After that, no more flip
requests arrive.

### 6.3 VideoOut path — why the RT is never displayed

The chain of evidence:

| Step | What happens | Why it's wrong |
|------|--------------|----------------|
| 1 | Unity calls `sceVideoOutRegisterBuffers2` once with the fallback image address | Should register the render target address as a presentable buffer |
| 2 | Unity writes setup state + flip into setup buffer, calls `sceAgcDriverSubmitDcb` | OK |
| 3 | Setup DCB is parsed, embedded `dcb_set_flip` fires, fallback image is flipped | The fallback image was the only registered buffer, so it gets flipped |
| 4 | Unity calls KRz on the draw buffer, writes shaders + DrawIndexAuto | OK |
| 5 | Auto-chain submits the draw buffer, draw translates to VulkanOffscreenGuestDraw | OK |
| 6 | Draw executes, writes to RT `0x11390000` | OK |
| 7 | No further `sceVideoOutSubmitFlip` is called | **Bug**: Unity is waiting for something before issuing the next flip |

The fundamental mismatch: **the render target where the draw writes is not
registered with VideoOut as a presentable buffer, and Unity does not issue
a second SubmitFlip after the draw completes.**

Three angles for the next investigation (none yet attempted):

1. **What address did `sceVideoOutRegisterBuffers2` register?** Trace its
   `rdi` / `rsi` arguments. If it registered `0x10B20000` (fallback), then
   the bug is that SharpEmu's `RegisterBuffers2` failed to register the RT
   address Unity actually passed (perhaps because the RT didn't exist yet at
   register time, so a fallback was substituted). If it registered
   `0x11390000`, then the bug is that the flip path is ignoring the registered
   address and using the fallback.

2. **Is Unity blocked on a semaphore waiting for the auto-chained draw's
   completion event?** The setup DCB's completion fired (submission 1), but
   the auto-chained draw's completion (submission 3) may not propagate
   through `NotifySubmittedDcbCompleted` because `CompletionEventNotifiedSubmissionId`
   was set to 1 and the gate `state.CompletionEventNotifiedSubmissionId == submissionId`
   may be skipping re-notification. Unity might be waiting on a graphics
   completion event that never fires.

3. **Is `dcb_set_flip` actually inside the setup DCB or in a separate buffer?**
   The log shows `agc.dcb_set_flip buf=0x6011684A8` (the setup buffer), so
   it is inside the setup DCB. But Unity may also call
   `sceVideoOutSubmitFlip` directly somewhere — investigate whether the
   `VideoOutSubmitFlip=1` call happened before or after the auto-chained
   draw, and what buffer address it passed.

---

## 7. Commit Plan for this Checkpoint

This checkpoint consists of two commits captured plus one new documentation
commit:

| Hash | Type | Subject |
|------|------|---------|
| `4cc320f` | code (already on main) | fix: strip kernel handle bit (0x80000000) in semaphore APIs |
| `58464ca` | code (already on main) | fix: queue-level state persistence for KRz-touched draw buffers |
| **(this commit)** | documentation | docs: checkpoint v0.0.12 — Yatzi multi-buffer draw pipeline |

The documentation commit adds:

- `CHECKPOINT_v0.0.12.md` (this file)
- `worklog.md` EXP-018 entry

No source files are modified by this commit. No code is deleted or reset.
The experimental `SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS=1` flag remains OFF by
default, exactly as it was after commit `58464ca`.
