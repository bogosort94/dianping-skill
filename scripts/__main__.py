#!/usr/bin/env python3
"""
大众点评 CLI 入口
"""

import argparse
import json
import sys

from .client import DianpingClient, CaptchaError, LoginRequiredError, DEFAULT_COOKIE_PATH
from . import login
from . import search
from . import shop


def format_output(data) -> str:
    """格式化输出为 JSON"""
    if data is None:
        return json.dumps({"error": "No data"}, ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False, indent=2)


def _headless(args) -> bool:
    """从 args 解析 headless 值"""
    val = getattr(args, 'headless', 'true')
    if isinstance(val, bool):
        return val
    return val.lower() != 'false'


# ============================================================
# 命令处理函数
# ============================================================

def cmd_qrcode(args):
    """有头浏览器扫码登录"""
    cookie_path = args.cookie or DEFAULT_COOKIE_PATH

    # 先快速检查是否已登录
    is_logged_in, _ = login.check_login(cookie_path=cookie_path)
    if is_logged_in:
        print(format_output({"status": "logged_in", "message": "已登录"}))
        return 0

    # 未登录 → 启动可见浏览器
    client = DianpingClient(headless=False, cookie_path=cookie_path)
    try:
        client.start()
        action = login.LoginAction(client)

        # 打开登录页
        action.open_login_page()
        print(format_output({
            "status": "waiting",
            "message": "请在浏览器窗口中用大众点评 APP 扫码登录",
        }))

        # 等待扫码
        success = action.wait_for_login(timeout=120)
        if success:
            print(format_output({"status": "logged_in", "message": "登录成功！"}))
            return 0
        else:
            print(format_output({"status": "timeout", "message": "扫码超时"}))
            return 2
    finally:
        client.close()


def cmd_check_login(args):
    """检查登录状态"""
    is_logged_in, info = login.check_login(
        cookie_path=args.cookie or DEFAULT_COOKIE_PATH,
    )
    print(format_output({
        "is_logged_in": is_logged_in,
        "info": info,
    }))
    return 0


def cmd_search(args):
    """搜索商户"""
    results = search.search(
        keyword=args.keyword,
        city=args.city,
        limit=args.limit,
        headless=_headless(args),
        cookie_path=args.cookie or DEFAULT_COOKIE_PATH,
    )
    output = {
        "count": len(results),
        "results": results,
    }
    if len(results) == 0:
        output["warning"] = "未找到相关商户，请确认城市和关键词是否正确"
    print(format_output(output))
    return 0


def cmd_shop(args):
    """商户详情"""
    detail = shop.shop_detail(
        shop_id=args.shop_id,
        headless=_headless(args),
        cookie_path=args.cookie or DEFAULT_COOKIE_PATH,
    )
    print(format_output(detail))
    return 0 if detail else 1


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="大众点评 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 全局参数
    parser.add_argument("--cookie", "-c", help="Cookie 文件路径", default=None)
    parser.add_argument("--headless", help="无头模式: true/false（默认 true）", default='true')

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # qrcode
    qr_p = subparsers.add_parser("qrcode", help="有头浏览器扫码登录")
    qr_p.set_defaults(func=cmd_qrcode)

    # check-login
    chk_p = subparsers.add_parser("check-login", help="检查登录状态")
    chk_p.set_defaults(func=cmd_check_login)

    # search
    s_p = subparsers.add_parser("search", help="搜索商户")
    s_p.add_argument("keyword", help="搜索关键词")
    s_p.add_argument("--city", required=True, help="中文城市名（必填，如：杭州、昆明、大理，不是数字 ID）")
    s_p.add_argument("--sort-by", help="排序方式")
    s_p.add_argument("--limit", "-n", type=int, default=20, help="返回数量（默认 20）")
    s_p.add_argument("--headless", default='true')
    s_p.set_defaults(func=cmd_search)

    # shop
    sh_p = subparsers.add_parser("shop", help="获取商户详情")
    sh_p.add_argument("shop_id", help="商户 ID")
    sh_p.add_argument("--headless", default='true')
    sh_p.set_defaults(func=cmd_shop)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except CaptchaError as e:
        print(format_output({
            "status": "error",
            "error_type": "CaptchaError",
            "message": str(e),
            "captcha_url": e.captcha_url,
        }))
        return 1
    except LoginRequiredError as e:
        print(format_output({
            "status": "error",
            "error_type": "LoginRequiredError",
            "message": str(e),
            "action": "运行 python3 -m scripts qrcode 重新扫码登录",
        }))
        return 1
    except Exception as e:
        print(format_output({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
