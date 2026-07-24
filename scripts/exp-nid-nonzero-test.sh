#!/bin/bash
# EXP-NID-NONZERO-TEST
# Cheap experiment per user's suggestion:
#  1. Baseline (return 0): observe NID call counts over 15 seconds
#  2. Non-zero return (R8 value): observe if NID call counts drop to 0
#     (which would mean the loop is broken)
# Caller mapping is enabled for both phases.
set -uo pipefail

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_APP0_DIR=/tmp/games/yatzi
export SHARPEMU_WRITABLE_APP0=1
export SHARPEMU_NID_CALLER_MAP=1
unset SHARPEMU_TRACE_GUEST_IMAGES
unset SHARPEMU_DUMP_VIDEOOUT

RUN_DIR=/tmp/exp-nid-nonzero
rm -rf "$RUN_DIR"; mkdir -p "$RUN_DIR"

run_phase () {
  local label="$1"
  local extra_env="$2"
  local log="$RUN_DIR/${label}.log"
  rm -f "$log"
  echo "=== Phase: $label (env: $extra_env) ==="
  env $extra_env timeout 18 /home/z/my-project/work/sharpemu-build/SharpEmu \
      --log-level=info /tmp/games/yatzi/eboot.bin > "$log" 2>&1 || true

  echo "--- NID-COUNTS progression (last 20): ---"
  grep "\[NID-COUNTS\]" "$log" | tail -20
  echo ""
  echo "--- Final NID-COUNTS line: ---"
  grep "\[NID-COUNTS\]" "$log" | tail -1
  echo ""
  echo "--- NID-TRACE lines (unique callers): ---"
  grep "\[NID-TRACE\]" "$log" | grep -oP 'caller=\K[^ ]+' | sort -u
  echo ""
  echo "--- Did game progress past NID loop? (search for new subsystems) ---"
  grep -iE "VideoOut.*ready|Renderer initialized|Scene loaded|Frame [0-9]+ rendered|GfxDevice.*Init" "$log" | head -5
  echo ""
  echo "--- Tail of log: ---"
  tail -10 "$log"
  echo ""
  echo "============================================"
  echo ""
}

run_phase "baseline_return0" "SHARPEMU_NID_RETURN_NONZERO="
run_phase "nonzero_returnR8" "SHARPEMU_NID_RETURN_NONZERO=1"
