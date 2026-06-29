import re
from typing import List, Set, Dict, Any
from core.parser import Node

# Region mapping for Emoji flags
REGION_FLAGS = {
    'HK': '🇭🇰', 'HKG': '🇭🇰', 'Hong Kong': '🇭🇰', '香港': '🇭🇰',
    'TW': '🇹🇼', 'TWN': '🇹🇼', 'Taiwan': '🇹🇼', '台湾': '🇹🇼',
    'JP': '🇯🇵', 'JPN': '🇯🇵', 'Japan': '🇯🇵', '日本': '🇯🇵',
    'US': '🇺🇸', 'USA': '🇺🇸', 'United States': '🇺🇸', '美国': '🇺🇸',
    'SG': '🇸🇬', 'SGP': '🇸🇬', 'Singapore': '🇸🇬', '新加坡': '🇸🇬',
    'KR': '🇰🇷', 'KOR': '🇰🇷', 'Korea': '🇰🇷', '韩国': '🇰🇷',
    'GB': '🇬🇧', 'UK': '🇬🇧', 'United Kingdom': '🇬🇧', '英国': '🇬🇧',
    'FR': '🇫🇷', 'FRA': '🇫🇷', 'France': '🇫🇷', '法国': '🇫🇷',
    'DE': '🇩🇪', 'DEU': '🇩🇪', 'Germany': '🇩🇪', '德国': '🇩🇪',
    'CN': '🇨🇳', 'CHN': '🇨🇳', 'China': '🇨🇳', '中国': '🇨🇳',
    'RU': '🇷🇺', 'RUS': '🇷🇺', 'Russia': '🇷🇺', '俄罗斯': '🇷🇺',
    'CA': '🇨🇦', 'CAN': '🇨🇦', 'Canada': '🇨🇦', '加拿大': '🇨🇦',
    'VN': '🇻🇳', 'VNM': '🇻🇳', 'Vietnam': '🇻🇳', '越南': '🇻🇳',
    'NL': '🇳🇱', 'NLD': '🇳🇱', 'Netherlands': '🇳🇱', '荷兰': '🇳🇱',
    'CH': '🇨🇭', 'CHE': '🇨🇭', 'Switzerland': '🇨🇭', '瑞士': '🇨🇭',
    'IN': '🇮🇳', 'IND': '🇮🇳', 'India': '🇮🇳', '印度': '🇮🇳',
    'TR': '🇹🇷', 'TUR': '🇹🇷', 'Turkey': '🇹🇷', '土耳其': '🇹🇷',
    'AU': '🇦🇺', 'AUS': '🇦🇺', 'Australia': '🇦🇺', '澳大利亚': '🇦🇺',
}

class NodeProcessor:
    def __init__(self):
        self.used_names = set()

    def deduplicate(self, nodes: List[Node]) -> List[Node]:
        seen = set()
        deduped = []
        for node in nodes:
            h = hash(node)
            if h not in seen:
                seen.add(h)
                deduped.append(node)
        return deduped

    def clean_and_rename(self, nodes: List[Node]):
        self.used_names.clear()
        for node in nodes:
            name = node.data.get('name', 'node')
            # 1. Basic cleaning (Removing Ads / YAML-unsafe char / Telegram links)
            # Remove Telegram channels, group names, join links
            name = re.sub(r'(?i)(tg频道|订阅|加入|获取|联系|Telegram|tg|Channel)[\s:：]*@\S+', '', name)
            name = re.sub(r'(?i)(t\.me/\S+|https?://\S+)', '', name)
            
            # YAML Safety: Replace characters that often break naming references or YAML parsing
            name = name.replace(':', '-').replace('[', '').replace(']', '')
            
            # Keep original parts but remove specific junk tags
            name = name.replace('not found', '').replace('Unnamed', '')
            name = name.strip()
            
            # If name is empty or too short, use a fallback
            if not name:
                name = f"Node-{node.type}-{node.data.get('server', 'unknown')}"
            
            # 2. Add emoji flag if missing
            found_flag = False
            # Common regional group names to avoid clashing with
            GROUP_NAMES = ['🇭🇰 香港', '🇹🇼 台湾', '🇯🇵 日本', '🇺🇸 美国', '🇸🇬 新加坡', '🇰🇷 韩国', '🌍 其他地区']
            for code, flag in REGION_FLAGS.items():
                if flag in name:
                    found_flag = True
                    break
            
            if not found_flag:
                # 按照长度倒序排列，优先匹配长的关键词（如 Hong Kong 优先于 HK）
                sorted_codes = sorted(REGION_FLAGS.keys(), key=len, reverse=True)
                for code in sorted_codes:
                    flag = REGION_FLAGS[code]
                    # 使用正则匹配：要求关键词前后是边界（空格、下划线、短杠或字符串起止）
                    # 这样可以避免 speednode 里的 'de' 匹配到德国
                    pattern = rf"(?i)(^|[\s_\-（(]){re.escape(code)}([\s_\-）)]|$)"
                    if re.search(pattern, name):
                        name = f"{flag} {name}"
                        found_flag = True
                        break
            
            # 3. Ensure uniqueness and distinctiveness from groups
            GROUP_NAMES = ['🇭🇰 香港', '🇹🇼 台湾', '🇯🇵 日本', '🇺🇸 美国', '🇸🇬 新加坡', '🇰🇷 韩国', '🌍 其他地区']
            
            base_name = name
            # If name matches a group exactly, force a suffix to avoid loop
            if name in GROUP_NAMES:
                name = f"{base_name} #1"
            
            # Now handle duplicates within nodes
            if name in self.used_names:
                counter = 2
                new_name = f"{base_name} #{counter}"
                while new_name in self.used_names or new_name in GROUP_NAMES:
                    counter += 1
                    new_name = f"{base_name} #{counter}"
                name = new_name
            
            self.used_names.add(name)
            node.data['name'] = name

    def filter_invalid(self, nodes: List[Node]) -> List[Node]:
        valid_nodes = []
        for node in nodes:
            n_data = node.data
            n_type = n_data.get('type', 'unknown')
            n_server = n_data.get('server')
            n_port = n_data.get('port')
            
            # 1. 基础字段验证：type, server 不能为空
            if n_type == 'unknown' or not n_server:
                continue
            
            # 2. 验证 port 必须为有效端口 (1-65535)
            if n_port is None:
                continue
            try:
                port_val = int(n_port)
                if not (1 <= port_val <= 65535):
                    continue
                n_data['port'] = port_val
            except (ValueError, TypeError):
                continue
            
            # 3. 协议特定必要字段验证
            if n_type == 'vmess':
                if not n_data.get('uuid'):
                    continue
            elif n_type == 'vless':
                if not n_data.get('uuid'):
                    continue
            elif n_type == 'ss':
                if not n_data.get('cipher') or not n_data.get('password'):
                    continue
            elif n_type == 'trojan':
                if not n_data.get('password'):
                    continue
            
            valid_nodes.append(node)
        return valid_nodes

    def process_all(self, nodes: List[Node]) -> List[Node]:
        nodes = self.filter_invalid(nodes)  # 1. 过滤无效节点
        nodes = self.deduplicate(nodes)     # 2. 去重
        self.clean_and_rename(nodes)        # 3. 清洗命名
        return nodes
