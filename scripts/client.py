"""
大众点评浏览器客户端封装

基于 xiaohongshu-skill/scripts/client.py 架构，
适配大众点评反爬策略（HeadlessChrome 拦截、Cookie 城市锁定等）。
"""

import json
import os
import random
import sys
import time
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright  # pyrefly: ignore
except ImportError:
    print("请先安装 playwright: pip install playwright && playwright install chromium")
    raise


# Cookie 文件路径
DEFAULT_COOKIE_PATH = os.path.expanduser("~/.dianping/cookies.json")

# 验证码/安全拦截页面的 URL 特征
CAPTCHA_URL_PATTERNS = [
    'captcha',
    'security-verification',
    'verify',
    'reCAPTCHA',
]

# 验证码页面的标题特征
CAPTCHA_TITLE_PATTERNS = [
    '安全验证',
    '验证码',
    'captcha',
    'Security Verification',
]

# 登录页 URL 前缀（未登录时搜索会重定向到此）
LOGIN_URL_PREFIX = 'account.dianping.com'


class CaptchaError(Exception):
    """触发验证码异常"""
    def __init__(self, url: str, message: str = ""):
        self.captcha_url = url
        super().__init__(message or f"触发安全验证: {url}")


class LoginRequiredError(Exception):
    """Cookie 失效或未登录"""
    pass


class DianpingClient:
    """大众点评浏览器客户端"""

    # 频率控制参数
    MIN_INTERVAL = 3.0       # 两次导航最小间隔（秒）
    MAX_INTERVAL = 6.0       # 两次导航最大间隔（秒）
    BURST_THRESHOLD = 5      # 连续请求阈值，超过后增加额外冷却
    BURST_COOLDOWN = 10.0    # 连续请求冷却时间（秒）

    def __init__(
        self,
        headless: bool = True,
        cookie_path: str = DEFAULT_COOKIE_PATH,
        timeout: int = 60,
    ):
        self.headless = headless
        self.cookie_path = cookie_path
        self.timeout = timeout * 1000  # 转换为毫秒

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 请求计时器
        self._last_navigate_time: float = 0.0
        self._navigate_count: int = 0
        self._session_start: float = 0.0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """启动浏览器"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled'],
        )

        # 创建上下文 — 显式设置不含 HeadlessChrome 的 UA
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
        )

        # 加载 Cookie
        self._load_cookies()

        # 创建页面
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout)

    def close(self):
        """关闭浏览器"""
        # 保存 Cookie
        self._save_cookies()

        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _load_cookies(self):
        """从文件加载 Cookie"""
        if not os.path.exists(self.cookie_path):
            return

        try:
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            if cookies:
                self.context.add_cookies(cookies)
                print(f"已加载 {len(cookies)} 个 Cookie", file=sys.stderr)
        except Exception as e:
            print(f"加载 Cookie 失败: {e}", file=sys.stderr)

    def _save_cookies(self):
        """保存 Cookie 到文件"""
        if not self.context:
            return

        try:
            cookies = self.context.cookies()
            os.makedirs(os.path.dirname(self.cookie_path), exist_ok=True)
            with open(self.cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"已保存 {len(cookies)} 个 Cookie 到 {self.cookie_path}", file=sys.stderr)
        except Exception as e:
            print(f"保存 Cookie 失败: {e}", file=sys.stderr)

    def _throttle(self):
        """请求频率控制：模拟人类浏览节奏"""
        now = time.time()

        # 初始化会话起点
        if self._session_start == 0:
            self._session_start = now

        # 计算距上次导航的间隔
        elapsed = now - self._last_navigate_time if self._last_navigate_time > 0 else 999

        # 连续请求达到阈值 → 额外冷却
        if self._navigate_count > 0 and self._navigate_count % self.BURST_THRESHOLD == 0:
            cooldown = self.BURST_COOLDOWN + random.uniform(0, 3)
            if elapsed < cooldown:
                wait = cooldown - elapsed
                print(f"反爬保护: 连续请求 {self._navigate_count} 次，冷却 {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
        elif elapsed < self.MIN_INTERVAL:
            # 普通间隔控制
            wait = random.uniform(self.MIN_INTERVAL, self.MAX_INTERVAL) - elapsed
            if wait > 0:
                time.sleep(wait)

        self._last_navigate_time = time.time()
        self._navigate_count += 1

    def _check_captcha(self) -> bool:
        """
        检测当前页面是否被重定向到验证码页面

        Returns:
            True 表示触发了验证码
        """
        if not self.page:
            return False

        try:
            current_url = self.page.url.lower()
            for pattern in CAPTCHA_URL_PATTERNS:
                if pattern in current_url:
                    return True

            page_title = self.page.title().lower()
            for pattern in CAPTCHA_TITLE_PATTERNS:
                if pattern.lower() in page_title:
                    return True
        except Exception:
            pass

        return False

    def _handle_captcha(self):
        """
        处理验证码拦截：抛出异常通知调用方

        Raises:
            CaptchaError
        """
        url = self.page.url if self.page else "unknown"
        raise CaptchaError(
            url=url,
            message=(
                f"触发大众点评安全验证！\n"
                f"  验证页面: {url}\n"
                f"  本次会话已请求 {self._navigate_count} 次\n"
                f"  建议: 1) 等待几分钟后重试  2) 用 --headless=false 手动过验证码  "
                f"3) 重新扫码登录"
            ),
        )

    def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """导航到指定 URL（含频率控制和验证码检测）"""
        if not self.page:
            raise RuntimeError("浏览器未启动")

        # 频率控制
        self._throttle()

        self.page.goto(url, wait_until=wait_until)
        # 等待页面稳定
        time.sleep(random.uniform(1.5, 3.0))
        # 尝试等待 networkidle，但不强制
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # 验证码检测
        if self._check_captcha():
            self._handle_captcha()

        # 登录页重定向检测
        if LOGIN_URL_PREFIX in self.page.url:
            raise LoginRequiredError(
                "Cookie 已失效或未登录，页面被重定向到登录页。\n"
                "请运行 python3 -m scripts qrcode 重新扫码登录。"
            )

    def get_page_text(self, selector: str = 'body') -> str:
        """
        通过 inner_text 提取页面文本内容

        这是大众点评的主要数据提取方式（vs 小红书的 __INITIAL_STATE__）。

        Args:
            selector: CSS 选择器，默认 'body'

        Returns:
            页面文本内容
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")

        try:
            return self.page.inner_text(selector)
        except Exception:
            return ""

    def get_cookie_value(self, name: str) -> Optional[str]:
        """从当前上下文中获取指定 Cookie 的值"""
        if not self.context:
            return None
        for cookie in self.context.cookies():
            if cookie.get('name') == name:
                return cookie.get('value')
        return None

    def scroll_to_bottom(self, distance: int = 500):
        """滚动页面"""
        if not self.page:
            raise RuntimeError("浏览器未启动")

        self.page.evaluate(f"window.scrollBy(0, {distance})")
        time.sleep(0.5)


def create_client(
    headless: bool = True,
    cookie_path: str = DEFAULT_COOKIE_PATH,
    timeout: int = 60,
) -> DianpingClient:
    """创建大众点评客户端的便捷函数"""
    return DianpingClient(
        headless=headless,
        cookie_path=cookie_path,
        timeout=timeout,
    )
