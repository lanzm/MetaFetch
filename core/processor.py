import re
from typing import List, Set, Dict, Any
from core.parser import Node
from utils.regions import REGIONS_DB

# Region mapping for Emoji flags
REGION_FLAGS = {}
for code, info in REGIONS_DB.items():
    for kw in info['keywords'] + [code, info['name']]:
        REGION_FLAGS[kw] = info['emoji']

# 动态生成所有组名(地区组 + 自动选择组),防止节点名与组名冲突导致 Clash 循环引用
GROUP_NAMES = [f"{info['emoji']} {info['name']}" for info in REGIONS_DB.values()]
GROUP_NAMES += ['🌍 其他地区']
GROUP_NAMES += [f"⚡ 自动选择 | {name}" for name in GROUP_NAMES]

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
                # 校验 Shadowsocks plugin
                plugin = n_data.get('plugin')
                if plugin:
                    if plugin in ('obfs-local', 'simple-obfs'):
                        plugin = 'obfs'
                    
                    opts = n_data.get('plugin-opts')
                    if not isinstance(opts, dict):
                        opts = {}

                    if plugin == 'obfs':
                        mode = str(opts.get('mode', '')).lower()
                        if mode in ('http', 'tls'):
                            opts['mode'] = mode
                            n_data['plugin'] = 'obfs'
                            n_data['plugin-opts'] = opts
                        elif mode == 'websocket':
                            # websocket 属于 v2ray-plugin 模式，自动纠正
                            n_data['plugin'] = 'v2ray-plugin'
                            opts['mode'] = 'websocket'
                            n_data['plugin-opts'] = opts
                        else:
                            # 非法 obfs mode，移除插件属性降级为普通 ss
                            n_data.pop('plugin', None)
                            n_data.pop('plugin-opts', None)

                    if n_data.get('plugin') == 'v2ray-plugin':
                        opts = n_data.get('plugin-opts', {})
                        mode = str(opts.get('mode', 'websocket')).lower()
                        if mode not in ('websocket', 'http', 'quic'):
                            mode = 'websocket'
                        opts['mode'] = mode
                        for bool_key in ('mux', 'tls', 'skip-cert-verify'):
                            if bool_key in opts:
                                val = opts[bool_key]
                                if isinstance(val, str):
                                    opts[bool_key] = (val.lower() in ('true', '1', 'yes') or (bool_key == 'mux' and val not in ('0', 'false', 'no', '')))
                                elif isinstance(val, int):
                                    opts[bool_key] = bool(val)
                        n_data['plugin'] = 'v2ray-plugin'
                        n_data['plugin-opts'] = opts
                    elif n_data.get('plugin') not in ('obfs', 'v2ray-plugin', 'shadow-tls', 'restls'):
                        # 其他不支持的第三方插件，移除插件属性降级为普通 ss
                        n_data.pop('plugin', None)
                        n_data.pop('plugin-opts', None)
            elif n_type == 'trojan':
                if not n_data.get('password'):
                    continue
            elif n_type in ('hysteria2', 'hy2'):
                if not n_data.get('password'):
                    continue
                # 校验 obfs 完整性：有 obfs 但无 obfs-password 时剔除孤立的 obfs 字段
                obfs = n_data.get('obfs')
                if obfs and obfs != 'none' and not n_data.get('obfs-password'):
                    n_data.pop('obfs', None)
            
            valid_nodes.append(node)
        return valid_nodes

    def process_all(self, nodes: List[Node]) -> List[Node]:
        nodes = self.filter_invalid(nodes)  # 1. 过滤无效节点
        nodes = self.deduplicate(nodes)     # 2. 去重
        self.clean_and_rename(nodes)        # 3. 清洗命名
        return nodes
