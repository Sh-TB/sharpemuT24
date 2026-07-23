#!/bin/bash
# Arise — First Frame Test
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build:${LD_LIBRARY_PATH:-}
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_APP0_DIR=/tmp/arise-app0
export SHARPEMU_SEMA_FAST_PATH=1
APP0="/tmp/arise-app0"
# Ensure save data
mkdir -p /home/z/my-project/work/sharpemu-build/user/savedata/268435456/arise/SaveData
touch /home/z/my-project/work/sharpemu-build/user/savedata/268435456/arise/SaveData/save.xml
touch /home/z/my-project/work/sharpemu-build/user/savedata/268435456/arise/SaveData/statistics.bin
touch /home/z/my-project/work/sharpemu-build/user/savedata/268435456/arise/SaveData/trophies.bin
touch /home/z/my-project/work/sharpemu-build/user/savedata/268435456/arise/SaveData/unlockables.bin
# Ensure game data
mkdir -p $APP0/resources/cookeddata $APP0/resources/shaders/2d $APP0/resources/texts/en.lproj
touch $APP0/resources/cookeddata/bigfile.bfdb
touch $APP0/resources/shaders/2d/basic_vs_a3cd97ea_vs.ags
touch $APP0/resources/shaders/2d/basic_fs_3488995a_ps.ags
touch $APP0/resources/texts/en.lproj/localizable.strings
touch $APP0/resources/texts/localizable.strings
timeout 90 /home/z/my-project/work/sharpemu-build/SharpEmu --log-level=info "$APP0/eboot.bin" 2>&1 | grep -E "first frame|presented|VideoOut ready"
