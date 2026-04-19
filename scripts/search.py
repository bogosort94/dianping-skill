"""
大众点评搜索模块

通过 DOM inner_text 提取搜索结果（不依赖 __INITIAL_STATE__）。
支持城市切换和自动翻页。
"""

import re
import sys
import time
from typing import Optional, List, Dict, Any

from .client import DianpingClient, DEFAULT_COOKIE_PATH


# 空结果页/错误页的关键词
EMPTY_PAGE_PATTERNS = ["没有找到", "很抱歉", "无搜索结果", "暂无相关", "未找到"]


# 城市名 → (city_id, city_pinyin) 映射
# city_id 用于搜索 URL，city_pinyin 用于城市切换
CITY_MAP = {
    "北京": (1, "beijing"),
    "上海": (2, "shanghai"),
    "杭州": (3, "hangzhou"),
    "广州": (4, "guangzhou"),
    "深圳": (7, "shenzhen"),
    "成都": (8, "chengdu"),
    "武汉": (5, "wuhan"),
    "南京": (9, "nanjing"),
    "重庆": (17, "chongqing"),
    "天津": (10, "tianjin"),
    "西安": (6, "xian"),
    "长沙": (26, "changsha"),
    "苏州": (11, "suzhou"),
    "厦门": (15, "xiamen"),
    "昆明": (23, "kunming"),
    "大理": (252, "dali"),
    "丽江": (108, "lijiang"),
    "三亚": (135, "sanya"),
    "青岛": (13, "qingdao"),
    "郑州": (12, "zhengzhou"),
    "沈阳": (14, "shenyang"),
    "哈尔滨": (16, "haerbin"),
    "济南": (19, "jinan"),
    "合肥": (20, "hefei"),
    "福州": (21, "fuzhou"),
    "无锡": (22, "wuxi"),
    "宁波": (28, "ningbo"),
    "东莞": (29, "dongguan"),
    "佛山": (30, "foshan"),
    "贵阳": (31, "guiyang"),
    "南宁": (32, "nanning"),
    "太原": (24, "taiyuan"),
    "石家庄": (25, "shijiazhuang"),
    "长春": (27, "changchun"),
    "珠海": (42, "zhuhai"),
    "温州": (46, "wenzhou"),
    "常州": (50, "changzhou"),
    "中山": (43, "zhongshan"),
    "烟台": (53, "yantai"),
    "惠州": (55, "huizhou"),
    "南昌": (36, "nanchang"),
    "大连": (18, "dalian"),
    "兰州": (33, "lanzhou"),
    "海口": (113, "haikou"),
    "拉萨": (200, "lasa"),
    "香港": (999, "hongkong"),
    "澳门": (998, "aomen"),
}


def get_city_info(city_name: str) -> Optional[tuple]:
    """
    从静态映射表获取城市信息

    Args:
        city_name: 城市名（如：杭州、上海）

    Returns:
        (city_id, city_pinyin) 或 None（未找到）
    """
    return CITY_MAP.get(city_name)


class SearchAction:
    """搜索动作"""

    def __init__(self, client: DianpingClient):
        self.client = client

    def _resolve_city_dynamic(self, city_name: str) -> tuple:
        """
        动态解析城市：通过浏览器访问大众点评城市列表页，查找目标城市的链接

        Args:
            city_name: 城市名

        Returns:
            (city_id, city_pinyin)

        Raises:
            ValueError: 找不到城市
        """
        print(f"城市 '{city_name}' 不在缓存中，尝试动态解析...", file=sys.stderr)

        self.client.navigate("https://www.dianping.com/citylist")
        time.sleep(2)

        # 在城市列表页中查找包含目标城市名的链接
        result = self.client.page.evaluate("""(cityName) => {
            // 查找所有城市链接
            const links = document.querySelectorAll('a[href*="dianping.com/"]');
            for (const a of links) {
                const text = a.textContent.trim();
                if (text === cityName) {
                    const href = a.getAttribute('href');
                    if (!href) continue;
                    // 处理 https://www.dianping.com/kunming 或 /kunming
                    const path = href.split('?')[0];
                    const parts = path.split('/').filter(p => p && p !== 'www.dianping.com');
                    if (parts.length > 0) {
                        return {pinyin: parts[parts.length - 1]};
                    }
                }
            }
            return null;
        }""", city_name)

        if not result:
            available = "、".join(sorted(CITY_MAP.keys()))
            raise ValueError(
                f"无法找到城市: {city_name}\n"
                f"静态缓存中的城市: {available}\n"
                f"动态解析也未找到，请确认城市名称是否正确"
            )

        city_pinyin = result["pinyin"]

        # 访问该城市首页，从 Cookie cy 获取 city_id
        city_url = f"https://www.dianping.com/{city_pinyin}"
        print(f"动态解析: 访问 {city_url} 获取城市 ID", file=sys.stderr)
        self.client.navigate(city_url)
        time.sleep(1)

        cy_value = self.client.get_cookie_value('cy')
        if cy_value:
            city_id = int(cy_value)
        else:
            # 从 URL 重定向中提取，或默认用 0
            city_id = 0
            print("警告: 无法从 Cookie 获取城市 ID，使用 0", file=sys.stderr)

        # 缓存到 CITY_MAP 供后续使用
        CITY_MAP[city_name] = (city_id, city_pinyin)
        print(f"动态解析成功: {city_name} → ID={city_id}, pinyin={city_pinyin}", file=sys.stderr)

        return city_id, city_pinyin

    def _switch_city(self, city_name: str) -> int:
        """
        切换城市：访问城市首页，从 Cookie cy 获取真实城市 ID

        CITY_MAP 中的 ID 可能不准确，所以始终以 Cookie cy 为准。

        Args:
            city_name: 城市名

        Returns:
            city_id（来自 Cookie cy）
        """
        info = get_city_info(city_name)
        if info:
            _, city_pinyin = info
            city_url = f"https://www.dianping.com/{city_pinyin}"
            print(f"切换城市: {city_name} ({city_url})", file=sys.stderr)
            self.client.navigate(city_url)
            time.sleep(1)
        else:
            # 动态解析（会自动访问城市首页）
            _, city_pinyin = self._resolve_city_dynamic(city_name)

        # 从 Cookie cy 获取真实城市 ID
        cy_value = self.client.get_cookie_value('cy')
        if cy_value:
            city_id = int(cy_value)
            print(f"城市 ID（来自 Cookie cy）: {city_id}", file=sys.stderr)
        else:
            # fallback: 用 CITY_MAP 中的 ID
            if info:
                city_id = info[0]
                print(f"警告: Cookie cy 未设置，使用缓存 ID={city_id}", file=sys.stderr)
            else:
                city_id = 0
                print("警告: Cookie cy 未设置，使用 ID=0", file=sys.stderr)

        return city_id

    def _make_search_url(self, keyword: str, city_id: int) -> str:
        """构建搜索 URL"""
        return f"https://www.dianping.com/search/keyword/{city_id}/0_{keyword}"

    def _check_empty_results(self) -> bool:
        """检测当前页面是否为空结果/错误页。返回 True 表示无有效结果。"""
        body_text = self.client.get_page_text()
        for pattern in EMPTY_PAGE_PATTERNS:
            if pattern in body_text:
                return True
        return False

    def _extract_results(self) -> List[Dict[str, Any]]:
        """
        从当前页 DOM 提取搜索结果列表

        Returns:
            商户列表
        """
        page = self.client.page

        # 使用 JS 在浏览器端提取结构化数据，比 inner_text + 正则更可靠
        results = page.evaluate("""() => {
            const items = document.querySelectorAll('#shop-all-list .shop-list ul li, .shoplist .shop-list ul li, .shop-wrap .shop-list ul li');
            if (items.length === 0) {
                // 备用选择器
                const altItems = document.querySelectorAll('[class*="shop-list"] li');
                if (altItems.length > 0) {
                    return Array.from(altItems).map(li => ({text: li.innerText}));
                }
                return [];
            }

            return Array.from(items).map(li => {
                const titleEl = li.querySelector('.tit a, h4 a, .shopname a');
                const name = titleEl ? titleEl.textContent.trim() : '';
                const href = titleEl ? titleEl.getAttribute('href') : '';

                // 从 href 提取 shop_id（格式：/shop/xxxxx）
                let shopId = '';
                if (href) {
                    const m = href.match(/\\/shop\\/(\\w+)/);
                    if (m) shopId = m[1];
                }

                const text = li.innerText;
                return {name, shop_id: shopId, text, href};
            });
        }""")

        if not results:
            return []

        shops = []
        for item in results:
            if not item.get('name') and not item.get('text'):
                continue

            shop = self._parse_shop_item(item)
            if shop:
                shops.append(shop)

        return shops

    def _parse_shop_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析单个商户项

        Args:
            item: 从 JS 提取的原始数据

        Returns:
            结构化商户数据
        """
        text = item.get('text', '')
        if not text.strip():
            return None

        shop = {
            "name": item.get('name', ''),
            "shop_id": item.get('shop_id', ''),
        }

        # 结果清洗：过滤无效条目
        name = shop["name"]
        if len(name) <= 1:
            return None
        if not shop["shop_id"]:
            return None
        for bad_word in EMPTY_PAGE_PATTERNS:
            if bad_word in name:
                return None

        # 从文本中提取人均价格（实际格式：人均 ￥144）
        avg_match = re.search(r'人均\s*[￥¥]\s*(\d+)', text)
        if avg_match:
            shop["avg_price"] = int(avg_match.group(1))

        # 提取评价数
        review_match = re.search(r'(\d+)\s*条评价', text)
        if review_match:
            shop["review_count"] = int(review_match.group(1))

        # 提取评分（如 4.5）
        rating_match = re.search(r'(\d+\.\d+)\s*分', text)
        if rating_match:
            shop["rating"] = rating_match.group(1)

        # 提取分类和商圈（实际格式：重庆火锅 | 湖滨商圈）
        # raw_text 中有独立 "|" 行，不能用跨行正则；逐行查找含内联 " | " 的行
        for line in text.split('\n'):
            parts = line.split(' | ')
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                shop["category"] = parts[0].strip()
                shop["area"] = parts[1].strip()
                break

        # 如果没有 name 但有文本，取第一行作为名称
        if not shop["name"] and text:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if lines:
                shop["name"] = lines[0]

        # 只返回有名称的结果
        if not shop["name"]:
            return None

        # 把原始文本也带上，方便调试
        shop["raw_text"] = text.strip()

        return shop

    def _go_next_page(self) -> bool:
        """
        点击下一页

        Returns:
            是否成功翻页
        """
        page = self.client.page

        try:
            # 大众点评分页按钮
            next_btn = page.locator('a.next, .page-next, a:has-text("下一页")')
            if next_btn.count() > 0 and next_btn.first.is_visible():
                next_btn.first.click()
                time.sleep(2)
                # 等待页面加载
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                return True
        except Exception as e:
            print(f"翻页失败: {e}", file=sys.stderr)

        return False

    def search(
        self,
        keyword: str,
        city: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        搜索大众点评商户

        Args:
            keyword: 搜索关键词
            city: 城市名（必填）
            limit: 返回数量限制

        Returns:
            搜索结果列表
        """
        # 切换城市
        city_id = self._switch_city(city)

        # 导航到搜索页
        search_url = self._make_search_url(keyword, city_id)
        print(f"搜索: {search_url}", file=sys.stderr)
        self.client.navigate(search_url)
        time.sleep(2)

        # 空结果页检测
        if self._check_empty_results():
            print("搜索结果为空：页面显示无相关商户", file=sys.stderr)
            return []

        # 滚动页面触发加载
        for _ in range(3):
            self.client.scroll_to_bottom(500)

        all_results = []
        max_pages = 10  # 防止无限翻页

        for page_num in range(max_pages):
            # 提取当前页结果
            page_results = self._extract_results()
            print(f"第 {page_num + 1} 页: 提取到 {len(page_results)} 个商户", file=sys.stderr)

            all_results.extend(page_results)

            # 达到限制
            if len(all_results) >= limit:
                break

            # 翻页
            if not self._go_next_page():
                print("没有更多页了", file=sys.stderr)
                break

            # 翻页后滚动
            for _ in range(2):
                self.client.scroll_to_bottom(500)

        # 截取到 limit
        return all_results[:limit]


# ====== 顶层便捷函数 ======

def search(
    keyword: str,
    city: str,
    limit: int = 20,
    headless: bool = True,
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> List[Dict[str, Any]]:
    """
    搜索大众点评商户

    Args:
        keyword: 搜索关键词
        city: 城市名（必填）
        limit: 返回数量限制
        headless: 是否无头模式
        cookie_path: Cookie 路径

    Returns:
        搜索结果列表
    """
    client = DianpingClient(
        headless=headless,
        cookie_path=cookie_path,
    )

    try:
        client.start()
        action = SearchAction(client)
        return action.search(
            keyword=keyword,
            city=city,
            limit=limit,
        )
    finally:
        client.close()
