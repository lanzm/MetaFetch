import copy
import yaml
import datetime
import re
import os
from typing import List, Dict, Any, Optional
from core.parser import Node
from utils.regions import REGIONS_DB, match_region, REGION_NAMES
from utils.common import b64encodes
from utils.logger import logger

_MB_SPEED_RE = re.compile(r'(\d+\.?\d*)\s*(?:mb/s|m/s|mbps)', re.IGNORECASE)
_KB_SPEED_RE = re.compile(r'(\d+\.?\d*)\s*(?:kb/s|k/s|kbps)', re.IGNORECASE)
# 引入控制字符深度清洗工具（保留 _YAML_SAFE_CONTROL_REGEX 与 deep_sanitize 导出兼容）
from utils.common import deep_sanitize, YAML_SAFE_CONTROL_REGEX as _YAML_SAFE_CONTROL_REGEX


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
    def __init__(self, template_path: str, pool_settings: Optional[Dict[str, Any]] = None):
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = yaml.safe_load(f) or {}
        self.pool_settings = pool_settings or {}

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
            matched_key = node.data['_region'] if '_region' in node.data else match_region(name)
            if matched_key and matched_key in REGIONS_DB:
                node_to_region[name] = matched_key
                region_counts[matched_key] += 1
            else:
                node_to_region[name] = 'OTHERS'

        # 2. Filter Active Regions (只要节点数 > 0 即可独立建组，自动保持 REGIONS_DB 插入序)
        active_keys = [
            k for k, count in region_counts.items() 
            if count > 0
        ]
        
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
                    speed_mb = float(m_mb.group(1))
                    score = (100.0 + speed_mb) if speed_mb > 0.0 else 5.0
                except (ValueError, TypeError):
                    score = 100.0
            else:
                m_kb = _KB_SPEED_RE.search(name)
                if m_kb:
                    try:
                        speed_kb = float(m_kb.group(1))
                        score = (90.0 + min(speed_kb / 1024.0, 5.0)) if speed_kb > 0.0 else 5.0
                    except (ValueError, TypeError):
                        score = 90.0
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

        # 私有节点专属策略组 (仅在包含私有节点时创建)
        private_nodes = [node for node in nodes if node.data.get('_is_private')]
        has_private = len(private_nodes) > 0
        priv_groups = []
        if has_private:
            priv_node_names = [n.name for n in private_nodes]
            priv_auto_name = "⚡ 自动选择 | 👑 私有节点"
            priv_sorted = sorted(priv_node_names, key=get_node_quality_score, reverse=True)
            priv_groups.append({
                'name': '👑 私有节点',
                'type': 'select',
                'proxies': ([priv_auto_name] + priv_sorted) if priv_sorted else ['DIRECT']
            })
            priv_groups.append({
                'name': priv_auto_name,
                'type': 'fallback',
                'url': test_url,
                'interval': test_interval,
                'timeout': test_timeout,
                'lazy': False,
                'hidden': True,
                'proxies': priv_sorted if priv_sorted else ['DIRECT']
            })

        # 5. 构建雨露均沾智能精选池 (Smart Pool Extractor)

        def is_china_node(name: str) -> bool:
            """判断是否为中国境内节点，对 CN2-GIA / IPLC 等海外中转线路进行白名单豁免"""
            reg = node_to_region.get(name, '')
            if reg == 'CN' or '🇨🇳' in name:
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

        def _parse_limit(val: Any, default: int) -> float:
            if val is None or val == "":
                return default
            try:
                iv = int(val)
                return float('inf') if iv == -1 else max(0, iv)
            except (ValueError, TypeError):
                return default

        # 解析 Smart Pool 配置 (方案 1: 防呆安全型，空值回退默认值，-1 不限，0 禁用)
        cfg_core_regions = self.pool_settings.get('core_regions')
        if not isinstance(cfg_core_regions, list) or not cfg_core_regions:
            cfg_core_regions = ["HK", "JP", "US", "SG"]
        core_regions_set = set(cfg_core_regions)

        priv_cfg = self.pool_settings.get('private') or {}
        priv_max_total = _parse_limit(priv_cfg.get('max_total'), 12)
        priv_core_limit = _parse_limit(priv_cfg.get('core_per_region'), 3)
        priv_other_limit = _parse_limit(priv_cfg.get('other_per_region'), 1)

        pub_cfg = self.pool_settings.get('public') or {}
        pub_core_limit = _parse_limit(pub_cfg.get('core_per_region'), 8)
        pub_other_limit = _parse_limit(pub_cfg.get('other_per_region'), 4)

        min_pool_size = _parse_limit(self.pool_settings.get('min_pool_size'), 20)
        max_pool_size = _parse_limit(self.pool_settings.get('max_pool_size'), 120)

        priv_selected = []
        pub_selected = []

        # 1. 精选私有节点代表 (仅限海外节点，按各地区配额提取)
        if has_private and priv_max_total > 0:
            for key in active_keys:
                if key == 'CN': continue
                candidates = [
                    n for n in region_nodes[key]
                    if not is_china_node(n) and name_to_node[n].data.get('_is_private')
                ]
                if not candidates: continue
                candidates_sorted = sorted(candidates, key=get_node_quality_score, reverse=True)
                limit = priv_core_limit if key in core_regions_set else priv_other_limit
                if limit > 0:
                    limit_count = len(candidates_sorted) if limit == float('inf') else int(limit)
                    priv_selected.extend(candidates_sorted[:limit_count])

            if others:
                other_priv = [
                    n for n in others
                    if not is_china_node(n) and name_to_node[n].data.get('_is_private')
                ]
                if other_priv and priv_other_limit > 0:
                    other_sorted = sorted(other_priv, key=get_node_quality_score, reverse=True)
                    limit_count = len(other_sorted) if priv_other_limit == float('inf') else int(priv_other_limit)
                    priv_selected.extend(other_sorted[:limit_count])

            # 私有节点全局上限截断 (按质量排序)
            if priv_max_total != float('inf') and len(priv_selected) > priv_max_total:
                priv_selected = sorted(priv_selected, key=get_node_quality_score, reverse=True)[:int(priv_max_total)]

        # 2. 精选公共节点代表 (用于日常兜底)
        for key in active_keys:
            if key == 'CN': continue
            candidates = [
                n for n in region_nodes[key]
                if not is_china_node(n) and not name_to_node[n].data.get('_is_private')
            ]
            if not candidates: continue
            candidates_sorted = sorted(candidates, key=get_node_quality_score, reverse=True)
            limit = pub_core_limit if key in core_regions_set else pub_other_limit
            if limit > 0:
                limit_count = len(candidates_sorted) if limit == float('inf') else int(limit)
                pub_selected.extend(candidates_sorted[:limit_count])

        if others:
            other_pub = [
                n for n in others
                if not is_china_node(n) and not name_to_node[n].data.get('_is_private')
            ]
            if other_pub and pub_other_limit > 0:
                other_sorted = sorted(other_pub, key=get_node_quality_score, reverse=True)
                limit_count = len(other_sorted) if pub_other_limit == float('inf') else int(pub_other_limit)
                pub_selected.extend(other_sorted[:limit_count])

        # 3. 编排 Smart Pool: 私有节点置顶，公共节点紧随其后作为容灾兜底
        smart_pool_nodes = priv_selected + pub_selected

        # 4. 保底补充 (min_pool_size): 若节点过少，从公共海外全量节点按质量补齐
        pub_oversea_nodes = [
            n for n in node_names
            if not is_china_node(n) and not name_to_node[n].data.get('_is_private')
        ]
        min_limit_int = int(min_pool_size) if min_pool_size != float('inf') else len(pub_oversea_nodes)
        if min_limit_int > 0 and len(smart_pool_nodes) < min_limit_int and pub_oversea_nodes:
            fallback_sorted = sorted(pub_oversea_nodes, key=get_node_quality_score, reverse=True)
            for fn in fallback_sorted:
                if fn not in smart_pool_nodes:
                    smart_pool_nodes.append(fn)
                if len(smart_pool_nodes) >= min_limit_int:
                    break

        if not smart_pool_nodes:
            oversea_all = [n for n in node_names if not is_china_node(n)]
            smart_pool_nodes = pub_oversea_nodes if pub_oversea_nodes else (oversea_all if oversea_all else node_names)

        # 5. 全局最大容量最终截断 (防测速风暴，优先保全私有节点)
        if max_pool_size != float('inf') and len(smart_pool_nodes) > int(max_pool_size):
            max_limit_int = int(max_pool_size)
            priv_in_pool = [n for n in smart_pool_nodes if name_to_node.get(n) and name_to_node[n].data.get('_is_private')]
            pub_in_pool = [n for n in smart_pool_nodes if not (name_to_node.get(n) and name_to_node[n].data.get('_is_private'))]
            if len(priv_in_pool) >= max_limit_int:
                smart_pool_nodes = priv_in_pool[:max_limit_int]
            else:
                smart_pool_nodes = priv_in_pool + pub_in_pool[:(max_limit_int - len(priv_in_pool))]

        # 6. Fill Template Groups
        template_groups = config.get('proxy-groups', [])
        for g in template_groups:
            if g['name'] == '🚀 选择代理':
                if has_private and '👑 私有节点' not in g['proxies']:
                    g['proxies'] = ['👑 私有节点'] + [p for p in g['proxies'] if p != '👑 私有节点']
            elif g['name'] == '🗺️ 选择地区':
                g['proxies'] = region_list_for_menu if region_list_for_menu else ['DIRECT']
            elif g['name'] in ('♻️ 自动选择', '🔰 延迟最低'):
                g['proxies'] = smart_pool_nodes if smart_pool_nodes else ['DIRECT']
            elif g['name'] == '✅ 手动选择':
                g['proxies'] = node_names if node_names else ['DIRECT']
            elif g['name'] == '📢 订阅信息':
                g['proxies'] = info_names if info_names else ['DIRECT']

        # 组装策略组：如果存在私有节点，将 👑 私有节点 插入在 🗺️ 选择地区 之前
        final_template_groups = []
        for g in template_groups:
            if g['name'] == '🗺️ 选择地区' and has_private:
                final_template_groups.extend(priv_groups)
            final_template_groups.append(g)
        if has_private and not any(g['name'] == '👑 私有节点' for g in final_template_groups):
            final_template_groups.extend(priv_groups)

        config['proxy-groups'] = final_template_groups + dynamic_groups
        config = deep_sanitize(config, preserve_newlines=True)

        # 6. Save YAML (Clash Meta)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Generated by MetaFetch\n# Updated at: {now_str}\n")
            yaml_content = yaml.dump(config, Dumper=SafeDumper, allow_unicode=True, default_flow_style=False, sort_keys=False)
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
