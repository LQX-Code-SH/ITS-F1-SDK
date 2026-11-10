"""f1_thermal — INREII F1 热成像二次开发 SDK

支持:
  - 视频流采集 (USB bulk, 25fps, 256x192 Y16)
  - 帧同步解析 / 遥测参数块解码
  - 自校准测温 (T⁴) + 两点标定
  - 9 色板伪彩渲染 / 2x 超分 / NUC 去噪
  - 实时预览 (OpenCV)

典型用法:
    from f1_thermal import F1Camera, TempParams, colorize, temp_from_shutter_ref
    cam = F1Camera()
    frames = cam.read_frames(10)
    tp = TempParams(frames[0][1])
    tC = temp_from_shutter_ref(frames[0][0], shutter_raw_from_telemetry(frames[0][1]))
"""
from .camera import F1Camera, VID, PID, CMD_SHUTTER, CMD_WARM, CMD_COLD
from .temperature import (TempParams, temp_from_shutter_ref, shutter_raw_from_telemetry,
                          raw_to_signal, signal_to_tempC, load_temp_calib, K2C)
from .palettes import make_palette, colorize, super_resolve, apply_agc, PALETTES
from .denoise import load_flat, nuc_apply, build_flat, temporal_median

__version__ = '1.0.0'
__all__ = ['F1Camera', 'TempParams', 'temp_from_shutter_ref',
           'shutter_raw_from_telemetry', 'raw_to_signal', 'signal_to_tempC',
           'load_temp_calib', 'make_palette', 'colorize', 'super_resolve',
           'apply_agc', 'PALETTES', 'VID', 'PID', 'K2C',
           'load_flat', 'nuc_apply', 'build_flat', 'temporal_median']
