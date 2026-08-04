#!/usr/bin/env python3
"""EXP-038: Apply instrumentation patches."""
import sys
from pathlib import Path

REPO = Path("/tmp/my-project/work/sharpemuT24")
EXCEPTIONS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Exceptions.cs"
IMPORTS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs"


def patch_exceptions():
    src = EXCEPTIONS.read_text()
    original = src

    if "Exp038TryHandleCrashFuncInt3" in src:
        print("[SKIP] Exceptions already patched for EXP-038")
        return

    old = """                        // EXP-037: Handle INT3 from global pointer watchpoints.
                        if (exceptionCode == 2147483651u && Exp037TryHandleWatchpointInt3(contextRecord, rip))
                        {
                                return -1;
                        }"""

    new = """                        // EXP-038: Handle INT3 from crash function tracer.
                        if (exceptionCode == 2147483651u && Exp038TryHandleCrashFuncInt3(contextRecord, rip))
                        {
                                return -1;
                        }
                        // EXP-037: Handle INT3 from global pointer watchpoints.
                        if (exceptionCode == 2147483651u && Exp037TryHandleWatchpointInt3(contextRecord, rip))
                        {
                                return -1;
                        }"""

    if old in src:
        src = src.replace(old, new)
        print("[OK] Patched VectoredHandler (added EXP-038 crash func check)")
    else:
        print("[FAIL] Could not find EXP-037 insertion point")
        sys.exit(1)

    if src != original:
        EXCEPTIONS.write_text(src)
        print(f"[WRITE] {EXCEPTIONS}")


def patch_imports():
    src = IMPORTS.read_text()
    original = src

    if "Exp038InstallTracers" in src:
        print("[SKIP] Imports already patched for EXP-038")
        return

    old = """                                    // EXP-037: Install watchpoints for the NULL global pointer at 0x801E51240.
                                    // The crash is at 0x80135DE83: mov ecx, [rax+0x98] where rax comes from
                                    // the global at 0x801E51240. We patch the WRITE site (0x8013EF019)
                                    // with INT3 to trace when the global is initialized.
                                    Exp037InstallWatchpoints();
                                }"""

    new = """                                    // EXP-037: Install watchpoints for the NULL global pointer at 0x801E51240.
                                    Exp037InstallWatchpoints();

                                    // EXP-038: Install INT3 at crash function 0x80135DDD0 to trace caller.
                                    Exp038InstallTracers();
                                }"""

    if old in src:
        src = src.replace(old, new)
        print("[OK] Patched Imports (added Exp038InstallTracers call)")
    else:
        print("[FAIL] Could not find Exp037InstallWatchpoints call")
        sys.exit(1)

    if src != original:
        IMPORTS.write_text(src)
        print(f"[WRITE] {IMPORTS}")


if __name__ == "__main__":
    patch_exceptions()
    print()
    patch_imports()
    print()
    print("[DONE] EXP-038 patches applied")
