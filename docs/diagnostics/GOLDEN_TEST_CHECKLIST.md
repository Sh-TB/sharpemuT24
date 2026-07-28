# EXP-028 — Golden Test Checklist (Dreaming Sarah Regression)

**Purpose:** Verify that every EXP-028 instrumentation patch is DIAGNOSTIC ONLY
(no functional changes, no fix, only temporary instrumentation).

**Test Subject:** Dreaming Sarah (a game known to boot correctly on SharpEmu
without any EXP-028 patches applied).

**Policy:** Every patch MUST pass this Golden Test before being used to collect
Yatzi traces. If Dreaming Sarah fails to boot, the patch has a bug.

---

## Baseline (No Patch)

Run Dreaming Sarah WITHOUT any EXP-028 patches:

```bash
cd /path/to/sharpemuT24
dotnet build SharpEmu.slnx -c Release
mkdir -p /tmp/exp028_baseline
./SharpEmu.bin /path/to/dreaming_sarah/eboot.bin 2>&1 | tee /tmp/exp028_baseline/ds_run.log
```

### Baseline Checklist

| Check | Method | PASS criteria |
|-------|--------|---------------|
| Boot starts | Log: `[INFO] SharpEmu starting` | Present |
| ELF loads | Log: `[LOADER] eboot base = 0x...` | Non-zero base |
| No crash during boot | Process still running after 30s | Yes |
| First frame renders | Log: `videoOutSubmitFlip` | At least 1 flip |
| Frame rate stable | PerfOverlay (if enabled) | > 10 FPS |
| No new errors | Compare with known-good log | No new `[ERROR]` lines |
| Audio plays (if applicable) | Log: `audioOutOutput` | Audio output calls |

**Record baseline metrics:**
- Time to first frame: _______ seconds
- Frame rate after 1 minute: _______ FPS
- Total errors in log: _______
- Total warnings in log: _______

---

## After Each EXP-028 Patch

For each patch (T12/T13, T5, T6, T1/T2/T3), apply the patch, rebuild, and re-run Dreaming Sarah:

### Step 1: Apply Patch

```bash
# Copy the patch file
cp /home/z/my-project/download/exp028/_Exp028T12T13BoundaryTrace.cs \
   src/SharpEmu.Libs/Kernel/

# Edit DirectExecutionBackend.Imports.cs per _Exp028_Patch_Instructions.md
# (apply the diff)

# Rebuild
dotnet build SharpEmu.slnx -c Release
```

### Step 2: Run Dreaming Sarah with Patch

```bash
mkdir -p /tmp/exp028_patch_T12_T13
./SharpEmu.bin /path/to/dreaming_sarah/eboot.bin 2>&1 | tee /tmp/exp028_patch_T12_T13/ds_run.log
```

### Step 3: Verify Patch Is Active

Check that the patch's log lines appear:

```bash
grep "\[EXP028-T12\]" /tmp/exp028_patch_T12_T13/ds_run.log | head -5
```

Expected: should see `[EXP028-T12-PRE]` and `[EXP028-T12-POST]` lines
(if Dreaming Sarah uses IL2CPP — if not, that's OK, just verify no crashes).

### Step 4: Regression Check

| Check | Method | PASS criteria |
|-------|--------|---------------|
| Boot starts | Log: `[INFO] SharpEmu starting` | Present |
| ELF loads | Log: `[LOADER] eboot base = 0x...` | Same base as baseline |
| No crash during boot | Process still running after 30s | Yes |
| First frame renders | Log: `videoOutSubmitFlip` | At least 1 flip |
| Time to first frame | Compare with baseline | Within ±10% of baseline |
| Frame rate after 1 min | Compare with baseline | Within ±10% of baseline |
| No new errors | `diff` baseline vs patch log | No new `[ERROR]` lines |
| No new crashes | Process exit code | 0 (clean exit) or signal-free |

### Step 5: Document Results

For each patch, fill in this table:

| Patch | Boot OK | First Frame | FPS | New Errors | Golden Test |
|-------|---------|-------------|-----|------------|-------------|
| Baseline (no patch) | ✅ | 12.3s | 45.2 | 0 | N/A |
| T12/T13 boundary trace | ___ | ___s | ___ | ___ | ✅/❌ |
| T5 memory read trace | ___ | ___s | ___ | ___ | ✅/❌ |
| T6 branch trace | ___ | ___s | ___ | ___ | ✅/❌ |
| T1/T2/T3 per-instruction | ___ | ___s | ___ | ___ | ✅/❌ |

---

## Failure Handling

If Dreaming Sarah fails to boot after applying a patch:

1. **DO NOT proceed** with collecting Yatzi traces
2. **DO NOT** apply the next patch
3. Investigate the patch for bugs:
   - Did the patch accidentally modify the resolver's behavior?
   - Did the SIGTRAP handler fail to resume execution correctly?
   - Did the breakpoint installation corrupt memory?
4. Fix the patch (it's a debug patch, fixable)
5. Re-run Golden Test
6. Only proceed once Golden Test passes

---

## Final Sign-Off

Before reporting EXP-028 results:

```
I confirm that:
  [ ] All EXP-028 patches applied are DIAGNOSTIC ONLY
  [ ] No functional changes were made to SharpEmu
  [ ] No fix was applied (yet)
  [ ] Dreaming Sarah Golden Test passes with ALL patches applied
  [ ] The instrumentation logs are present in /tmp/exp028_logs/
  [ ] The analyzer script has been run on the collected logs
  [ ] The first divergent instruction has been identified with raw evidence
```

Signed: _______________  Date: _______________
