"""
大众点评商户详情模块

通过 DOM 提取商户详细信息。
"""

import re
import sys
import time
from typing import Optional, Dict, Any

from .client import DianpingClient, DEFAULT_COOKIE_PATH


class ShopDetailAction:
    """商户详情动作"""

    def __init__(self, client: DianpingClient):
        self.client = client

    def _make_shop_url(self, shop_id: str) -> str:
        """构建商户详情 URL"""
        return f"https://www.dianping.com/shop/{shop_id}"

    def get_shop_detail(self, shop_id: str) -> Optional[Dict[str, Any]]:
        """
        获取商户详细信息

        Args:
            shop_id: 商户 ID

        Returns:
            商户详情数据
        """
        client = self.client
        page = client.page

        url = self._make_shop_url(shop_id)
        print(f"打开商户详情页: {url}", file=sys.stderr)
        client.navigate(url)
        time.sleep(2)

        # 滚动页面加载更多内容
        for _ in range(3):
            client.scroll_to_bottom(500)

        # 通过 JS 在浏览器端提取结构化数据
        detail = page.evaluate("""(shopId) => {
            const result = {shop_id: shopId};

            // 商户名
            const nameEl = document.querySelector('h1.shop-name, .shop-name, h1');
            if (nameEl) result.name = nameEl.textContent.trim();

            // 评分
            const ratingEl = document.querySelector('.brief-info .mid-rank-stars, .score');
            if (ratingEl) {
                const title = ratingEl.getAttribute('title') || ratingEl.textContent.trim();
                result.rating = title;
            }

            // 整体文本（用于正则提取）
            const bodyText = document.body.innerText;
            result._body_text = bodyText;

            return result;
        }""", shop_id)

        if not detail:
            print("未获取到商户详情", file=sys.stderr)
            return None

        # 从 body text 中正则提取额外字段
        body_text = detail.pop('_body_text', '')
        self._extract_from_text(detail, body_text)

        return detail

    def _extract_from_text(self, detail: Dict[str, Any], text: str):
        """从页面文本中提取结构化字段"""
        # 人均
        avg_match = re.search(r'人均\s*[￥¥]\s*(\d+)', text)
        if avg_match:
            detail["avg_price"] = int(avg_match.group(1))

        # 地址
        addr_match = re.search(r'地址[：:]\s*(.+?)(?:\n|电话|营业)', text)
        if addr_match:
            detail["address"] = addr_match.group(1).strip()

        # 电话
        phone_match = re.search(r'电话[：:]\s*([\d\-\s]+)', text)
        if phone_match:
            detail["phone"] = phone_match.group(1).strip()

        # 营业时间
        hours_match = re.search(r'营业时间[：:]\s*(.+?)(?:\n|$)', text)
        if hours_match:
            detail["hours"] = hours_match.group(1).strip()

        # 评价数
        review_match = re.search(r'(\d+)\s*条评价', text)
        if review_match:
            detail["review_count"] = int(review_match.group(1))

        # 口味/环境/服务评分
        score_match = re.search(r'口味\s*([\d.]+)\s*环境\s*([\d.]+)\s*服务\s*([\d.]+)', text)
        if score_match:
            detail["score_taste"] = score_match.group(1)
            detail["score_env"] = score_match.group(2)
            detail["score_service"] = score_match.group(3)

        # 如果没有提取到足够信息，保留原始文本的前 500 字符方便调试
        extracted_fields = {"avg_price", "address", "phone", "hours", "review_count", "score_taste"}
        if not any(k in detail for k in extracted_fields):
            detail["raw_text"] = text[:500]


# ====== 顶层便捷函数 ======

def shop_detail(
    shop_id: str,
    headless: bool = True,
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> Optional[Dict[str, Any]]:
    """
    获取商户详情

    Args:
        shop_id: 商户 ID
        headless: 是否无头模式
        cookie_path: Cookie 路径

    Returns:
        商户详情数据
    """
    client = DianpingClient(
        headless=headless,
        cookie_path=cookie_path,
    )

    try:
        client.start()
        action = ShopDetailAction(client)
        return action.get_shop_detail(shop_id=shop_id)
    finally:
        client.close()
