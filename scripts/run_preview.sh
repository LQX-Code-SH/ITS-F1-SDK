#!/bin/bash
# F1 实时预览启动脚本 (需 root 或已配置 udev 规则)
cd "$(dirname "$0")/.." || exit 1
if [ "$EUID" -ne 0 ]; then
    exec sudo -E env PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}" \
        DISPLAY="${DISPLAY:-:0}" python3 -m f1_thermal.preview "${1:-iron_bow}"
else
    exec env PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}" python3 -m f1_thermal.preview "${1:-iron_bow}"
fi
