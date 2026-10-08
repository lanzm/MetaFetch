import copy
import yaml
import datetime
import re
import os
from typing import List, Dict, Any
from core.parser import Node
from utils.regions import REGIONS_DB, match_region, REGION_NAMES
from utils.common import b64encodes
from utils.logger import logger

_MB_SPEED_RE = re.compile(r'(\d+\.?\d*)\s*mb/s', re.IGNORECASE)
_KB_SPEED_RE = re.compile(r'(\d+\.?\d*)\s*kb/s', re.IGNORECASE)
_YAML_SAFE_CONTROL_REGEX = re.compile(
    r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufffe\uffff]'
)


def deep_sanitize(data: Any) -> Any:
    """递归清理字典、列表或字符串中的非法控制字符与不可见字符。"""
    if isinstance(data, str):
        return _YAML_SAFE_CONTROL_REGEX.sub('', data)
    elif isinstance(data, dict):
        return {
            (_YAML_SAFE_CONTROL_REGEX.sub('', k) if isinstance(k, str) else k): deep_sanitize(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [deep_sanitize(item) for item in data]
    return data


_YAML_V3_LITERALS = {
    "true", "True", "TRUE", "false", "False", "FALSE",
    "~", "null", "Null", "NULL",
    ".nan", ".NaN", ".NAN",
    ".inf", ".Inf", ".INF",
    "+.inf", "+.Inf", "+.INF",
    "-.inf", "-.Inf", "-.INF",
    "<<",
}
_YAML_V3_FLOAT = re.compile(r"^[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?$")
_YAML_V3_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}([Tt ]+.*)?$")


def _yaml_v3_needs_quotes(s: str) -> bool:
    """判断字符串在 go-yaml v3 中是否会被误解析为非字符串。"""
    if s in _YAML_V3_LITERALS:
        return True
    if s == "":
        return False
    plain = s.replace("_", "")
    try:
        int(plain, 0)
        return True
    except ValueError:
        pass
    try:
        int(plain, 16)
        return True
    except ValueError:
        pass
    if _YAML_V3_FLOAT.match(s) or _YAML_V3_TIMESTAMP.match(s):
        return True
    return False


class SafeDumper(yaml.SafeDumper):
    pass


def _represent_str(dumper, data):
    if _yaml_v3_needs_quotes(data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return yaml.SafeDumper.represent_str(dumper, data)


SafeDumper.add_representer(str, _represent_str)


class Generator:
    def __init__(self, template_path: str):
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = yaml.safe_load(f) or {}

    def generate(self, nodes: List[Node], output_path: str, source_count: int = 0, raw_count: int = 0, elapsed_time: float = 0):
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        now_short = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        # 0. 构造 5 个订阅信息/公告展示节点 (安全回环地址，仅供信息展示)
        info_names = [
            "⚠️ 本组仅作展示·请勿选择",
            f"⏰ 更新时间 | {now_short}",
            f"📊 节点数量 | {len(nodes)} 个有效节点",
            "⭐ 项目主页 | github.com/lanzm/MetaFetch",
            "📢 官方电报 | t.me/MetaFetchNodes"
        ]
        info_proxies = [
            {
                'name': name,
                'type': 'ss',
                'server': '127.0.0.1',
                'port': 10000,
                'cipher': 'aes-128-gcm',
                'password': 'fake'
            }
            for name in info_names
        ]

        config = copy.deepcopy(self.template)
        clash_proxies = [node.to_clash() for node in nodes]
        
        config['proxies'] = info_proxies + clash_proxies
        
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
        # 3. 质量评分函数 (实测带宽 > speednode > Hysteria2 > Reality > VLESS/Trojan > 普通)
        name_to_node = {node.name: node for node in nodes}

        def get_node_quality_score(name: str) -> float:
            score = 10.0
            name_lower = name.lower()
            node_obj = name_to_node.get(name)
            node_type = getattr(node_obj, 'type', '').lower() if node_obj else ''

            m_mb = _MB_SPEED_RE.search(name)
            if m_mb:
                try:
                    score = 100.0 + float(m_mb.group(1))
                except (ValueError, TypeError):
                    score = 100.0
            elif _KB_SPEED_RE.search(name):
                score = 95.0
            elif 'speednode' in name_lower:
                score = 90.0
            elif node_type in ('hysteria2', 'hy2') or 'hy2' in name_lower or 'hysteria' in name_lower:
                score = 80.0
            elif node_obj and (node_obj.data.get('reality-opts') or 'reality' in name_lower):
                score = 75.0
            elif node_type == 'vless':
                score = 60.0
            elif node_type == 'trojan':
                score = 50.0
            elif node_type == 'ss':
                score = 40.0
            else:
                score = 30.0
            return score

        # 4. Create Dynamic Region Groups (地区内自动选择同样采用 fallback 故障转移模式，并按质量排序)
        dynamic_groups = []
        region_list_for_menu = []
        
        test_url = "https://cp.cloudflare.com/generate_204"
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

        # 核心主流地区（港、日、美、新）适当倾斜配置名额
        CORE_REGIONS = {'HK', 'JP', 'US', 'SG'}
        smart_pool_nodes = []

        for key in active_keys:
            if key == 'CN': continue  # 排除纯国内组
            candidates = [n for n in region_nodes[key] if not is_china_node(n)]
            if not candidates: continue
            candidates_sorted = sorted(candidates, key=get_node_quality_score, reverse=True)
            max_limit = 8 if key in CORE_REGIONS else 4
            smart_pool_nodes.extend(candidates_sorted[:max_limit])

        if others:
            other_candidates = [n for n in others if not is_china_node(n)]
            if other_candidates:
                other_sorted = sorted(other_candidates, key=get_node_quality_score, reverse=True)
                smart_pool_nodes.extend(other_sorted[:4])

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
                g['proxies'] = (info_names + node_names) if (info_names or node_names) else ['DIRECT']
            elif g['name'] == '📢 订阅信息':
                g['proxies'] = info_names if info_names else ['DIRECT']
        
        config['proxy-groups'] = template_groups + dynamic_groups
        config = deep_sanitize(config)

        # 6. Save YAML (Clash Meta)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Generated by MetaFetch\n# Updated at: {now_str}\n")
            yaml_content = yaml.dump(config, Dumper=SafeDumper, allow_unicode=False, default_flow_style=False, sort_keys=False)
            yaml_content = re.sub(r'short-id:\s*([^\s"\']+)', r'short-id: "\1"', yaml_content)
            yaml_content = re.sub(r'public-key:\s*([^\s"\']+)', r'public-key: "\1"', yaml_content)
            yaml_content = _YAML_SAFE_CONTROL_REGEX.sub('', yaml_content)
            f.write(yaml_content)
        
        # 7. Save Universal Links (Base64 & Plain TXT)
        node_urls = [url for node in nodes if (url := node.to_url())]
        raw_urls_str = "\n".join(node_urls)
        
        output_dir = os.path.dirname(output_path)
        txt_path = os.path.join(output_dir, "list.txt") if output_dir else "list.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(raw_urls_str)
            
        b64_path = os.path.join(output_dir, "list.b64") if output_dir else "list.b64"
        with open(b64_path, 'w', encoding='utf-8') as f:
            f.write(b64encodes(raw_urls_str))

        logger.info(f"Successfully generated {len(nodes)} nodes across formats ({output_path}, {b64_path}, {txt_path})")
        return {
            'total_nodes': len(nodes),
            'region_nodes': region_nodes,
            'others': others,
            'timestamp': now_str,
            'source_count': source_count,
            'raw_count': raw_count,
            'elapsed_time': elapsed_time
        }
