"""统一命令行入口: python -m its_sdk <子命令>"""
import argparse


def main():
    parser = argparse.ArgumentParser(prog='its_sdk', description='ITS F1 红外测温传感器 SDK')
    sub = parser.add_subparsers(dest='command', required=True)

    p_preview = sub.add_parser('preview', help='实时预览 (伪彩 + 温度标记)')
    p_preview.add_argument('palette', nargs='?', default='iron_bow',
                           help='色板名称, 默认 iron_bow')

    sub.add_parser('calibrate-flat', help='平场标定 (首次使用必做)')
    sub.add_parser('calibrate-temp', help='测温两点标定 (可选)')

    args = parser.parse_args()
    if args.command == 'preview':
        from .cli.preview import run
        run(args.palette)
    elif args.command == 'calibrate-flat':
        from .cli.calibrate_flat import main as calibrate_flat
        calibrate_flat()
    elif args.command == 'calibrate-temp':
        from .cli.calibrate_temp import main as calibrate_temp
        calibrate_temp()


if __name__ == '__main__':
    main()
