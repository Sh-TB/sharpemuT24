# Golden Debug Protocol — SharpEmuT24

**Version:** 1.0
**Last updated:** EXP-200 (2026-08-13)

---

## Rule 1 — Evidence First

No decision based on guess. Before any fix:

```
Observation → Evidence → Hypothesis → Experiment → Validation
```

Every important claim must have:
- Static evidence (disassembly, source code, binary analysis)
- Runtime evidence (logs, register dumps, memory snapshots)
- Or external reference evidence (Prosper, Il2CppInspector, Il2CppDumper, IL2CPP source)

Prefer multiple independent evidence sources.

## Rule 2 — Root-Cause Focus

Do not patch symptoms merely to make the emulator continue.

Every modification must have a reason supported by evidence.

## Rule 3 — Preserve Baseline

Before changing anything:
- Record git status and commit hash
- Preserve current source state
- Preserve current binary if available
- Capture a fresh baseline crash/run

Do NOT destroy the baseline.

## Rule 4 — Do Not Repeat Already-Proven Hypotheses

Treat these as established unless new evidence directly contradicts them:

```
RELA relocation processing                  PASS
R_X86_64_RELATIVE processing               PASS
DT_INIT execution                          PASS
DT_INIT callback invocation                PASS
VideoOut initialization                    PASS
Vulkan initialization                      PASS
EXP-192 __cxa_throw root-cause hypothesis  REJECTED
EXP-195 il2cpp_init stub root cause        REJECTED
EXP-194 [0x801E51240] == Il2CppClass*      REJECTED
EXP-198 cJ2Y4E-t258 HLE stub root cause    CONFIRMED AND FIXED
```

## Rule 5 — Keep Rejected Hypotheses Closed

Especially:

```
"DT_SCE_INIT_ARRAY 0x61000017/19 is the init_array"
```

was disproven by source/reference analysis (EXP-190). Prosper's `self_dump.cpp` confirms `0x61000017 = DT_SCE_EXPORT_LIB_ATTR`.

Do not reopen it unless new evidence requires it.

## Rule 6 — Use External References Before Deep Custom Reverse Engineering

Mandatory reference families:

1. **Prosper** (github.com/mattias800/prosper) — PS5 compatibility layer, runs Unity IL2CPP games
2. **Il2CppInspector** (github.com/djkaty/Il2CppInspector) — IL2CPP binary analysis
3. **Il2CppDumper** (github.com/Perfare/Il2CppDumper) — IL2CPP structure definitions
4. **IL2CPP runtime/codegen** (github.com/kp7742/IL2CPPDumper) — Reference IL2CPP source
5. **PS5 IL2CPP runtime** (github.com/LiEnby/ps5-lib-il2cpp) — PS5-specific IL2CPP sources

Do NOT blindly copy implementations. Extract the underlying mechanism and verify against the actual PS5 binary.

## Rule 7 — Instrumentation Safety

EXP-192 demonstrated that INT3 instrumentation can alter behavior.

Prefer:
1. Logging (env vars like `SHARPEMU_LOG_ALL_IMPORTS=1`)
2. Counters (`SHARPEMU_PIPELINE_COUNTERS=1`)
3. State snapshots
4. Memory snapshots
5. Call tracing
6. Non-invasive hooks

Use INT3 only when its behavioral impact has been validated.

## Rule 8 — No Speculative Patches

Do NOT:
- Force globals non-NULL
- Fabricate registration structures
- Suppress crashes
- Swallow exceptions
- Bypass initialization
- Replace unknown pointers
- Patch guest code merely to advance execution
- Add arbitrary HLE stubs

unless the investigation has already proven that behavior is required.

## Rule 9 — Fix Gate

A code change is allowed ONLY when:

```
root cause identified
+
runtime evidence confirms it
+
external references support expected behavior
+
minimal implementation location identified
```

## Rule 10 — Regression Matrix

After every successful fix, verify:

```
PRX loading
RELA
DT_INIT
all modules
il2cpp_init
VideoOut
Vulkan
previously fixed paths
new path
crash location
```

A fix is NOT accepted if it breaks an earlier PASS.

## Available Environment Variables

| Variable | Purpose |
|----------|---------|
| `SHARPEMU_GUEST_ARGS` | Set to "dummy_arg" for argc=2 (required for Yatzi) |
| `SHARPEMU_SEMA_FAST_PATH` | Set to "0" for correct semaphore behavior |
| `SHARPEMU_VIDEOOUT_FALLBACK_IMAGE` | Set to "1" for headless mode |
| `SHARPEMU_PIPELINE_COUNTERS` | Set to "1" for GPU activity counters |
| `SHARPEMU_LOG_ALL_IMPORTS` | Set to "1" for detailed import resolution logging |
| `SHARPEMU_LOG_DLSYM` | Set to "1" for dlsym call logging |
| `SHARPEMU_LOG_IL2CPP_NULL` | Set to "1" to log IL2CPP stubs returning NULL |
| `SHARPEMU_LOG_IL2CPP_STUBS` | Set to "1" to log IL2CPP stubs returning non-NULL |
| `SHARPEMU_NID_TRACE` | Comma-separated NIDs to trace |
| `SHARPEMU_LOG_POSIX_SIGNALS` | Set to "1" for POSIX signal logging |
| `SHARPEMU_LOG_GUEST_EXCEPTIONS` | Set to "1" for guest exception delivery logging |
| `SHARPEMU_IGNORE_GUEST_EXCEPTIONS` | Set to "1" to skip exception delivery (debug) |
