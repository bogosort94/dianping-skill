# Dianping Skill (大众点评自动化工具)

这是一个基于 Python Playwright 的大众点评（Dianping）自动化查询工具。它模拟浏览器行为，支持商户搜索、详情提取、以及扫码登录功能，并内置了自动城市 ID 解析和防爬频率控制。

## 主要功能

- 🔍 **商户搜索**: 支持通过中文城市名进行全城搜索，自动处理翻页。
- 🏢 **商户详情**: 提取商户的基本信息、评分、人均消费等。
- 🏙️ **动态城市解析**: 输入中文城市名，自动解析对应的大众点评城市 ID。
- 🔑 **扫码登录**: 提供有头浏览器模式，支持使用大众点评 APP 扫码登录并持久化 Cookie。
- 🛡️ **反爬机制**: 内置随机频率控制、User-Agent 伪装以及验证码检测。

## 安装步骤

### 1. 克隆项目
```bash
git clone https://github.com/bogosort94/dianping-skill.git
cd dianping-skill
```

### 2. 安装依赖
建议在虚拟环境中运行：
```bash
pip install -r requirements.txt
playwright install chromium
```

## 使用说明

所有操作通过 `scripts` 模块运行。

### 1. 登录 (首次运行或 Cookie 过期)
运行以下命令会打开一个可见的浏览器窗口，请使用大众点评 APP 扫码。
```bash
python3 -m scripts qrcode
```
登录后的 Cookie 会保存在本地 `~/.dianping/cookies.json`。

### 2. 搜索商户
**注意**: `--city` 必须提供中文城市名。
```bash
# 基础搜索
python3 -m scripts search "火锅" --city "杭州"

# 指定返回数量
python3 -m scripts search "咖啡" --city "上海" --limit 10
```

### 3. 获取商户详情
```bash
python3 -m scripts shop <shop_id>
```

## 注意事项

- **仅供学习**: 本项目仅用于技术研究和学习，请勿用于大规模抓取或非法用途。
- **频率控制**: 脚本内置了模拟人类行为的冷却时间。频繁请求可能会触发验证码或封禁。
- **Cookie 安全**: Cookie 以 JSON 格式存储在用户家目录，请注意保护隐私。

## 鸣谢

本项目在架构设计上参考了 [xiaohongshu-skill](https://clawhub.ai/deliciousbuding/xiaohongshu-skill)，感谢原作者提供的灵感与基础架构。

## 许可证
MIT License

