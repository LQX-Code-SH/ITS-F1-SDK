"""运行数据路径集中定义

默认使用仓库根目录下的 calib/，可通过 F1_CALIB_DIR 环境变量覆盖。
环境变量在模块导入时读取；空值视为未设置，相对路径按进程当前目录解析，
建议使用绝对路径。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CALIB_DIR = PROJECT_ROOT / 'calib'

CALIB_DIR = Path(os.environ.get('F1_CALIB_DIR') or _DEFAULT_CALIB_DIR).expanduser()

CALIB_FILE = CALIB_DIR / 'temp_calib.json'
FLAT_GAIN = CALIB_DIR / 'flat_gain.npy'
FLAT_OFFSET = CALIB_DIR / 'flat_offset.npy'
FLAT_BAD = CALIB_DIR / 'flat_bad.npy'


def ensure_calib_dir():
    """创建标定目录 (写入标定数据前调用)"""
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
