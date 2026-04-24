import yaml
import datetime
import re
import os
from typing import List, Dict, Any
from core.parser import Node

# Region categorization mapping
REGIONS = {
    'HK': ['香港', 'HK', 'Hong Kong', '🇭🇰'],
    'TW': ['台湾', 'TW', 'Taiwan', '🇹🇼'],
    'JP': ['日本', 'JP', 'Japan', '🇯🇵'],
    'US': ['美国', 'US', 'United States', '🇺🇸'],
    'SG': ['新加坡', 'SG', 'Singapore', '🇸🇬'],
    'KR': ['韩国', 'KR', 'Korea', '🇰🇷'],
    'DE': ['德国', 'DE', 'Germany', '🇩🇪'],
    'GB': ['英国', 'GB', 'UK', 'United Kingdom', '🇬🇧'],
    'FR': ['法国', 'FR', 'France', '🇫🇷'],
    'RU': ['俄罗斯', 'RU', 'Russia', '🇷🇺'],
    'CA': ['加拿大', 'CA', 'Canada', '🇨🇦'],
    'VN': ['越南', 'VN', 'Vietnam', '🇻🇳'],
    'NL': ['荷兰', 'NL', 'Netherlands', '🇳🇱'],
    'CH': ['瑞士', 'CH', 'Switzerland', '🇨🇭'],
    'IN': ['印度', 'IN', 'India', '🇮🇳'],
    'TR': ['土耳其', 'TR', 'Turkey', '🇹🇷'],
    'AU': ['澳大利亚', 'AU', 'Australia', '🇦🇺'],
    'TH': ['泰国', 'TH', 'Thailand', '🇹🇭'],
    'PH': ['菲律宾', 'PH', 'Philippines', '🇵🇭'],
    'MY': ['马来西亚', 'MY', 'Malaysia', '🇲🇾'],
    'ID': ['印尼', 'ID', 'Indonesia', '🇮🇩'],
    'BR': ['巴西', 'BR', 'Brazil', '🇧🇷'],
    'AR': ['阿根廷', 'AR', 'Argentina', '🇦🇷'],
    'MX': ['墨西哥', 'MX', 'Mexico', '🇲🇽'],
    'IT': ['意大利', 'IT', 'Italy', '🇮🇹'],
    'ES': ['西班牙', 'ES', 'Spain', '🇪🇸'],
}

REGION_NAMES = {
    'HK': '🇭🇰 香港', 'TW': '🇹🇼 台湾', 'JP': '🇯🇵 日本', 'US': '🇺🇸 美国',
    'SG': '🇸🇬 新加坡', 'KR': '🇰🇷 韩国', 'DE': '🇩🇪 德国', 'GB': '🇬🇧 英国',
    'FR': '🇫🇷 法国', 'RU': '🇷🇺 俄罗斯', 'CA': '🇨🇦 加拿大', 'VN': '🇻🇳 越南',
    'NL': '🇳🇱 荷兰', 'CH': '🇨🇭 瑞士', 'IN': '🇮🇳 印度', 'TR': '🇹🇷 土耳其',
    'AU': '🇦🇺 澳大利亚', 'TH': '🇹🇭 泰国', 'PH': '🇵🇭 菲律宾', 'MY': '🇲🇾 马来西亚',
    'ID': '🇮🇩 印尼', 'BR': '🇧🇷 巴西', 'AR': '🇦🇷 阿根廷', 'MX': '🇲🇽 墨西哥',
    'IT': '🇮🇹 意大利', 'ES': '🇪🇸 西班牙',
}

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
        
        # 1. Identify region for each node
        node_to_region = {}
        region_counts = {key: 0 for key in REGIONS}
        
        for name in node_names:
            found = False
            for key, keywords in REGIONS.items():
                for kw in keywords:
                    if kw in name or kw.lower() in name.lower():
                        node_to_region[name] = key
                        region_counts[key] += 1
                        found = True
                        break
                if found: break
            if not found:
                node_to_region[name] = 'OTHERS'

        # 2. Filter Active Regions (Threshold > 3 or Fixed Regions)
        THRESHOLD = 3
        active_keys = [
            k for k, count in region_counts.items() 
            if count > THRESHOLD or (k in FIXED_REGIONS and count > 0)
        ]
        # Sort active keys to keep a consistent order (HK, JP, US usually first)
        priority = ['HK', 'TW', 'JP', 'US', 'SG', 'KR']
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
        
        test_url = "http://www.google.com/generate_204"
        test_interval = 300
        test_tolerance = 20

        for key in active_keys:
            nodes_in_region = region_nodes[key]
            group_name = REGION_NAMES[key]
            auto_name = f"⚡ 自动选择 | {group_name}"
            
            dynamic_groups.append({
                'name': auto_name, 'type': 'url-test', 'url': test_url,
                'interval': test_interval, 'tolerance': test_tolerance,
                'hidden': True, 'proxies': nodes_in_region
            })
            dynamic_groups.append({
                'name': group_name, 'type': 'select',
                'proxies': [auto_name] + nodes_in_region
            })
            region_list_for_menu.append(group_name)

        if others:
            others_group_name = '🌍 其他地区'
            others_auto_name = f"⚡ 自动选择 | {others_group_name}"
            dynamic_groups.append({
                'name': others_auto_name, 'type': 'url-test', 'url': test_url,
                'interval': test_interval, 'tolerance': test_tolerance,
                'hidden': True, 'proxies': others
            })
            dynamic_groups.append({
                'name': others_group_name, 'type': 'select',
                'proxies': [others_auto_name] + others
            })
            region_list_for_menu.append(others_group_name)

        # 4. Fill Template Groups
        template_groups = config.get('proxy-groups', [])
        for g in template_groups:
            if g['name'] == '🗺️ 选择地区':
                g['proxies'] = region_list_for_menu
            elif g['name'] in ('♻️ 自动选择', '🔰 延迟最低', '✅ 手动选择'):
                g['proxies'] = node_names
        
        config['proxy-groups'] = template_groups + dynamic_groups

        # 5. Save YAML
        with open(output_path, 'w', encoding='utf-8') as f:
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"# Generated by MetaFetch\n# Updated at: {now_str}\n")
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        self.update_readme(len(nodes), region_nodes, others, now_str, source_count, raw_count, elapsed_time)
        print(f"Successfully generated {len(nodes)} nodes with {len(active_keys)} active regions to {output_path}")

    def update_readme(self, total_nodes: int, region_nodes: Dict[str, List[str]], others: List[str], timestamp: str, source_count: int, raw_count: int, elapsed_time: float):
        readme_path = "README.md"
        if not os.path.exists(readme_path): return

        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        badge_content = (f"![Update](https://img.shields.io/badge/Updated-{timestamp.replace(' ', '--').replace(':', '%3A')}-green.svg)\n"
                         f"![Nodes](https://img.shields.io/badge/Valid_Nodes-{total_nodes}-orange.svg)\n"
                         f"![Sources](https://img.shields.io/badge/Active_Sources-{source_count}-blue.svg)")
        
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
        
        table_markdown = f"| {' | '.join(header_row)} |\n| {' | '.join([':---:']*len(header_row))} |\n| {' | '.join(value_row)} |"
        stats_summary = f"> 更新时间：`{timestamp}`\n> 运行分析：从 `{source_count}` 个活跃源中抓取 `{raw_count}` 个节点，耗时 `{elapsed_time:.2f}s`。去重后保留 `{total_nodes}` 个有效节点。"

        content = re.sub(r'<!-- STATS_TABLE_START -->.*?<!-- STATS_TABLE_END -->', 
                         f'<!-- STATS_TABLE_START -->\n{stats_summary}\n\n{table_markdown}\n<!-- STATS_TABLE_END -->', 
                         content, flags=re.DOTALL)

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
