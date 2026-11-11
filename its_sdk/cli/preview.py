"""ITS F1 实时预览 (OpenCV) — 伪彩 + 最高/最低温标记 + 温度条"""
import sys
import time

import cv2
import numpy as np

from ..camera import F1Camera
from ..temperature import shutter_raw_from_telemetry, temp_from_shutter_ref
from ..render import colorize, PALETTES
from ..denoise import load_flat, nuc_apply
from ..paths import FLAT_OFFSET, IMAGES_DIR, ensure_calib_dir, ensure_images_dir

W, H = 256, 192
SCALE = 3

CUR_PALETTE = ['iron_bow']
FPS = [0.0]


def draw_temp_bar(frame_img, tmin, tmax):
    """右侧垂直温度条 (注意: cv2 画布为 BGR)"""
    bar_h, bar_w = H*SCALE - 40, 22
    x0 = W*SCALE + 20
    y0 = 20
    grad = np.linspace(255, 0, bar_h, dtype=np.uint8)
    colors = colorize(grad, CUR_PALETTE[0])[:, ::-1]     # RGB -> BGR
    for i in range(bar_h):
        frame_img[y0+i, x0:x0+bar_w] = colors[i]
    for frac, label in ((0.0, '%.1f' % tmax), (1.0, '%.1f' % tmin)):
        ty = y0 + int(frac * (bar_h-1))
        cv2.line(frame_img, (x0+bar_w, ty), (x0+bar_w+6, ty), (255, 255, 255), 1)
        cv2.putText(frame_img, label, (x0+bar_w+8, ty+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)


def compose(tC, tmin, tmax):
    """温度场 -> 标注后的 BGR 画布"""
    u8 = np.clip((tC - tmin) / (tmax - tmin + 1e-9) * 255, 0, 255).astype(np.uint8)
    rgb = colorize(u8, CUR_PALETTE[0])
    imax = np.unravel_index(np.argmax(tC), tC.shape)
    imin = np.unravel_index(np.argmin(tC), tC.shape)
    cv2.drawMarker(rgb, (imax[1], imax[0]), (0, 255, 0), cv2.MARKER_CROSS, 14, 1)
    cv2.drawMarker(rgb, (imin[1], imin[0]), (255, 255, 0), cv2.MARKER_CROSS, 14, 1)
    cv2.putText(rgb, '%.1f' % tC[imax], (imax[1]+8, imax[0]-4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 0), 1, cv2.LINE_AA)
    cv2.putText(rgb, '%.1f' % tC[imin], (imin[1]+8, imin[0]-4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 0), 1, cv2.LINE_AA)
    big = cv2.resize(rgb, (W*SCALE, H*SCALE), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((H*SCALE + 30, W*SCALE + 90, 3), dtype=np.uint8)
    canvas[15:15+H*SCALE, 0:W*SCALE] = cv2.cvtColor(big, cv2.COLOR_RGB2BGR)
    draw_temp_bar(canvas, tmin, tmax)
    cv2.putText(canvas, 'ITS F1  %.1f C / %.1f C  %dfps  [%s]'
                % (tmax, tmin, FPS[0], CUR_PALETTE[0]),
                (6, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def run(palette='iron_bow'):
    if palette not in PALETTES:
        raise SystemExit("未知色板 %r, 可选: %s" % (palette, ', '.join(PALETTES)))
    CUR_PALETTE[0] = palette
    gain, offset, bad = load_flat()
    print("平场标定:", "已加载" if gain is not None else "未找到(退化用行列校正)")

    cam = None
    open_err = None
    fps_t, fps_n = time.time(), 0
    shutter_hold = 0
    fail_count = 0
    buf = []
    cv2.namedWindow('ITS F1 Thermal', cv2.WINDOW_AUTOSIZE)
    print("实时预览已启动 (q退出 p色板 s截图 n刷新偏置) — 支持热插拔")
    try:
        while True:
            # ---- 设备管理: 热插拔 ----
            if cam is None:
                if F1Camera.is_present():
                    try:
                        cam = F1Camera()
                        buf = []
                        fail_count = 0
                        open_err = None
                        print("设备已连接")
                    except RuntimeError as e:
                        if str(e) != open_err:      # 同一错误只提示一次
                            open_err = str(e)
                            print("打开设备失败:", e)
                if cam is None:
                    wait = np.zeros((H*SCALE+30, W*SCALE+90, 3), dtype=np.uint8)
                    cv2.putText(wait, 'Waiting for ITS F1 device...',
                                (30, H*SCALE//2), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 255, 255), 1, cv2.LINE_AA)
                    cv2.imshow('ITS F1 Thermal', wait)
                    if cv2.waitKey(500) & 0xFF == ord('q'):
                        break
                    continue

            frames, ok = cam.read_frames_safe(4, timeout=600)
            if not ok:
                fail_count += 1
                if fail_count >= 2:
                    print("设备已拔出, 等待重新连接...")
                    cam.close()
                    cam = None
                continue
            fail_count = 0
            if not frames:
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            buf.extend(frames)
            buf = buf[-9:]
            stack = np.stack([f[0].astype(np.float32) for f in buf])

            if float(stack[-1].std()) < 60:          # 快门闭合帧
                shutter_hold += 1
                if shutter_hold == 4 and gain is not None:
                    offset = offset - (stack[-4:].mean(axis=0)
                                       - np.median(stack[-4:])) * 0.5
                continue
            shutter_hold = 0

            scene = np.median(stack, axis=0)
            if gain is not None:
                proc = nuc_apply(scene, gain, offset, bad)
            else:
                proc = scene - scene.mean(axis=0, keepdims=True) \
                           - scene.mean(axis=1, keepdims=True) + scene.mean()

            tC = temp_from_shutter_ref(proc, shutter_raw_from_telemetry(frames[-1][1]))
            tC = np.clip(tC, *np.percentile(tC, [0.2, 99.8]))

            fps_n += 1
            if time.time() - fps_t >= 1.0:
                FPS[0] = fps_n
                fps_n = 0
                fps_t = time.time()

            cv2.imshow('ITS F1 Thermal', compose(tC, float(tC.min()), float(tC.max())))
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('p'):
                CUR_PALETTE[0] = PALETTES[(PALETTES.index(CUR_PALETTE[0]) + 1) % len(PALETTES)]
            elif key == ord('s'):
                fn = IMAGES_DIR / ('live_%d.png' % int(time.time()))
                ensure_images_dir()
                cv2.imwrite(str(fn), compose(tC, float(tC.min()), float(tC.max())))
                print('已保存', fn)
            elif key == ord('n') and gain is not None:
                fr = cam.read_frames(40, timeout=800)
                if fr:
                    st = np.stack([f[0].astype(np.float32) for f in fr])
                    offset = offset - (st.mean(axis=0) - np.median(st)) * 0.5
                    ensure_calib_dir()
                    np.save(FLAT_OFFSET, offset)
                    print('偏置已刷新')
    except KeyboardInterrupt:
        pass
    finally:
        if cam is not None:
            cam.close()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    pal = sys.argv[1] if len(sys.argv) > 1 else 'iron_bow'
    run(pal)
