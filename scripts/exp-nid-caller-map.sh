#!/bin/bash
# EXP-NID-CALLER-MAP
# Capture caller module+offset for the two busy-wait NIDs while
# return value is still 0 (baseline). 15 second run.
set -uo pipefail

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_APP0_DIR=/tmp/games/yatzi
export SHARPEMU_WRITABLE_APP0=1
# Caller mapping ON, non-zero return OFF (baseline)
export SHARPEMU_NID_CALLER_MAP=1
unset SHARPEMU_NID_RETURN_NONZERO
# Keep stall watchdog short — we know it stalls
export SHARPEMU_STALL_WATCHDOG_SECONDS=15
# Quiet other noisemakers
unset SHARPEMU_TRACE_GUEST_IMAGES
unset SHARPEMU_DUMP_VIDEOOUT

LOG=/tmp/exp-nid-caller-map.log
rm -f "$LOG"

timeout 25 /home/z/my-project/work/sharpemu-build/SharpEmu --log-level=info /tmp/games/yatzi/eboot.bin > "$LOG" 2>&1 || true

echo "=== Log size: $(wc -l < $LOG) lines ==="
echo ""
echo "=== NID-TRACE lines (first 30): ==="
grep "\[NID-TRACE\]" "$LOG" | head -30
echo ""
echo "=== Total NID-TRACE lines: $(grep -c '\[NID-TRACE\]' "$LOG") ==="
echo ""
echo "=== Unique caller offsets for 1D0H2KNjshE: ==="
grep "\[NID-TRACE\] 1D0H2KNjshE" "$LOG" | grep -oP 'caller=\K[^ ]+' | sort -u | head -10
echo ""
echo "=== Unique caller offsets for hsi9drzHR2k: ==="
grep "\[NID-TRACE\] hsi9drzHR2k" "$LOG" | grep -oP 'caller=\K[^ ]+' | sort -u | head -10
echo ""
echo "=== Stall watchdog fired? ==="
grep -i "stall\|watchdog" "$LOG" | head -5
echo ""
echo "=== Last 20 log lines: ==="
tail -20 "$LOG"
