import copy
import yaml
import datetime
import re
import os
from typing import List, Dict, Any
from core.parser import Node
from utils.regions import REGIONS_DB, match_region
from utils.common import b64encodes
from utils.logger import logger

REGION_NAMES = {
    code: f"{info['emoji']} {info['name']}"
    for code, info in REGIONS_DB.items()
}

class Generator:
    def __init__(self, template_path: str):
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = yaml.safe_load(f) or {}

    def generate(self, nodes: List[Node], output_path: str, source_count: int = 0, raw_count: int = 0, elapsed_time: float = 0):
        config = copy.deepcopy(self.template)
        clash_proxies = [node.to_clash() for node in nodes]
        
        config['proxies'] = clash_proxies
        
        # 1. 直接读取 processor 持久化的 _region 属性 (零重复计算)
        node_to_region = {}
        region_counts = {key: 0 for key in REGIONS_DB}

        node_names = [node.name for node in nodes]
        for node in nodes:
            name = node.name
            matched_key = node.data.get('_region') or match_region(name)
            if matched_key and matched_key in REGIONS_DB:
                node_to_region[name] = matched_key
                region_counts[matched_key] += 1
            else:
                node_to_region[name] = 'OTHERS'

        # 2. Filter Active Regions (只要节点数 > 0 即可独立建组)
        active_keys = [
            k for k, count in region_counts.items() 
            if count > 0
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
        # 3. 质量评分函数 (实测带宽 > speednode > hy2 > 普通)
        name_to_node = {node.name: node for node in nodes}

        def get_node_quality_score(name: str) -> float:
            score = 10.0
            m_mb = re.search(r'(\d+\.?\d*)\s*mb/s', name.lower())
            if m_mb:
                try:
                    score = 100.0 + float(m_mb.group(1))
                except (ValueError, TypeError):
                    score = 100.0
            elif re.search(r'(\d+\.?\d*)\s*kb/s', name.lower()):
                score = 95.0
            elif 'speednode' in name.lower():
                score = 90.0
            else:
                node_obj = name_to_node.get(name)
                if node_obj and getattr(node_obj, 'type', '') in ('hysteria2', 'hy2'):
                    score = 80.0
                elif 'hy2' in name.lower() or 'hysteria' in name.lower():
                    score = 80.0
            return score

        # 4. Create Dynamic Region Groups (地区内自动选择同样采用 fallback 故障转移模式，并按质量排序)
        dynamic_groups = []
        region_list_for_menu = []
        
        test_url = "http://cp.cloudflare.com/generate_204"
        test_interval = 60
        test_timeout = 2000

        for key in active_keys:
            group_name = REGION_NAMES[key]
            auto_name = f"⚡ 自动选择 | {group_name}"
            raw_region_nodes = [n for n in region_nodes[key] if n != group_name and n != auto_name]
            nodes_in_region = sorted(raw_region_nodes, key=get_node_quality_score, reverse=True)
            fallback_proxies = nodes_in_region if nodes_in_region else ['DIRECT']
            dynamic_groups.append({
                'name': auto_name, 'type': 'fallback', 'url': test_url,
                'interval': test_interval, 'timeout': test_timeout,
                'lazy': False, 'hidden': True, 'proxies': fallback_proxies
            })
            dynamic_groups.append({
                'name': group_name, 'type': 'select',
                'proxies': ([auto_name] + nodes_in_region) if nodes_in_region else ['DIRECT']
            })
            region_list_for_menu.append(group_name)

        if others:
            others_group_name = '🌍 其他地区'
            others_auto_name = f"⚡ 自动选择 | {others_group_name}"
            raw_others = [n for n in others if n != others_group_name and n != others_auto_name]
            others = sorted(raw_others, key=get_node_quality_score, reverse=True)
            others_fallback_proxies = others if others else ['DIRECT']
            dynamic_groups.append({
                'name': others_auto_name, 'type': 'fallback', 'url': test_url,
                'interval': test_interval, 'timeout': test_timeout,
                'lazy': False, 'hidden': True, 'proxies': others_fallback_proxies
            })
            dynamic_groups.append({
                'name': others_group_name, 'type': 'select',
                'proxies': ([others_auto_name] + others) if others else ['DIRECT']
            })
            region_list_for_menu.append(others_group_name)

        # 5. 构建雨露均沾智能精选池 (Smart Pool Extractor)

        def is_china_node(name: str) -> bool:
            """判断是否为中国境内节点，对 CN2-GIA / IPLC 等海外中转线路进行白名单豁免"""
            reg = node_to_region.get(name, '')
            if reg == 'CN' or name.startswith('🇨🇳'):
                upper_name = name.upper()
                if any(tag in upper_name for tag in ('CN2', 'CNIX', 'CN-TRANSIT', 'IPLC', 'BGP-CN')):
                    if any(flag in name for flag in ('🇭🇰', '🇯🇵', '🇺🇸', '🇸🇬', '🇰🇷', '🇩🇪', '🇬🇧', 'HK', 'JP', 'US', 'SG', 'TW')):
                        return False
                return True
            elif '中国' in name:
                # 若明确识别为海外地区（如 HK, JP, US 等），说明是海外节点的运营商优化线路，不判定为国内
                if reg in REGIONS_DB and reg != 'CN':
                    return False
                return True
            return False

        MAX_PER_REGION = 6
        smart_pool_nodes = []

        for key in active_keys:
            if key == 'CN': continue  # 排除纯国内组
            candidates = [n for n in region_nodes[key] if not is_china_node(n)]
            if not candidates: continue
            candidates_sorted = sorted(candidates, key=get_node_quality_score, reverse=True)
            smart_pool_nodes.extend(candidates_sorted[:MAX_PER_REGION])

        if others:
            other_candidates = [n for n in others if not is_china_node(n)]
            if other_candidates:
                other_sorted = sorted(other_candidates, key=get_node_quality_score, reverse=True)
                smart_pool_nodes.extend(other_sorted[:MAX_PER_REGION])

        # 兜底保障：若精选节点数少于 20 个，从全量非 CN 节点中按分数补充至 30 个
        oversea_nodes = [n for n in node_names if not is_china_node(n)]
        if len(smart_pool_nodes) < 20 and oversea_nodes:
            fallback_sorted = sorted(oversea_nodes, key=get_node_quality_score, reverse=True)
            for fn in fallback_sorted:
                if fn not in smart_pool_nodes:
                    smart_pool_nodes.append(fn)
                if len(smart_pool_nodes) >= 30:
                    break

        if not smart_pool_nodes:
            smart_pool_nodes = oversea_nodes if oversea_nodes else node_names

        # 5. Fill Template Groups
        template_groups = config.get('proxy-groups', [])
        for g in template_groups:
            if g['name'] == '🗺️ 选择地区':
                g['proxies'] = region_list_for_menu if region_list_for_menu else ['DIRECT']
            elif g['name'] in ('♻️ 自动选择', '🔰 延迟最低'):
                g['proxies'] = smart_pool_nodes if smart_pool_nodes else ['DIRECT']
            elif g['name'] == '✅ 手动选择':
                g['proxies'] = node_names if node_names else ['DIRECT']
        
        config['proxy-groups'] = template_groups + dynamic_groups

        # 6. Save YAML (Clash Meta)
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Generated by MetaFetch\n# Updated at: {now_str}\n")
            yaml_content = yaml.safe_dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
            yaml_content = re.sub(r'short-id:\s*([^\s"\']+)', r'short-id: "\1"', yaml_content)
            yaml_content = re.sub(r'public-key:\s*([^\s"\']+)', r'public-key: "\1"', yaml_content)
            f.write(yaml_content)
        
        # 7. Save Universal Links (Base64 & Plain TXT)
        node_urls = [node.to_url() for node in nodes if node.to_url()]
        raw_urls_str = "\n".join(node_urls)
        
        txt_path = "list.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(raw_urls_str)
            
        b64_path = "list.b64"
        with open(b64_path, 'w', encoding='utf-8') as f:
            f.write(b64encodes(raw_urls_str))

        self.update_readme(len(nodes), region_nodes, others, now_str, source_count, raw_count, elapsed_time)
        self.generate_tg_summary(len(nodes), region_nodes, others, now_str, source_count, raw_count, elapsed_time)
        logger.info(f"Successfully generated {len(nodes)} nodes across formats ({output_path}, {b64_path}, {txt_path})")

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

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

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
            f"• <b>Shadowrocket / Base64:</b>\n<code>https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.b64</code>\n\n"
            f"⭐ <b>GitHub 仓库：</b> <a href=\"https://github.com/lanzm/MetaFetch\">lanzm/MetaFetch</a>"
        )
        
        with open("tg_summary.txt", "w", encoding="utf-8") as f:
            f.write(message)
