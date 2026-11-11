"""导入与 CLI 冒烟测试 (stdlib unittest, 无需设备)"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SmokeTest(unittest.TestCase):
    def test_public_api(self):
        import its_sdk
        for name in ('F1Camera', 'TempParams', 'colorize', 'apply_agc',
                     'temp_from_shutter_ref', 'shutter_raw_from_telemetry',
                     'load_flat', 'nuc_apply'):
            self.assertTrue(hasattr(its_sdk, name), name)
        self.assertRegex(its_sdk.__version__, r'^\d+\.\d+\.\d+$')

    def test_cli_help(self):
        r = subprocess.run([sys.executable, '-m', 'its_sdk', '--help'],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for cmd in ('preview', 'calibrate-flat', 'calibrate-temp'):
            self.assertIn(cmd, r.stdout)

    def test_calib_dir_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'calib')
            env = dict(os.environ, F1_CALIB_DIR=target, PYTHONPATH=str(ROOT))
            code = ('from its_sdk.paths import CALIB_DIR, ensure_calib_dir;'
                    'ensure_calib_dir(); print(CALIB_DIR)')
            r = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), target)
            self.assertTrue(os.path.isdir(target))

    def test_images_dir(self):
        from its_sdk.paths import IMAGES_DIR
        self.assertEqual(IMAGES_DIR, ROOT / 'images')

    def test_empty_calib_dir_falls_back(self):
        env = dict(os.environ, F1_CALIB_DIR='', PYTHONPATH=str(ROOT))
        r = subprocess.run([sys.executable, '-c',
                            'from its_sdk.paths import CALIB_DIR; print(CALIB_DIR)'],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(Path(r.stdout.strip()), ROOT / 'calib')

    def test_preview_rejects_unknown_palette(self):
        r = subprocess.run([sys.executable, '-m', 'its_sdk', 'preview', 'bogus'],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('未知色板', r.stderr)


if __name__ == '__main__':
    unittest.main()
