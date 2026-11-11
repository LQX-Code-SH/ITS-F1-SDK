"""ITS F1 USB 相机核心: 采集 / 帧同步 / 设备信息"""
import numpy as np
import usb.core
import usb.util

VID, PID = 0x04B4, 0x000A          # USB 设备识别 ID
BLOCK, HDR = 14348, 12             # 流块: 12B头 + 14336B数据
W, H = 256, 192                    # 图像分辨率
BLOCK_TYPES = [0x01, 0x1D, 0x39, 0x55, 0x71, 0x8D, 0xA9]   # 帧内 7 块循环

# 扩展命令常量 (EP0 类请求, CS=0x0B)
CMD_SHUTTER         = 0x8000
CMD_BG_CORRECT      = 0x8001
CMD_LASER_CROSS_ON  = 0x8085
CMD_LASER_CROSS_OFF = 0x8086
CMD_COLD            = 0x80B0
CMD_WARM            = 0x80B1
CMD_BLINDPIX_OFF    = 0x8D00
CMD_BLINDPIX_ON     = 0x8D01

# 标准 UVC PU 控制 CS
PU_BRIGHTNESS, PU_CONTRAST, PU_GAIN = 0x02, 0x03, 0x04
PU_HUE, PU_SATURATION, PU_SHARPNESS, PU_GAMMA = 0x06, 0x07, 0x08, 0x09


class F1Camera:
    """ITS F1 热成像相机 (USB bulk 视频 + EP0 控制)

    用法:
        cam = F1Camera()
        frames = cam.read_frames(10)   # [(img(192,256)u16, telemetry bytes), ...]
        cam.close()
    """

    def __init__(self):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise RuntimeError("未找到 ITS F1 (04b4:000a)，请检查 USB 连接")
        self.dev.set_configuration()
        for ifn in (0, 1):
            try:
                if self.dev.is_kernel_driver_active(ifn):
                    self.dev.detach_kernel_driver(ifn)
            except Exception:
                pass
        usb.util.claim_interface(self.dev, 0)
        usb.util.claim_interface(self.dev, 1)
        self.dev.set_interface_altsetting(0, 1)   # 激活视频 bulk 端点
        self.buf = b""

    # ---------- 控制 (EP0) ----------
    def _zoom_cmd(self, value: int):
        self.dev.ctrl_transfer(0x21, 0x01, 0x0B00, 0,
                               (value & 0xFFFF).to_bytes(2, 'little'), 1000)

    def shutter(self):
        """触发快门校正"""
        self._zoom_cmd(CMD_SHUTTER)

    def set_warm(self, warm=True):
        """暖/冷色调"""
        self._zoom_cmd(CMD_WARM if warm else CMD_COLD)

    def set_u8(self, cs: int, v: int):
        """标准 PU 控制 SET (亮度/对比度/锐度/增益/伽马, cs 见 PU_* 常量)"""
        self.dev.ctrl_transfer(0x21, 0x01, cs << 8, 0,
                               (v & 0xFFFF).to_bytes(2, 'little'), 1000)

    def get_u16(self, cs: int) -> int:
        """标准 PU 控制 GET"""
        r = self.dev.ctrl_transfer(0xA1, 0x00, cs << 8, 0, 2, 1000)
        return int.from_bytes(bytes(r), 'little')

    # ---------- 视频流 ----------
    @staticmethod
    def _sync_anchor(data: bytes) -> int:
        """定位 TYPE=0x01 的真帧起始块"""
        for p in range(0, min(len(data) - HDR, 300000)):
            c = data[p:p+HDR]
            if (c[0] == 0x0C and 0x88 <= c[1] <= 0x90
                    and c[5:8] == b'\x00\x01\x00'
                    and c[8] == 0x01 and c[9:12] == b'\x00\x00\x00'):
                return p
        return -1

    def read_frames(self, n=1, timeout=2000):
        """读取 n 个完整帧。

        返回 list[(img, telemetry)]:
            img       np.uint16 (192, 256)  Y16 原始帧
            telemetry bytes (2048)          帧尾 4 行遥测/参数块
        """
        need = BLOCK * 7 * (n + 1)
        fails = 0
        while len(self.buf) < need and fails < 5:
            try:
                self.buf += bytes(self.dev.read(0x82, 16384, timeout))
            except usb.core.USBError:
                fails += 1
        data, self.buf = self.buf, b""
        anchor = self._sync_anchor(data)
        if anchor < 0:
            return []
        frames, i = [], anchor
        while i + BLOCK*7 <= len(data) and len(frames) < n:
            ok, payload = True, bytearray()
            for k in range(7):
                h = data[i+k*BLOCK: i+k*BLOCK+HDR]
                if not (h[0] == 0x0C and 0x88 <= h[1] <= 0x90
                        and h[5:8] == b'\x00\x01\x00'
                        and h[8] == BLOCK_TYPES[k % 7]):
                    ok = False
                    break
                payload += data[i+k*BLOCK+HDR: i+(k+1)*BLOCK]
            if ok:
                words = np.frombuffer(bytes(payload), dtype='<u2').reshape(H+4, W)
                frames.append((words[:H].copy(), words[H:].tobytes()))
                i += BLOCK*7
            else:
                i += 1
        return frames

    def close(self):
        try:
            usb.util.release_interface(self.dev, 0)
            usb.util.release_interface(self.dev, 1)
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

    @staticmethod
    def is_present() -> bool:
        """设备是否在位 (支持热插拔检测)"""
        return usb.core.find(idVendor=VID, idProduct=PID) is not None

    def read_frames_safe(self, n=1, timeout=1000):
        """带热插拔检测的读取。

        返回 (frames, ok):
            ok=True  frames 有效
            ok=False 设备已拔出 (调用方应 close 并等待重新插入)
        """
        if not self.is_present():
            return [], False
        try:
            return self.read_frames(n, timeout), True
        except usb.core.USBError:
            return [], False
