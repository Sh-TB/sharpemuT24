#!/bin/bash
# Dreaming Sarah — Golden Test (Regression)
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build:${LD_LIBRARY_PATH:-}
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_APP0_DIR=/home/z/my-project/upload/PPSA02929/PPSA02929-app0
export SHARPEMU_SEMA_FAST_PATH=1
APP0="/home/z/my-project/upload/PPSA02929/PPSA02929-app0"
timeout 60 /home/z/my-project/work/sharpemu-build/SharpEmu --log-level=info "$APP0/eboot.bin" 2>&1 | grep -E "first frame|presented|VideoOut ready"
