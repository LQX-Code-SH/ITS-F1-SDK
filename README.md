# INREII F1 热成像二次开发 SDK

基于官方安卓应用逆向协议实现的 Linux 端 F1 热成像仪（InfiRay 方案, USB 04b4:000a）二次开发 SDK。

> 协议逆向细节见 `docs/F1_F2_二次开发接口文档.md`（含 F2/其他型号的 UVC/BLE/WiFi 接口）。

## 功能

| 模块 | 功能 |
|---|---|
| `camera.py` | USB 视频流采集（25fps, 256×192 Y16）、帧同步、设备信息、控制命令 |
| `temperature.py` | 遥测解析（序列号/固件/发射率）、T⁴ 自校准测温、两点标定加载 |
| `palettes.py` | 9 种伪彩色板 LUT、AGC、2× 超分（占位） |
| `denoise.py` | 平场标定（NUC）、坏点掩蔽、暗场参考、多帧时域降噪 |
| `calibration.py` | 测温两点标定（交互式，生成 `calib/temp_calib.json`） |
| `preview.py` | 实时预览（伪彩 + 最高/最低温标记 + 温度条），q/p/s/n 按键 |

## 安装

```bash
pip3 install -r requirements.txt    # pyusb numpy scipy opencv-python-headless pillow
```

设备权限（二选一）：
- 临时：`sudo` 运行
- 永久：`sudo tee /etc/udev/rules.d/99-f1.rules <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="04b4", ATTRS{idProduct}=="000a", MODE="0666"
EOF
sudo udevadm control --reload && sudo udevadm trigger`

## 快速开始

```bash
# 实时预览（需先平场标定一次）
sudo -E python3 -m f1_thermal.preview

# 平场标定：运行后按提示, 前 6 秒用手掌盖住镜头
sudo -E python3 -m f1_thermal.nuc_calibrate

# 测温两点标定（可选, 提升 absolute 精度至 ±2℃）
sudo -E python3 -m f1_thermal.calibration

# 单帧采集
sudo -E python3 -m f1_thermal.camera --frames 30 --save shot.png
```

### Python API

```python
from f1_thermal import (F1Camera, TempParams, colorize, apply_agc,
                        temp_from_shutter_ref, shutter_raw_from_telemetry)

cam = F1Camera()
frames = cam.read_frames(10)
tp = TempParams(frames[0][1])           # 型号/序列号/固件/发射率
print(tp.summary())

sr = shutter_raw_from_telemetry(frames[0][1])
tC = temp_from_shutter_ref(frames[0][0], sr)   # ℃
rgb = colorize(apply_agc(tC), 'iron_bow')
cam.close()
```

## 项目结构

```
f1-thermal-sdk/
├── f1_thermal/           # Python 包
│   ├── camera.py         # USB 采集/帧同步/控制
│   ├── temperature.py    # 测温与遥测解析
│   ├── palettes.py       # 色板/AGC/超分
│   ├── denoise.py        # NUC 去噪
│   ├── calibration.py    # 测温两点标定 (CLI)
│   ├── nuc_calibrate.py  # 平场标定 (CLI)
│   └── preview.py        # 实时预览
├── calib/                # 标定数据 (flat_*.npy / temp_calib.json)
├── docs/                 # 协议逆向文档
├── scripts/run_preview.sh
└── requirements.txt
```

## 已知限制

- F1 固件不响应 EP0 类控制请求（逆向证实），快门/调色板等全部主机端实现
- 超分为插值占位实现；官方为 TNN GAN 模型，可转 ONNX 替换 `palettes.super_resolve`
- 测温出厂精度 ±3~5℃，两点标定后 ±2℃（SOP 见文档附录 F）
- 标定数据与设备绑定，更换设备需重跑平场标定
