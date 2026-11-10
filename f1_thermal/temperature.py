"""测温: 遥测解析 / T⁴ 自校准 / 两点标定加载"""
import json
import struct
from pathlib import Path

import numpy as np

K2C = 273.15
CALIB_DIR = Path(__file__).resolve().parent.parent / 'calib'
CALIB_FILE = CALIB_DIR / 'temp_calib.json'

# 原始计数校正多项式系数 (设备测温算法)
POLY = dict(a1=0.06939, a0=1.5587, a2=-0.00027816, a3=6.8455e-7)


class TempParams:
    """帧尾遥测块解析 (2048B = 4行x512B)

    属性: model/serial/version 设备信息;
          p30 标定温(25.0), p42 发射率(0.98), cal_floats 出厂标定浮点;
          dyn0/dyn32 动态计数字段 (dyn0[0]≈快门参考原始计数)
    """

    def __init__(self, telemetry: bytes):
        self.raw = telemetry
        r1 = telemetry[512:1024]
        self.cal_floats = list(struct.unpack('<5f', r1[6:26]))
        self.p26 = struct.unpack('<f', r1[26:30])[0]
        self.p30 = struct.unpack('<f', r1[30:34])[0]      # 标定温 25.0
        self.p34 = struct.unpack('<f', r1[34:38])[0]
        self.p38 = struct.unpack('<f', r1[38:42])[0]
        self.p42 = struct.unpack('<f', r1[42:46])[0]      # 发射率 0.98
        self.version = telemetry[512+48:512+63].split(b'\x00')[0].decode('ascii', 'ignore')
        self.serial = telemetry[512+64:512+79].split(b'\x00')[0].decode('ascii', 'ignore')
        self.model = telemetry[512+80:512+82].decode('ascii', 'ignore')
        self.dyn0 = struct.unpack('<HH', telemetry[0:4])
        self.dyn32 = struct.unpack('<H', telemetry[32:34])[0]

    def summary(self) -> str:
        return (f"型号={self.model} 序列号={self.serial} 固件={self.version}\n"
                f"标定浮点={['%.5g' % v for v in self.cal_floats]} "
                f"标定温={self.p30:.4g} 发射率={self.p42:.4g}")


def shutter_raw_from_telemetry(telemetry: bytes) -> int:
    """遥测行0 word0 = 快门参考原始计数"""
    return struct.unpack('<H', telemetry[0:2])[0]


def raw_to_signal(raw):
    """CalcFixRaw 多项式: raw Y16 -> 辐射信号"""
    r = np.asarray(raw, dtype=np.float64)
    return POLY['a1']*r + POLY['a0'] + POLY['a2']*r*r + POLY['a3']*r**3


def signal_to_tempC(signal, t_shutter_c=25.0, epsilon=0.98, calib=None):
    """T⁴ 环境混合公式 (设备测温算法还原)"""
    g, o = calib if calib else (1.0, 0.0)
    s = np.clip(signal, 1e-9, None) * g + o
    T4s = (t_shutter_c + K2C) ** 4
    A = (1.0 - epsilon) * T4s * 0.9
    T4 = np.clip(T4s - s * T4s * 0.02 - A, 1e-3, None)
    return np.power(T4 * epsilon, 0.25) - K2C


def temp_from_shutter_ref(img, shutter_raw, t_shutter_c=25.0):
    """
    自校准测温 (推荐入口):
        T(℃) = (T_shutter + 273.15) × (raw / shutter_raw)^0.25 − 273.15
    自动应用两点标定修正 (calib/temp_calib.json 存在时)。
    """
    r = np.clip(np.asarray(img, dtype=np.float64), 1.0, None)
    tC = (t_shutter_c + K2C) * np.power(r / max(shutter_raw, 1), 0.25) - K2C
    cal = load_temp_calib()
    if cal:
        tC = cal['a'] * tC + cal['b']
    return tC


_CALIB_CACHE = None


def load_temp_calib():
    """加载两点标定结果 (temp_calibration.py 生成); 无则返回 None"""
    global _CALIB_CACHE
    if _CALIB_CACHE is not None:
        return _CALIB_CACHE or None
    try:
        _CALIB_CACHE = json.loads(CALIB_FILE.read_text())
        return _CALIB_CACHE
    except Exception:
        _CALIB_CACHE = {}
        return None


def reload_temp_calib():
    """强制重新加载标定文件"""
    global _CALIB_CACHE
    _CALIB_CACHE = None
    return load_temp_calib()
