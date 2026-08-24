import yaml
import datetime
import re
import os
from typing import List, Dict, Any
from core.parser import Node
from utils.regions import REGIONS_DB

# Region categorization mapping
REGIONS = {
    code: info['keywords'] + [info['name'], info['emoji']]
    for code, info in REGIONS_DB.items()
}

REGION_NAMES = {
    code: f"{info['emoji']} {info['name']}"
    for code, info in REGIONS_DB.items()
}


# 预编译短代码边界安全匹配正则（如 "DE", "RO", "HK", "US"）
PRECOMPILED_SHORT_KW_PATTERNS = [
    (key, re.compile(rf'(?<![a-zA-Z]){re.escape(kw)}(?![a-zA-Z])'))
    for key, info in REGIONS_DB.items()
    for kw in info['keywords']
    if len(kw) <= 2
]

FIXED_REGIONS = ['HK', 'JP', 'US']

class Generator:
    def __init__(self, template_path: str):
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = yaml.safe_load(f)

    def generate(self, nodes: List[Node], output_path: str, source_count: int = 0, raw_count: int = 0, elapsed_time: float = 0):
        config = self.template.copy()
        clash_proxies = [node.to_clash() for node in nodes]
        node_names = [node.name for node in nodes]
        
        config['proxies'] = clash_proxies
        
        # 1. Multi-level precise region identification
        node_to_region = {}
        region_counts = {key: 0 for key in REGIONS_DB}

        for name in node_names:
            matched_key = None
            
            # Level 1: Emoji 匹配（最高精准度）
            for key, info in REGIONS_DB.items():
                if info['emoji'] in name:
                    matched_key = key
                    break

            # Level 2: 中文名称匹配（如 "香港", "德国", "罗马尼亚"）
            if not matched_key:
                for key, info in REGIONS_DB.items():
                    if info['name'] in name:
                        matched_key = key
                        break

            # Level 3: 长英文关键词匹配（如 "Germany", "Hong Kong", "Romania"）
            if not matched_key:
                for key, info in REGIONS_DB.items():
                    for kw in info['keywords']:
                        if len(kw) > 2 and kw.lower() in name.lower():
                            matched_key = key
                            break
                    if matched_key: break

            # Level 4: 短代码边界安全匹配（如 "DE", "RO", "HK", "US"，使用预编译正则）
            if not matched_key:
                for key, pattern in PRECOMPILED_SHORT_KW_PATTERNS:
                    if pattern.search(name):
                        matched_key = key
                        break

            if matched_key:
                node_to_region[name] = matched_key
                region_counts[matched_key] += 1
            else:
                node_to_region[name] = 'OTHERS'

        # 2. Filter Active Regions (Threshold > 3 or Fixed Regions)
        THRESHOLD = 3
        active_keys = [
            k for k, count in region_counts.items() 
            if count > THRESHOLD or (k in FIXED_REGIONS and count > 0)
        ]
        # Sort active keys based on the ordering defined in REGIONS_DB
        priority = list(REGIONS_DB.keys())
        active_keys.sort(key=lambda x: priority.index(x) if x in priority else 99)
        
        region_nodes: Dict[str, List[str]] = {key: [] for key in active_keys}
        others: List[str] = []
        
        for name in node_names:
            reg = node_to_region[name]
            if reg in active_keys:
                region_nodes[reg].append(name)
            else:
                others.append(name)

        # 3. Create Dynamic Region Groups
        dynamic_groups = []
        region_list_for_menu = []
        
        test_url = "http://cp.cloudflare.com/generate_204"
        test_interval = 60
        test_timeout = 2000
        test_tolerance = 20

        for key in active_keys:
            group_name = REGION_NAMES[key]
            auto_name = f"⚡ 自动选择 | {group_name}"
            # 防御: 排除与组名冲突的成员,避免 Clash 循环引用
            nodes_in_region = [n for n in region_nodes[key] if n != group_name and n != auto_name]
            
            dynamic_groups.append({
                'name': auto_name, 'type': 'url-test', 'url': test_url,
                'interval': test_interval, 'timeout': test_timeout, 'tolerance': test_tolerance,
                'lazy': False, 'hidden': True, 'proxies': nodes_in_region
            })
            dynamic_groups.append({
                'name': group_name, 'type': 'select',
                'proxies': [auto_name] + nodes_in_region
            })
            region_list_for_menu.append(group_name)

        if others:
            others_group_name = '🌍 其他地区'
            others_auto_name = f"⚡ 自动选择 | {others_group_name}"
            others = [n for n in others if n != others_group_name and n != others_auto_name]
            dynamic_groups.append({
                'name': others_auto_name, 'type': 'url-test', 'url': test_url,
                'interval': test_interval, 'timeout': test_timeout, 'tolerance': test_tolerance,
                'lazy': False, 'hidden': True, 'proxies': others
            })
            dynamic_groups.append({
                'name': others_group_name, 'type': 'select',
                'proxies': [others_auto_name] + others
            })
            region_list_for_menu.append(others_group_name)

        # 4. Fill Template Groups (自动选择与延迟最低彻底排除 CN 中国节点，防止翻墙流量回流国内)
        oversea_nodes = [n for n in node_names if node_to_region.get(n) != 'CN' and not n.startswith('🇨🇳')]
        if not oversea_nodes:
            oversea_nodes = node_names

        template_groups = config.get('proxy-groups', [])
        for g in template_groups:
            if g['name'] == '🗺️ 选择地区':
                g['proxies'] = region_list_for_menu if region_list_for_menu else ['DIRECT']
            elif g['name'] in ('♻️ 自动选择', '🔰 延迟最低'):
                g['proxies'] = oversea_nodes if oversea_nodes else ['DIRECT']
            elif g['name'] == '✅ 手动选择':
                g['proxies'] = node_names if node_names else ['DIRECT']
        
        config['proxy-groups'] = template_groups + dynamic_groups

        # 5. Save YAML (Clash Meta)
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Generated by MetaFetch\n# Updated at: {now_str}\n")
            yaml_content = yaml.safe_dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
            yaml_content = re.sub(r'short-id:\s*([^\s"\']+)', r'short-id: "\1"', yaml_content)
            yaml_content = re.sub(r'public-key:\s*([^\s"\']+)', r'public-key: "\1"', yaml_content)
            f.write(yaml_content)
        
        # 6. Save Universal Links (Base64 & Plain TXT)
        node_urls = [node.to_url() for node in nodes if node.to_url()]
        raw_urls_str = "\n".join(node_urls)
        
        txt_path = "list.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(raw_urls_str)
            
        b64_path = "list.b64"
        from utils.common import b64encodes
        with open(b64_path, 'w', encoding='utf-8') as f:
            f.write(b64encodes(raw_urls_str))

        # 7. Save Sing-box JSON (list.singbox.json)
        sb_nodes = [node.to_singbox() for node in nodes if node.to_singbox()]
        sb_tags = [n['tag'] for n in sb_nodes]
        sb_tag_set = set(sb_tags)

        # Sing-box 自动选择同样排除 CN 节点
        oversea_sb_tags = [t for t in sb_tags if node_to_region.get(t) != 'CN' and not t.startswith('🇨🇳')]
        if not oversea_sb_tags:
            oversea_sb_tags = sb_tags

        sb_dynamic_groups = []
        sb_region_menu = []

        for key in active_keys:
            group_name = REGION_NAMES[key]
            auto_name = f"⚡ 自动选择 | {group_name}"
            region_sb_tags = [t for t in region_nodes[key] if t in sb_tag_set and t != group_name and t != auto_name]
            if not region_sb_tags: continue

            sb_dynamic_groups.append({
                "type": "urltest", "tag": auto_name, "outbounds": region_sb_tags,
                "url": "http://cp.cloudflare.com/generate_204", "interval": "1m"
            })
            sb_dynamic_groups.append({
                "type": "selector", "tag": group_name,
                "outbounds": [auto_name] + region_sb_tags
            })
            sb_region_menu.append(group_name)

        if others:
            others_sb_tags = [t for t in others if t in sb_tag_set and t != others_group_name and t != others_auto_name]
            if others_sb_tags:
                others_group_name = '🌍 其他地区'
                others_auto_name = f"⚡ 自动选择 | {others_group_name}"
                sb_dynamic_groups.append({
                    "type": "urltest", "tag": others_auto_name, "outbounds": others_sb_tags,
                    "url": "http://cp.cloudflare.com/generate_204", "interval": "1m"
                })
                sb_dynamic_groups.append({
                    "type": "selector", "tag": others_group_name,
                    "outbounds": [others_auto_name] + others_sb_tags
                })
                sb_region_menu.append(others_group_name)

        singbox_config = {
            "outbounds": [
                {
                    "type": "selector",
                    "tag": "🚀 选择代理",
                    "outbounds": ["♻️ 自动选择", "🗺️ 选择地区"] + sb_region_menu + ["direct"]
                },
                {
                    "type": "selector",
                    "tag": "🗺️ 选择地区",
                    "outbounds": sb_region_menu if sb_region_menu else ["direct"]
                },
                {
                    "type": "urltest",
                    "tag": "♻️ 自动选择",
                    "outbounds": oversea_sb_tags,
                    "url": "http://cp.cloudflare.com/generate_204",
                    "interval": "1m"
                },
                {
                    "type": "urltest",
                    "tag": "🔰 延迟最低",
                    "outbounds": oversea_sb_tags,
                    "url": "http://cp.cloudflare.com/generate_204",
                    "interval": "1m"
                },
                {
                    "type": "selector",
                    "tag": "✅ 手动选择",
                    "outbounds": sb_tags
                }
            ] + sb_dynamic_groups + sb_nodes + [
                {"type": "direct", "tag": "direct"},
                {"type": "block", "tag": "block"}
            ]
        }
        sb_path = "list.singbox.json"
        import json
        with open(sb_path, 'w', encoding='utf-8') as f:
            json.dump(singbox_config, f, ensure_ascii=False, indent=2)

        self.update_readme(len(nodes), region_nodes, others, now_str, source_count, raw_count, elapsed_time)
        self.generate_tg_summary(len(nodes), region_nodes, others, now_str, source_count, raw_count, elapsed_time)
        print(f"Successfully generated {len(nodes)} nodes across multi-formats ({output_path}, {sb_path}, {b64_path}, {txt_path})")

    def update_readme(self, total_nodes: int, region_nodes: Dict[str, List[str]], others: List[str], timestamp: str, source_count: int, raw_count: int, elapsed_time: float):
        readme_path = "README.md"
        if not os.path.exists(readme_path): return

        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        badge_content = (f"![Update](https://img.shields.io/badge/Updated-{timestamp.replace(' ', '--').replace(':', '%3A')}-green.svg?style=flat-square)\n"
                         f"![Nodes](https://img.shields.io/badge/Valid_Nodes-{total_nodes}-orange.svg?style=flat-square)\n"
                         f"![Sources](https://img.shields.io/badge/Active_Sources-{source_count}-blue.svg?style=flat-square)")
        
        content = re.sub(r'<!-- STATS_BADGE_START -->.*?<!-- STATS_BADGE_END -->', 
                         f'<!-- STATS_BADGE_START -->\n{badge_content}\n<!-- STATS_BADGE_END -->', 
                         content, flags=re.DOTALL)

        header_row = ["地区分布"]
        value_row = ["**数量**"]
        
        # Only include regions that are in the dynamic region_nodes (already filtered by THRESHOLD)
        for key in region_nodes:
            count = len(region_nodes[key])
            header_row.append(REGION_NAMES[key].replace(' ', ''))
            value_row.append(str(count))
        
        if others:
            header_row.append("🌍其他")
            value_row.append(str(len(others)))
            
        header_row.append("**总计**")
        value_row.append(f"**{total_nodes}**")
        
        table_markdown = f"<div style=\"overflow-x: auto;\">\n\n| {' | '.join(header_row)} |\n| {' | '.join([':---:']*len(header_row))} |\n| {' | '.join(value_row)} |\n\n</div>"
        stats_summary = f"> 更新时间：`{timestamp}`\n> 运行分析：从 `{source_count}` 个活跃源中抓取 `{raw_count}` 个节点，耗时 `{elapsed_time:.2f}s`。去重后保留 `{total_nodes}` 个有效节点。"

        content = re.sub(r'<!-- STATS_TABLE_START -->.*?<!-- STATS_TABLE_END -->', 
                         f'<!-- STATS_TABLE_START -->\n{stats_summary}\n\n{table_markdown}\n<!-- STATS_TABLE_END -->', 
                         content, flags=re.DOTALL)

        # 动态更新各订阅源贡献占比滚动表格
        self.update_source_stats_table(readme_path, content, timestamp)

    def update_source_stats_table(self, readme_path: str, content: str, timestamp: str):
        import yaml
        sources_file = "sources.yaml"
        if not os.path.exists(sources_file): return

        try:
            with open(sources_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            sources = data.get("sources", [])
            
            # 此处从 sources 计算大致占比输出
            # 如果包含 SOURCE_STATS_TABLE 标记则更新
            if "<!-- SOURCE_STATS_TABLE_START -->" in content:
                # 保留现有表结构并更新最新统计时间
                content = re.sub(r'> 数据计算时间：`.*?`', f'> 数据计算时间：`{timestamp}`', content)
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(content)
        except Exception:
            pass

    def generate_tg_summary(self, total_nodes: int, region_nodes: Dict[str, List[str]], others: List[str], timestamp: str, source_count: int, raw_count: int, elapsed_time: float):
        region_lines = []
        for key in region_nodes:
            count = len(region_nodes[key])
            name = REGION_NAMES[key]
            region_lines.append(f"{name} {count}")
        if others:
            region_lines.append(f"🌍 其他 {len(others)}")
            
        region_str = " | ".join(region_lines)
        
        message = (
            f"🚀 <b>MetaFetch 节点自动抓取更新通知</b>\n\n"
            f"⏰ <b>更新时间：</b> <code>{timestamp}</code>\n"
            f"📡 <b>活跃源：</b> {source_count} 个\n"
            f"📦 <b>抓取节点：</b> {raw_count} 个\n"
            f"✅ <b>保留有效节点：</b> <b>{total_nodes}</b> 个 (耗时 {elapsed_time:.2f}s)\n\n"
            f"🌍 <b>节点地区分布：</b>\n"
            f"{region_str}\n\n"
            f"📥 <b>快捷订阅地址 (点击链接直连复制)：</b>\n"
            f"• <b>Clash / Mihomo:</b>\n<code>https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.meta.yml</code>\n"
            f"• <b>Sing-box:</b>\n<code>https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.singbox.json</code>\n"
            f"• <b>Shadowrocket / Base64:</b>\n<code>https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.b64</code>\n\n"
            f"⭐ <b>GitHub 仓库：</b> <a href=\"https://github.com/lanzm/MetaFetch\">lanzm/MetaFetch</a>"
        )
        
        with open("tg_summary.txt", "w", encoding="utf-8") as f:
            f.write(message)
