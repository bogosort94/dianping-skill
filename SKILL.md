---
name: dianping-skill
description: 当用户想要查询大众点评（dianping）上的餐厅、美食、商户信息时使用此 Skill。包括搜索商户、获取商户详情、二维码扫码登录等。当用户提到大众点评、dianping、找餐厅、美食推荐、人均价格、点评评分等关键词时激活此 Skill。
user-invokable: true
---

# 大众点评 Skill

基于 Python Playwright 的大众点评自动化查询工具，通过浏览器自动化从搜索结果页提取结构化商户数据。

## 前置条件

在 `{baseDir}` 目录下安装依赖：

```bash
cd {baseDir}
pip install -r requirements.txt
playwright install chromium
```

## 快速开始

所有命令从 `{baseDir}` 目录运行。

### 1. 登录（首次必须）

```bash
cd {baseDir}

# 打开浏览器窗口，用大众点评 APP 扫码登录
python3 -m scripts qrcode

# 检查登录是否有效
python3 -m scripts check-login
```

登录后 Cookie 保存在 `~/.dianping/cookies.json`，有效期约 7 天。

### 2. 搜索

> **注意：`--city` 为必填参数，值为中文城市名（如 `杭州`、`昆明`、`大理`），不是数字 ID。** 如果用户未指定城市，请先询问用户想在哪个城市搜索。

```bash
cd {baseDir}

# 基础搜索（城市必填）
python3 -m scripts search "火锅" --city=杭州

# 指定数量
python3 -m scripts search "日料" --city=上海 --limit=10

# 大数量（自动翻页）
python3 -m scripts search "咖啡" --city=成都 --limit=30
```

**支持的城市（部分）**：北京、上海、杭州、广州、深圳、成都、武汉、南京、重庆、天津、西安、长沙、苏州、厦门、昆明、大理、丽江、三亚、青岛等。不在列表中的城市会自动从大众点评动态解析。

### 3. 商户详情

```bash
cd {baseDir}

# 使用搜索结果中的 shop_id
python3 -m scripts shop <shop_id>
```

## 反爬保护

本 Skill 内置了针对大众点评反机器人策略的保护措施：

- **UA 伪装**：自动设置 `--disable-blink-features=AutomationControlled` 并使用正常 User-Agent（大众点评会拦截 HeadlessChrome UA）
- **频率控制**：两次导航间自动延迟 3-6 秒，每 5 次连续请求后冷却 10 秒
- **验证码检测**：自动检测安全验证页面，触发时抛出 `CaptchaError` 并给出处理建议

**触发验证码时的处理：**
1. 等待几分钟后重试
2. 运行 `cd {baseDir} && python3 -m scripts qrcode` 手动过验证
3. 如 Cookie 失效，重新扫码登录

## 输出格式

所有命令输出 JSON 到标准输出。搜索结果示例：
```json
{
  "count": 5,
  "results": [
    {
      "name": "海底捞火锅(湖滨银泰店)",
      "shop_id": "H1234567",
      "avg_price": 144,
      "review_count": 13867,
      "rating": "4.5",
      "raw_text": "..."
    }
  ]
}
```

## 文件结构

```
{baseDir}/
├── SKILL.md              # 本文件（Skill 规范）
├── requirements.txt      # Python 依赖
└── scripts/              # 核心模块
    ├── __init__.py
    ├── __main__.py       # CLI 入口
    ├── client.py         # 浏览器客户端封装（频率控制 + 验证码检测）
    ├── login.py          # 扫码登录流程
    ├── search.py         # 搜索（含城市切换 + 自动翻页）
    └── shop.py           # 商户详情提取
```

## 注意事项

1. **城市必填**：搜索时必须指定 `--city`，值为**中文城市名**（如 `杭州`），不是数字 ID。如果用户未提供，请先询问
2. **Cookie 过期**：Cookie 有效期约 7 天，`check-login` 返回 false 时需重新登录
3. **城市自动切换**：搜索前会自动访问目标城市首页更新 Cookie，无需用户手动处理
4. **频率限制**：过度抓取会触发验证码，请依赖内置的频率控制
5. **字体混淆**：搜索结果页数字为纯文本；商户详情页可能存在字体混淆（待验证）
6. **Cookie 安全**：Cookie 明文存储在 `~/.dianping/cookies.json`，建议 `chmod 600` 保护
7. **仅供学习**：请遵守大众点评的使用条款，本工具仅用于学习研究

## 常见问题

| 现象 | 原因 | 解决方案 |
|------|------|----------|
| 搜索返回空结果 + warning | 城市/关键词不匹配，或该城市无相关商户 | 确认城市名正确，换个关键词试试 |
| `LoginRequiredError` | Cookie 失效或从未登录 | 运行 `python3 -m scripts qrcode` 重新扫码 |
| `CaptchaError` | 触发反爬验证码 | 等几分钟后重试，或用 `--headless=false` 手动过验证 |
| `警告: Cookie cy=X，目标城市 ID=Y` | 城市切换可能未生效 | 通常不影响结果（URL 中已含正确城市 ID），如结果异常则重新登录 |
