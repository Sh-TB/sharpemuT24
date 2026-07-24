#!/bin/bash
# EXP-GIMG-LIFECYCLE
# Trace _guestImages creation lifecycle in both Dreaming Sarah and Yatzi.
# Goal: determine whether RegisterBuffers SHOULD create the Vulkan image, or
# whether AGC render-target creation is the legitimate path.
set -uo pipefail

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_WRITABLE_APP0=1

# Turn on guest image creation tracing AND pipeline counters
export SHARPEMU_TRACE_GUEST_IMAGE_EVENTS=1
export SHARPEMU_PIPELINE_COUNTERS=1

OUT_DIR=/tmp/exp-gimg-lifecycle
rm -rf "$OUT_DIR"; mkdir -p "$OUT_DIR"

run_game () {
  local label="$1"
  local app0="$2"
  local eboot="$3"
  local log="$OUT_DIR/${label}.log"
  rm -f "$log"
  echo "=== Running $label (15s) ==="

  SHARPEMU_APP0_DIR="$app0" \
  SHARPEMU_TRACE_GUEST_IMAGES=present \
  SHARPEMU_GUEST_IMAGE_DUMP_DIR="$OUT_DIR/${label}-frames" \
  SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1 \
  timeout 15 /home/z/my-project/work/sharpemu-build/SharpEmu \
      --log-level=info "$eboot" > "$log" 2>&1 || true

  echo "--- GIMG-CREATE events (first 15): ---"
  grep "\[GIMG-CREATE\]" "$log" | head -15
  echo ""
  echo "--- Total GIMG-CREATE events: $(grep -c '\[GIMG-CREATE\]' "$log") ---"
  echo ""
  echo "--- GIMG-CREATE by path: ---"
  grep "\[GIMG-CREATE\]" "$log" | grep -oP 'path=\K\S+' | sort | uniq -c
  echo ""
  echo "--- GIMG-CREATE unique addresses (first 10): ---"
  grep "\[GIMG-CREATE\]" "$log" | grep -oP 'addr=0x\K[0-9A-F]+' | sort -u | head -10
  echo ""
  echo "--- RegisterKnownDisplayBuffer / videoout.register_buffers events: ---"
  grep -iE "videoout\.register_buffers" "$log" | head -5
  echo ""
  echo "--- Total register_buffers events: $(grep -c 'videoout\.register_buffers' "$log") ---"
  echo ""
  echo "--- First vk.flip_capture_failed: ---"
  grep -n "flip_capture_failed" "$log" | head -1
  echo ""
  echo "--- Address in first flip_capture_failed: ---"
  grep "flip_capture_failed" "$log" | head -1 | grep -oP 'addr=0x\K[0-9A-F]+'
  echo ""
  echo "--- Final PIPELINE-COUNTS line: ---"
  grep "\[PIPELINE-COUNTS\]" "$log" | tail -1
  echo ""
  echo "--- Frames produced: $(ls "$OUT_DIR/${label}-frames" 2>/dev/null | wc -l) ---"
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
