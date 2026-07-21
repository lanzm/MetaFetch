# 🚀 MetaFetch Proxy Aggregator

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg?style=flat-square)](https://www.python.org/)
<!-- STATS_BADGE_START -->
![Update](https://img.shields.io/badge/Updated-2026-07-22--00%3A15%3A16-green.svg)
![Nodes](https://img.shields.io/badge/Valid_Nodes-228-orange.svg)
![Sources](https://img.shields.io/badge/Active_Sources-18-blue.svg)
<!-- STATS_BADGE_END -->
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

MetaFetch 是基于 Python 异步极速并发，每天抓取免费节点，生成免费订阅链接，全球地区自动识别分流的高性能全自动化代理订阅引擎。支持 Clash / Mihomo、Sing-box、Shadowrocket (小火箭) 等全平台客户端。

> [!IMPORTANT]
> **声明：** 本项目由 [peasoft/NoMoreWalls](https://github.com/peasoft/NoMoreWalls) 改造而来，并在此基础上进行了深度定制化开发，增强了异步抓取、YAML 配置管理与地区自动分组逻辑。

## 📥 订阅链接面板

支持 **Clash / Mihomo**、**Sing-box**、**Shadowrocket (小火箭)**、**V2rayN / V2rayNG**、**Quantumult X** 等全平台客户端。

### 1. 🛡️ Clash / Mihomo 专用订阅 (YAML)
| 线路类型 | 订阅地址 (复制使用) | 快捷操作 |
| :--- | :--- | :---: |
| **CDN 加速 (推荐)** | `https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.meta.yml` | [<img src="https://img.shields.io/badge/一键导入-Clash-2563eb?style=for-the-badge&logo=clash&logoColor=white" height="24" alt="Import to Clash" />](clash://install-config?url=https%3A%2F%2Ffastly.jsdelivr.net%2Fgh%2Flanzm%2FMetaFetch%40master%2Flist.meta.yml&name=MetaFetch) |
| **GitHub 直连** | `https://raw.githubusercontent.com/lanzm/MetaFetch/master/list.meta.yml` | [<img src="https://img.shields.io/badge/一键导入-Clash-475569?style=for-the-badge&logo=clash&logoColor=white" height="24" alt="Import to Clash" />](clash://install-config?url=https%3A%2F%2Fraw.githubusercontent.com%2Flanzm%2FMetaFetch%2Fmaster%2Flist.meta.yml&name=MetaFetch) |

> 💡 支持 **Clash Verge / Mihomo Party / Clash Nyanpasu / Stash / Clash for Windows** 等客户端。

### 2. ⚡ Sing-box 专用订阅 (JSON)
| 线路类型 | 订阅地址 (复制使用) | 适用客户端 |
| :--- | :--- | :--- |
| **CDN 加速 (推荐)** | `https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.singbox.json` | **Sing-box** (iOS/Android/Windows/Mac) |
| **GitHub 直连** | `https://raw.githubusercontent.com/lanzm/MetaFetch/master/list.singbox.json` | **Sing-box / Hiddify / Karing** |

### 3. 📱 通用 Base64 / 节点列表订阅 (小火箭 / V2rayN)
| 格式 | 订阅地址 (复制使用) | 快捷操作 |
| :--- | :--- | :---: |
| **Base64 订阅 (推荐)** | `https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.b64` | [<img src="https://img.shields.io/badge/一键导入-Shadowrocket-3b82f6?style=for-the-badge&logo=shadowrocket&logoColor=white" height="24" alt="Import to Shadowrocket" />](sub://aHR0cHM6Ly9mYXN0bHkuanNkZWxpdnIubmV0L2doL2xhbnptL01ldGFGZXRjaEBtYXN0ZXIvbGlzdC5iNjQ=) |
| **明文 URL 节点列表** | `https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.txt` | 复制在线节点链接 |

> 💡 适合 **Shadowrocket (小火箭)**、**V2rayN**、**V2rayNG**、**Quantumult X**、**Surfboard** 等常用代理客户端直接添加订阅。

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
> 更新时间：`2026-07-22 00:15:16`
> 运行分析：从 `18` 个活跃源中抓取 `347` 个节点，耗时 `3.15s`。去重后保留 `228` 个有效节点。

| 地区分布 | 🇭🇰香港 | 🇯🇵日本 | 🇺🇸美国 | 🇸🇬新加坡 | 🇰🇷韩国 | 🇩🇪德国 | 🇻🇳越南 | 🇳🇱荷兰 | 🇦🇷阿根廷 | 🇷🇴罗马尼亚 | 🌍其他 | **总计** |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **数量** | 9 | 14 | 24 | 8 | 4 | 59 | 6 | 52 | 10 | 4 | 38 | **228** |
<!-- STATS_TABLE_END -->

---

## 🚀 私有化部署与使用

如果你想添加自己的私密源或修改分流规则，可以按照以下步骤操作：

1. **环境准备**：
   > 💡 **提示：** 由于项目每天自动抓取并提交更新，包含非常多的历史 commit。强烈建议克隆时加上 `--depth=1` 以进行浅克隆，节省下载时间与空间。
   ```bash
   git clone --depth=1 https://github.com/lanzm/MetaFetch.git
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

1. **仅供学习与交流使用**：本项目（包括所有相关代码、脚本及文档）仅供进行计算机网络测试、学术交流及科研学习之最终目的。
2. **不对资源的安全性负责**：本项目提供的所有节点数据均系按照自动化程序爬取自互联网公开渠道。**开发者对任何节点的安全性、可用性、隐私性或网速不提供任何哪怕是默示的担保**。
3. **数据隐私风险提示**：由于节点来源不受控，强烈建议使用者**切莫**使用本项目的代理环境进行涉及网银、个人隐私、敏感信息的账户操作！否则流量可能随时遭到中间人攻击窃听或日志记录。
4. **法律与合规指引**：使用者在获取或使用本项目等内容时，必须严格遵守当地的所有适用法律法规。任何因非法滥用、或不当使用本项目工具/节点所引发的一切违法违规行为及相关法律后果，均由使用者本人自行全部承担。开发者不负任何连带责任。
5. **严禁商业用途**：项目代码属于完全免费的开源代码，作者从未授权任何个人和组织将本项目的产出或代码用于任何商业牟利行为。

---
感谢原项目作者 [peasoft](https://github.com/peasoft) 的杰出贡献。
*Generated & Updated Automatically by **MetaFetch Engine***
