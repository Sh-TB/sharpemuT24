#!/bin/bash
# EXP-FALLBACK-FLIP
# Test the fallback guest image fix on Yatzi.
# Goal: verify that with SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1, Yatzi:
#   - No longer hits vk.flip_capture_failed
#   - Produces > 0 frames (black frame is OK as intermediate)
#   - Does not stall in Unity error handler
set -uo pipefail

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_APP0_DIR=/tmp/games/yatzi
export SHARPEMU_WRITABLE_APP0=1
export SHARPEMU_PIPELINE_COUNTERS=1
export SHARPEMU_TRACE_GUEST_IMAGE_EVENTS=1
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/exp-fallback-flip/frames
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1

# KEY: enable fallback
export SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1

OUT_DIR=/tmp/exp-fallback-flip
rm -rf "$OUT_DIR"; mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/yatzi.log"
rm -f "$LOG"

echo "=== Running Yatzi (20s) with fallback enabled ==="
timeout 20 /home/z/my-project/work/sharpemu-build/SharpEmu \
    --log-level=info /tmp/games/yatzi/eboot.bin > "$LOG" 2>&1 || true

echo ""
echo "--- Final PIPELINE-COUNTS line: ---"
grep "\[PIPELINE-COUNTS\]" "$LOG" | tail -1
echo ""
echo "--- vk.flip_capture_failed occurrences: ---"
grep -c "flip_capture_failed" "$LOG"
echo ""
echo "--- vk.flip_fallback_created occurrences: ---"
grep -c "flip_fallback_created" "$LOG"
echo ""
echo "--- First flip_fallback_created line: ---"
grep "flip_fallback_created" "$LOG" | head -1
echo ""
echo "--- GIMG-CREATE events (all paths): ---"
grep "\[GIMG-CREATE\]" "$LOG" | grep -oP 'path=\K\S+' | sort | uniq -c
echo ""
echo "--- Total GIMG-CREATE events: $(grep -c '\[GIMG-CREATE\]' "$LOG") ---"
echo ""
echo "--- UNMAPPED faults: $(grep -c 'UNMAPPED' "$LOG") ---"
echo ""
echo "--- Frames produced: $(ls "$OUT_DIR/frames" 2>/dev/null | wc -l) ---"
echo ""
echo "--- Distinct colors in last 5 frames (if any): ---"
for f in $(ls "$OUT_DIR/frames"/*.bgra 2>/dev/null | tail -5); do
    if [ -f "$f" ]; then
        SIZE=$(stat -c %s "$f")
        # Calculate pixel count assuming RGBA8 (4 bytes per pixel)
        PIXELS=$((SIZE / 4))
        if [ $PIXELS -gt 0 ]; then
            COLORS=$(python3 -c "
import sys
with open('$f', 'rb') as fh:
    data = fh.read()
pixels = set()
# Sample every 1000th byte to keep it fast
for i in range(0, len(data)-3, 4000):
    pixels.add((data[i], data[i+1], data[i+2], data[i+3]))
print(len(pixels))
" 2>/dev/null)
            echo "  $(basename $f): $COLORS distinct colors (sampled)"
        fi
    fi
done
echo ""
echo "--- NID loop / Unity error handler check (NID-COUNTS final): ---"
grep "\[NID-COUNTS\]" "$LOG" | tail -1
echo ""
echo "--- Magic error marker 0xC0DEC0DECAFEBA00 occurrences: ---"
grep -c "C0DEC0DECAFEBA00" "$LOG"
echo ""
echo "--- Last 10 log lines: ---"
tail -10 "$LOG"
