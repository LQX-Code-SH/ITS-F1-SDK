"""NUC 去噪: 平场标定 / 坏点掩蔽 / 暗场参考 / 多帧合成"""
import numpy as np
from scipy import ndimage

from .camera import F1Camera
from .temperature import CALIB_DIR

FLAT_GAIN = CALIB_DIR / 'flat_gain.npy'
FLAT_OFFSET = CALIB_DIR / 'flat_offset.npy'
FLAT_BAD = CALIB_DIR / 'flat_bad.npy'


def detect_bad_pixels(stack):
    """坏点: raw<100 / 饱和 / 偏离 5x5 邻域中值过大"""
    tmean = stack.mean(axis=0)
    med = ndimage.median_filter(tmean, size=5)
    return (tmean < 100) | (tmean > 65000) | (np.abs(tmean - med) > 400)


def replace_bad_pixels(img, bad):
    if bad is None or not bad.any():
        return img
    out = img.copy()
    out[bad] = ndimage.median_filter(img, size=5)[bad]
    return out


def detect_uniform_frames(stack, std_thresh=80):
    """均匀帧检测 (手掌盖镜/快门闭合): 帧空间 std 低于阈值"""
    stds = np.array([f.std() for f in stack])
    return np.where(stds < std_thresh)[0], stds


def build_flat(cam, n_read=300, win=12):
    """
    平场标定: 采集 n_read 帧, 自动检测最均匀的连续段 (需用户配合盖镜头),
    生成 offset(逐像素固定偏移) / gain(增益图) / bad(坏点掩码) 并保存.
    """
    frames = cam.read_frames(n_read, timeout=1000)
    if len(frames) < 20:
        raise RuntimeError('采集帧数不足: %d' % len(frames))
    stack = np.stack([f[0].astype(np.float32) for f in frames])
    energies = np.array([(stack[i:i+win] - ndimage.gaussian_filter(
        stack[i:i+win].mean(axis=0), 1.5)).std()
        for i in range(0, len(stack) - win)])
    i0 = int(np.argmin(energies))
    flat = stack[i0:i0+win].mean(axis=0)

    med5 = ndimage.median_filter(flat, size=5)
    bad = np.abs(flat - med5) > max(120, np.percentile(np.abs(flat - med5), 99.9) * 2.5)
    flat[bad] = med5[bad]

    flat_low = ndimage.gaussian_filter(flat, 6)
    gain = flat_low / np.median(flat_low)
    offset = flat - flat_low

    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    np.save(FLAT_GAIN, gain)
    np.save(FLAT_OFFSET, offset)
    np.save(FLAT_BAD, bad)
    return gain, offset, bad, i0


def load_flat():
    """加载已保存的平场标定; 无则返回 (None, None, None)"""
    try:
        return np.load(FLAT_GAIN), np.load(FLAT_OFFSET), np.load(FLAT_BAD)
    except FileNotFoundError:
        return None, None, None


def nuc_apply(scene, gain, offset, bad=None):
    """单帧 NUC: 扣偏移 + 除增益 + 坏点替换 + 残余列条纹去除 + 轻度平滑"""
    c = (np.asarray(scene, dtype=np.float32) - offset) / gain
    c = replace_bad_pixels(c, bad)
    col = ndimage.uniform_filter1d(c, size=32, axis=0)
    c = c - (col - ndimage.gaussian_filter(col, 6))
    return ndimage.median_filter(c, size=3)


def temporal_median(frames):
    """多帧中值 (时域降噪)"""
    return np.median(np.stack([f[0].astype(np.float32) for f in frames]), axis=0)


def dark_reference(frames):
    """无平场时的近似暗场: 时间std最小的连续帧均值"""
    stack = np.stack([f[0].astype(np.float32) for f in frames])
    if len(stack) < 6:
        return None
    tstd = np.array([stack[i:i+4].std(axis=0).mean() for i in range(len(stack)-3)])
    i0 = int(np.argmin(tstd))
    return stack[i0:i0+4].mean(axis=0)


def nuc_capture_shutter(cam, wait_s=1.2, frames_after=40):
    """触发快门命令后抓闭合帧作暗场 (F1 未验证: 设备可能不响应 EP0 命令)"""
    import time
    cam.shutter()
    time.sleep(wait_s)
    fr = cam.read_frames(frames_after, timeout=1000)
    return dark_reference(fr) if len(fr) >= 6 else None
