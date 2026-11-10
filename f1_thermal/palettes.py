"""伪彩色板 (9 种 LUT) / AGC / R+ 超分"""
import numpy as np

PALETTES = ['white_hot', 'black_hot', 'rainbow', 'iron_bow', 'lava',
            'arctic', 'glory', 'red_hot', 'medical']


def make_palette(name: str) -> np.ndarray:
    """生成 256x3 (RGB u8) 色板 LUT"""
    x = np.linspace(0, 1, 256)
    if name == 'white_hot':
        lut = np.stack([x]*3, axis=1)
    elif name == 'black_hot':
        lut = np.stack([1-x]*3, axis=1)
    elif name == 'iron_bow':
        # 标准铁红: 黑→蓝紫→红→橙→黄→白 (控制点插值)
        pts = [(0.00, (0.00, 0.00, 0.02)), (0.15, (0.15, 0.02, 0.35)),
               (0.35, (0.55, 0.00, 0.45)), (0.55, (0.90, 0.10, 0.10)),
               (0.75, (1.00, 0.45, 0.00)), (0.90, (1.00, 0.80, 0.10)),
               (1.00, (1.00, 1.00, 0.92))]
        xs = [p[0] for p in pts]
        lut = np.stack([np.interp(x, xs, [p[1][c] for p in pts]) for c in range(3)], axis=1)
    elif name == 'rainbow':
        lut = np.stack([np.clip(1.5-2*np.abs(x-v), 0, 1) for v in (0.8, 0.5, 0.2)], axis=1)
    elif name == 'lava':
        lut = np.stack([np.clip(x*1.8, 0, 1), np.clip(x*x*1.4-0.3, 0, 1),
                        np.clip((x-0.75)*3.5, 0, 1)], axis=1)
    elif name == 'arctic':
        lut = np.stack([np.clip((x-0.6)*2.2, 0, 1), np.clip((x-0.25)*1.7, 0, 1),
                        np.clip(x*1.6+0.1, 0, 1)], axis=1)
    elif name == 'glory':
        lut = np.stack([np.clip(np.sin(x*np.pi), 0, 1),
                        np.clip(np.sin(x*np.pi*0.7), 0, 1),
                        np.clip(0.5+0.5*np.cos(x*np.pi*1.3), 0, 1)], axis=1)
    elif name == 'red_hot':
        lut = np.stack([x, np.clip(x*0.25, 0, 1), np.zeros(256)], axis=1)
    elif name == 'medical':
        lut = np.stack([np.clip(1.4*x-0.2, 0, 1),
                        np.clip(0.8-1.2*np.abs(x-0.55), 0.05, 1),
                        np.clip(0.9-x*1.1, 0, 1)], axis=1)
    else:
        lut = np.stack([x]*3, axis=1)
    return (np.clip(lut, 0, 1) * 255).astype(np.uint8)


def colorize(img_u8, palette='white_hot'):
    """8bit 灰度 -> 伪彩 RGB"""
    return make_palette(palette)[img_u8]


def apply_agc(img, lo_p=1, hi_p=99):
    """百分位拉伸 -> u8"""
    lo, hi = np.percentile(img, [lo_p, hi_p])
    return np.clip((img - lo) / (hi - lo + 1e-9) * 255, 0, 255).astype(np.uint8)


def super_resolve(img_u8, scale=2):
    """
    R+ 超分 (占位): Lanczos scale倍 + 非锐化掩模.
    官方为 TNN GAN 模型 (APK assets/cplus/*.tnnmodel), 可转 ONNX 后替换.
    """
    from PIL import Image, ImageFilter
    im = Image.fromarray(img_u8)
    w, h = im.size
    im = im.resize((w*scale, h*scale), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
    return np.array(im)
