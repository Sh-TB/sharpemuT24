#!/bin/bash
# golden-test.sh — Automated Golden Test (Dreaming Sarah regression check)
#
# Usage: bash scripts/golden-test.sh [timeout_seconds]
# Default timeout: 90 seconds
#
# Requirements: Run bootstrap-runtime.sh first
#
# PASS criteria:
#   - Emulator starts
#   - First frame presented
#   - No crash
#
# Output: /tmp/golden-test-results/

set -uo pipefail

TIMEOUT="${1:-90}"
RESULTS_DIR="/tmp/golden-test-results"
mkdir -p "$RESULTS_DIR"
TS=$(date -u +%Y%m%d_%H%M%S)
LOG="$RESULTS_DIR/golden-test-${TS}.log"

echo "=== Golden Test: Dreaming Sarah ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Timeout: ${TIMEOUT}s"
echo ""

# Verify environment
if [ -z "$DISPLAY" ]; then
    echo "FAIL: DISPLAY not set. Run bootstrap-runtime.sh first."
    exit 1
fi
if [ ! -f "/tmp/games/dreaming-sarah/PPSA02929-app0/eboot.bin" ]; then
    echo "FAIL: Dreaming Sarah not extracted. Run bootstrap-runtime.sh first."
    exit 1
fi

EMU="/tmp/my-project/work/sharpemuT24/artifacts/bin/Release/net10.0/linux-x64/SharpEmu"
if [ ! -f "$EMU" ]; then
    echo "FAIL: SharpEmu not built. Run: dotnet build SharpEmu.slnx -c Release"
    exit 1
fi

export SHARPEMU_APP0_DIR="/tmp/games/dreaming-sarah/PPSA02929-app0"
export SHARPEMU_SEMA_FAST_PATH=1
export SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1

echo "Running Dreaming Sarah..."
timeout "$TIMEOUT" "$EMU" --log-level=info \
    /tmp/games/dreaming-sarah/PPSA02929-app0/eboot.bin \
    > "$LOG" 2>&1
EXIT_CODE=$?

echo ""
echo "--- Results ---"

# Check for first frame
if grep -q "presented first frame" "$LOG"; then
    echo "PASS: First frame presented"
    grep "presented first frame" "$LOG" | head -1
else
    echo "FAIL: No first frame"
fi

# Check for crash
if grep -q "SIGSEGV\|SIGABRT\|Segmentation fault" "$LOG"; then
    echo "FAIL: Crash detected"
    grep -i "SIGSEGV\|SIGABRT\|Segmentation" "$LOG" | head -3
else
    echo "PASS: No crash"
fi

# Check for VideoOut
if grep -q "VideoOut ready" "$LOG"; then
    echo "PASS: VideoOut initialized"
else
    echo "FAIL: VideoOut not initialized"
fi

echo ""
echo "Log: $LOG"
echo "Exit code: $EXIT_CODE"

# Verdict
if grep -q "presented first frame" "$LOG" && ! grep -q "SIGSEGV\|SIGABRT\|Segmentation" "$LOG"; then
    echo ""
    echo "=== Golden Test: PASS ==="
    exit 0
else
    echo ""
    echo "=== Golden Test: FAIL ==="
    exit 1
fi
