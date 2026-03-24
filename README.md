# 🚀 MetaFetch Proxy Aggregator

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg?style=flat-square)](https://www.python.org/)
<!-- STATS_BADGE_START -->
![Update](https://img.shields.io/badge/Updated-2026-03-24--15%3A43%3A46-green.svg)
![Nodes](https://img.shields.io/badge/Valid_Nodes-177-orange.svg)
![Sources](https://img.shields.io/badge/Active_Sources-16-blue.svg)
<!-- STATS_BADGE_END -->
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

MetaFetch 是一款高性能的自动化代理节点聚合工具。它能够从全球公开渠道自动抓取、清洗、分类节点，并为 Clash (Mihomo) 提供开箱即用的高级分流配置文件。

> [!IMPORTANT]
> **声明：** 本项目由 [peasoft/NoMoreWalls](https://github.com/peasoft/NoMoreWalls) 改造而来，并在此基础上进行了深度定制化开发，增强了异步抓取、YAML 配置管理与地区自动分组逻辑。

---

## 📥 订阅链接 (推荐)

建议使用 **Clash Meta / Mihomo** 客户端以获得最佳体验（支持最新协议）。

### 🛠️ Clash / Meta 订阅 (YAML)
| 线路类型 | 订阅链接 (点击复制) |
| :--- | :--- |
| **CDN 加速 (推荐)** | `https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.meta.yml` |
| **GitHub 直连** | `https://raw.githubusercontent.com/lanzm/MetaFetch/master/list.meta.yml` |

---

## ✨ 核心特性
- **⚡ 极速异步抓取**：基于 `httpx` & `asyncio` 的全异步并发抓取，抓取上百个源仅需数秒。
- **🛠️ 结构化配置**：使用简洁的 `sources.yaml` 管理订阅源。
- **🌍 智能地区分类**：自动归类 🇯🇵 日本、🇺🇸 美国、🇭🇰 香港、🇩🇪 德国等。
- **🏁 旗帜增强**：自动补全缺失 Emoji 的节点旗帜。
- **📅 每日动态源**：支持 `%Y%m%d` 日期占位符。

---

## 📊 节点分布统计

<!-- STATS_TABLE_START -->
> 更新时间：`2026-03-24 15:43:46`
> 运行分析：从 `16` 个活跃源中抓取 `375` 个节点，耗时 `0.83s`。去重后保留 `177` 个有效节点。

| 地区分布 | 香港 | 台湾 | 日本 | 美国 | 新加坡 | 韩国 | 德国 | 英国 | 法国 | 俄罗斯 | 其他 | **总计** |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **数量** | 6 | 1 | 5 | 51 | 5 | 12 | 8 | 1 | 1 | 3 | 84 | **177** |
<!-- STATS_TABLE_END -->

---

## 🚀 私有化部署与使用

如果你想添加自己的私密源或修改分流规则，可以按照以下步骤操作：

1. **环境准备**：
   > 💡 **提示：** 由于项目每天自动抓取并提交更新，包含非常多的历史 commit。强烈建议克隆时加上 `--depth=1` 以进行浅克隆，节省下载时间与空间。
   ```bash
   git clone --depth=1 <你的项目地址>
   cd MetaFetch
   pip install -r requirements.txt
   ```

2. **添加自定义源**：
   在 `sources.yaml` 中加入你的订阅链接。支持普通文本、Base64 或 Clash YAML 格式。

3. **开始运行**：
   ```bash
   python main.py
   ```

4. **成果检查**：
   生成的配置文件为 `list.meta.yml`，可直接导入 Clash Meta (Mihomo) 使用。

---

## ⚠️ 免责声明

1. 本项目及其所有代码仅供计算机网络技术学习、交流之用途。
2. 订阅内所有节点均由爬虫自动搜集，**作者无法保证节点安全性、隐私性或速度**。
3. 请勿使用本项目节点传输任何高度敏感数据（如网银、支付信息等）。
4. 使用者必须严格遵守当地法律法规。因使用本项目产生的所有法律后果由使用者本人承担。

---
感谢原项目作者 [peasoft](https://github.com/peasoft) 的杰出贡献。
*Generated & Updated Automatically by **MetaFetch Engine***
