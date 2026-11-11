# ITS F1 Thermal Imaging SDK

面向 ITS F1 红外测温传感器（USB `04b4:000a`）的 Linux 端二次开发 SDK，
提供 Ubuntu 下的实时预览、测温、拍照与图像处理接口。

> **声明**: 本项目为独立的开源互操作项目，与设备制造商无任何隶属或授权关系。
> 本项目按"现状"提供，使用产生的任何风险由使用者自行承担。

## 功能

- **实时预览**: 伪彩画面 + 最高/最低温十字标记 + 温度条，支持热插拔
- **测温**: T⁴ 辐射模型 + 设备快门参考自校准，两点标定可达 ±2℃
- **图像处理**: 平场 NUC 去噪、坏点掩蔽、AGC、9 种伪彩色板、2× 超分
- **采集**: 25fps 连续流（256×192 Y16），单帧/批量保存

## 安装

```bash
pip3 install -r requirements.txt    # pyusb numpy scipy opencv-python-headless pillow
```

设备权限（二选一）：
- 临时：`sudo` 运行
- 永久：

```bash
sudo tee /etc/udev/rules.d/99-f1.rules <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="04b4", ATTRS{idProduct}=="000a", MODE="0666"
EOF
sudo udevadm control --reload && sudo udevadm trigger
```

## 快速开始

```bash
# 1. 平场标定（首次使用必做）: 运行后按提示, 前 6 秒用手掌盖住镜头
sudo -E python3 -m f1_thermal.nuc_calibrate

# 2. 实时预览
sudo -E python3 -m f1_thermal.preview

# 3. 测温两点标定（可选, 精度提升至 ±2℃）
sudo -E python3 -m f1_thermal.calibration
```

## Python API

```python
from f1_thermal import (F1Camera, TempParams, colorize, apply_agc,
                        temp_from_shutter_ref, shutter_raw_from_telemetry)

cam = F1Camera()
frames = cam.read_frames(10)

tp = TempParams(frames[0][1])       # 型号/序列号/固件/发射率
print(tp.summary())

sr = shutter_raw_from_telemetry(frames[0][1])
tC = temp_from_shutter_ref(frames[0][0], sr)   # 温度场 (℃)
rgb = colorize(apply_agc(tC), 'iron_bow')      # 伪彩 RGB
cam.close()
```

完整接口说明见 [docs/二次开发接口文档.md](docs/二次开发接口文档.md)。

## 项目结构

```
f1-thermal-sdk/
├── f1_thermal/           # Python 包
│   ├── camera.py         # USB 采集/帧同步/热插拔
│   ├── temperature.py    # 测温与遥测解析
│   ├── palettes.py       # 色板/AGC/超分
│   ├── denoise.py        # NUC 去噪
│   ├── calibration.py    # 测温两点标定 (CLI)
│   ├── nuc_calibrate.py  # 平场标定 (CLI)
│   └── preview.py        # 实时预览
├── calib/                # 标定数据 (flat_*.npy / temp_calib.json)
├── docs/                 # 接口文档
├── scripts/run_preview.sh
└── requirements.txt
```

## 已知限制

- 图像增强（调色板/测温/AGC）在主机端实现，设备仅输出原始 Y16 流
- 超分为插值占位实现，可替换为 GAN/ONNX 模型
- 测温出厂精度 ±3~5℃，两点标定后 ±2℃（SOP 见接口文档）
- 标定数据与设备绑定，更换设备需重跑平场标定

## Roadmap

- [x] 实时预览 / 热插拔 / 平场 NUC / T⁴ 测温 / 9 色板 / 2× 超分
- [ ] 测温两点标定执行（程序已就绪）
- [ ] 真实 GAN 超分（TNN→ONNX）
- [ ] 点击测温 / 区域统计 / 高低温报警
- [ ] MP4 录制、离线回放分析

## License

MIT — 见 [LICENSE](LICENSE)。
