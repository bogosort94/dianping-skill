"""
大众点评登录模块

有头浏览器扫码登录，Cookie 持久化。
与小红书 skill 不同，不需要保存二维码截图 — 用户直接在浏览器窗口扫码。
"""

import sys
import time
from typing import Optional, Tuple, Dict, Any

from .client import DianpingClient, DEFAULT_COOKIE_PATH, LOGIN_URL_PREFIX


class LoginAction:
    """登录动作"""

    def __init__(self, client: DianpingClient):
        self.client = client

    def check_login_status(self) -> Tuple[bool, Optional[str]]:
        """
        检查登录状态

        加载 cookie 后访问大众点评首页，检查是否被重定向到登录页。

        Returns:
            (是否已登录, 状态信息)
        """
        page = self.client.page

        try:
            self.client.navigate("https://www.dianping.com")
            time.sleep(2)

            current_url = page.url
            if LOGIN_URL_PREFIX in current_url:
                return False, None

            return True, "已登录"
        except Exception as e:
            print(f"检查登录状态失败: {e}", file=sys.stderr)
            return False, None

    def open_login_page(self):
        """
        打开登录页面（有头浏览器，用户直接看到二维码）
        """
        self.client.navigate("https://account.dianping.com/pclogin")
        time.sleep(2)

    def wait_for_login(self, timeout: int = 120) -> bool:
        """
        等待用户扫码登录

        轮询检测 URL 是否离开 account.dianping.com，成功后保存 cookie。

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否登录成功
        """
        page = self.client.page
        start = time.time()

        print(f"请在手机上打开大众点评 APP 扫码登录（最多等待 {timeout} 秒）...", file=sys.stderr)

        while time.time() - start < timeout:
            try:
                current_url = page.url
                # 登录成功后会重定向离开 account.dianping.com
                if LOGIN_URL_PREFIX not in current_url:
                    print("登录成功！", file=sys.stderr)
                    self.client._save_cookies()
                    return True
            except Exception:
                pass

            elapsed = int(time.time() - start)
            remaining = timeout - elapsed
            if remaining > 0 and remaining % 15 == 0:
                print(f"  仍在等待登录... 剩余 {remaining} 秒", file=sys.stderr)
            time.sleep(2)

        print("登录超时", file=sys.stderr)
        return False


# ====== 顶层便捷函数 ======

def check_login(
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> Tuple[bool, Optional[str]]:
    """检查登录状态"""
    client = DianpingClient(headless=True, cookie_path=cookie_path)
    try:
        client.start()
        action = LoginAction(client)
        return action.check_login_status()
    finally:
        client.close()


def login(
    headless: bool = False,
    cookie_path: str = DEFAULT_COOKIE_PATH,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    登录大众点评（打开浏览器 + 等待扫码）

    Returns:
        登录结果字典
    """
    client = DianpingClient(headless=headless, cookie_path=cookie_path)
    try:
        client.start()
        action = LoginAction(client)

        # 先检查是否已登录
        is_logged_in, _ = action.check_login_status()
        if is_logged_in:
            return {
                "status": "logged_in",
                "message": "已登录",
            }

        # 打开登录页
        action.open_login_page()

        # 等待扫码
        success = action.wait_for_login(timeout=timeout)
        if success:
            return {
                "status": "logged_in",
                "message": "扫码登录成功",
            }
        return {
            "status": "timeout",
            "message": "扫码超时",
        }
    finally:
        client.close()
