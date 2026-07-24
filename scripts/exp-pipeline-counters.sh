#!/bin/bash
# EXP-PIPELINE-COUNTERS
# Compare pipeline function call counts between Dreaming Sarah (working)
# and Yatzi (broken, no rendering). 20-second runs each.
set -uo pipefail

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_WRITABLE_APP0=1
export SHARPEMU_PIPELINE_COUNTERS=1

OUT_DIR=/tmp/exp-pipeline-counters
rm -rf "$OUT_DIR"; mkdir -p "$OUT_DIR"

run_game () {
  local label="$1"
  local app0="$2"
  local eboot="$3"
  local log="$OUT_DIR/${label}.log"
  rm -f "$log"
  echo "=== Running $label (20s) ==="

  SHARPEMU_APP0_DIR="$app0" \
  SHARPEMU_TRACE_GUEST_IMAGES=present \
  SHARPEMU_GUEST_IMAGE_DUMP_DIR="$OUT_DIR/${label}-frames" \
  SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1 \
  timeout 20 /home/z/my-project/work/sharpemu-build/SharpEmu \
      --log-level=info "$eboot" > "$log" 2>&1 || true

  echo "--- Final PIPELINE-COUNTS line: ---"
  grep "\[PIPELINE-COUNTS\]" "$log" | tail -1
  echo ""
  echo "--- All PIPELINE-COUNTS snapshots (compact): ---"
  grep "\[PIPELINE-COUNTS\]" "$log"
  echo ""
  echo "--- Frame count produced: ---"
  ls "$OUT_DIR/${label}-frames" 2>/dev/null | wc -l
  echo ""
  echo "--- Last 5 log lines: ---"
  tail -5 "$log"
  echo ""
  echo "============================================"
  echo ""
}

run_game "dreaming-sarah" \
  /tmp/games/dreaming-sarah/PPSA02929-app0 \
  /tmp/games/dreaming-sarah/PPSA02929-app0/eboot.bin

run_game "yatzi" \
  /tmp/games/yatzi \
  /tmp/games/yatzi/eboot.bin
