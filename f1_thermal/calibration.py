"""测温两点标定 (交互式) — 生成 calib/temp_calib.json

SOP 详见 docs/二次开发接口文档.md 第 5 节
"""
import datetime
import json

import numpy as np

from .camera import F1Camera
from .temperature import TempParams, shutter_raw_from_telemetry, temp_from_shutter_ref
from .palettes import apply_agc

CALIB_FILE = __import__('pathlib').Path(__file__).resolve().parent.parent / 'calib' / 'temp_calib.json'


def measure_stable_region(cam, label):
    input('  将镜头对准[%s], 画面稳定后按回车...' % label)
    frames = cam.read_frames(30, timeout=1200)
    if not frames:
        print('  采集失败!')
        return None
    tp = TempParams(frames[-1][1])
    sr = shutter_raw_from_telemetry(frames[-1][1])
    stack = np.stack([f[0].astype(np.float64) for f in frames])
    med = np.median(stack, axis=0)
    cy, cx = med.shape[0]//2, med.shape[1]//2
    tC = temp_from_shutter_ref(med[cy-24:cy+24, cx-32:cx+32], sr)
    val = float(np.median(tC))
    print('  当前模型读数: %.2f ℃ (快门参考=%d, 发射率=%.2f)'
          % (val, sr, tp.p42 if 0.5 < tp.p42 <= 1.0 else 0.98))
    return val


def save_calibration(points):
    """points: [(T_model, T_true), ...] 至少两点"""
    (m1, t1), (m2, t2) = points[0], points[-1]
    if abs(m2 - m1) < 3:
        raise ValueError('两点模型读数差过小(%.2f℃), 标定无效' % abs(m2-m1))
    a = (t2 - t1) / (m2 - m1)
    b = t1 - a * m1
    data = {'a': round(a, 5), 'b': round(b, 3),
            'points': points,
            'date': datetime.datetime.now().isoformat(),
            'device': 'F1'}
    CALIB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    from .temperature import reload_temp_calib
    reload_temp_calib()
    return a, b


def main():
    cam = F1Camera()
    pts = []
    try:
        while True:
            print('\n==== F1 两点标定 ====')
            print('  1. 冷点 (冰水混合物 0.0℃)')
            print('  2. 热点 (热水, 输入温度计实测值)')
            print('  3. 完成并保存标定')
            print('  4. 验证模式 (对照读数)')
            print('  q. 退出(不保存)')
            c = input('选择> ').strip()
            if c == '1':
                v = measure_stable_region(cam, '冰水混合物 0.0℃')
                if v is not None:
                    pts.append((v, 0.0))
                    print('  已记录冷点')
            elif c == '2':
                try:
                    t_true = float(input('  输入温度计实测水温(℃): '))
                except ValueError:
                    print('  无效输入')
                    continue
                v = measure_stable_region(cam, '热水 %.1f℃' % t_true)
                if v is not None:
                    pts.append((v, t_true))
                    print('  已记录热点')
            elif c == '3':
                if len(pts) < 2:
                    print('  至少需要 2 个标定点!')
                    continue
                a, b = save_calibration(pts)
                print('  标定已保存: %s' % CALIB_FILE)
                print('  修正公式: T真实 = %.4f × T模型 + %.3f' % (a, b))
            elif c == '4':
                v = measure_stable_region(cam, '任意目标')
                if v is not None:
                    try:
                        cal = json.loads(CALIB_FILE.read_text())
                        print('  模型 %.2f℃ -> 标定后 %.2f℃' % (v, cal['a']*v + cal['b']))
                    except FileNotFoundError:
                        print('  尚无标定文件')
            elif c.lower() == 'q':
                break
    finally:
        cam.close()


if __name__ == '__main__':
    main()
