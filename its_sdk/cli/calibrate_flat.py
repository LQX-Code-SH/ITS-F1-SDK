"""平场标定 CLI: 采集期间自动检测均匀段(盖镜头), 生成 calib/flat_*.npy

标定目录默认 calib/，可用 F1_CALIB_DIR 环境变量覆盖。
"""
import numpy as np
from PIL import Image

from ..camera import F1Camera
from ..denoise import build_flat, nuc_apply
from ..paths import IMAGES_DIR, ensure_images_dir
from ..render import colorize, apply_agc


def main():
    cam = F1Camera()
    try:
        print("开始采集 300 帧 (~12s) —— 请在前 6 秒用手掌盖住镜头!")
        gain, offset, bad, i0 = build_flat(cam, n_read=300)
        print("标定完成: 均匀段帧#%d, 坏点 %d 个" % (i0, int(bad.sum())))

        # 立即用标定渲染一帧验证
        frames = cam.read_frames(20, timeout=1500)
        if frames:
            stack = np.stack([f[0].astype(np.float32) for f in frames])
            scene = np.median(stack, axis=0)
            after = nuc_apply(scene, gain, offset, bad)
            before = scene - scene.mean(axis=0, keepdims=True) \
                           - scene.mean(axis=1, keepdims=True) + scene.mean()
            print("高频噪声: 前=%.1f 后=%.1f" % (
                float((before - ndimage_gaussian(before)).std()),
                float((after - ndimage_gaussian(after)).std())))
            W, H = 256, 192
            cmp_img = Image.new('RGB', (W*4+30, H*2+40), (25, 25, 25))
            cmp_img.paste(Image.fromarray(colorize(apply_agc(before), 'iron_bow'))
                          .resize((W*2, H*2)), (0, 20))
            cmp_img.paste(Image.fromarray(colorize(apply_agc(after), 'iron_bow'))
                          .resize((W*2, H*2)), (W*2+30, 20))
            out = IMAGES_DIR / 'nuc_result.png'
            ensure_images_dir()
            cmp_img.save(str(out))
            print("对比图 %s 已保存" % out)
    finally:
        cam.close()


def ndimage_gaussian(img):
    from scipy import ndimage
    return ndimage.gaussian_filter(img, 1.5)


if __name__ == '__main__':
    main()
