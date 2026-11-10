"""平场标定 CLI: 采集期间自动检测均匀段(盖镜头), 生成 calib/flat_*.npy"""
import numpy as np

from .camera import F1Camera
from .denoise import build_flat, load_flat, nuc_apply
from .palettes import colorize, apply_agc


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
            Image = __import__('PIL.Image', fromlist=['Image']).Image
            W, H = 256, 192
            cmp_img = Image.new('RGB', (W*4+30, H*2+40), (25, 25, 25))
            cmp_img.paste(Image.fromarray(colorize(apply_agc(before), 'iron_bow'))
                          .resize((W*2, H*2)), (0, 20))
            cmp_img.paste(Image.fromarray(colorize(apply_agc(after), 'iron_bow'))
                          .resize((W*2, H*2)), (W*2+30, 20))
            cmp_img.save('nuc_result.png')
            print("对比图 nuc_result.png 已保存")
    finally:
        cam.close()


def ndimage_gaussian(img):
    from scipy import ndimage
    return ndimage.gaussian_filter(img, 1.5)


if __name__ == '__main__':
    main()
