import re
from collections import defaultdict
from typing import List, Set, Dict
from core.parser import Node
from utils.regions import REGIONS_DB, match_region

# 清理广告与多余链接的预编译正则
CLEAN_AD_REGEXES = [
    re.compile(r'(?i)(tg频道|订阅|加入|获取|联系|Telegram|tg|Channel)[\s:：]*@\S+'),
    re.compile(r'(?i)(t\.me/\S+|https?://\S+)')
]

# 动态生成所有组名(地区组 + 自动选择组 + 模板静态组),防止节点名与组名冲突导致 Clash 循环引用
GROUP_NAMES = {f"{info['emoji']} {info['name']}" for info in REGIONS_DB.values()}
GROUP_NAMES.add('🌍 其他地区')
GROUP_NAMES.update([f"⚡ 自动选择 | {name}" for name in list(GROUP_NAMES)])
GROUP_NAMES.update({'🚀 选择代理', '🗺️ 选择地区', '♻️ 自动选择', '🔰 延迟最低', '✅ 手动选择', 'DIRECT', 'REJECT', 'PASS'})

# 无效与回环 server 过滤黑名单
INVALID_SERVERS = {
    '0.0.0.0', '127.0.0.1', 'localhost', '::1', '1.1.1.1',
    'example.com', 'test.com', 'none', 'null', 'undefined'
}

class NodeProcessor:
    def __init__(self):
        self.used_names: Set[str] = set()
        self.name_counter: Dict[str, int] = defaultdict(int)

    def deduplicate(self, nodes: List[Node]) -> List[Node]:
        seen = set()
        deduped = []
        for node in nodes:
            ident = node.get_identity()
            if ident not in seen:
                seen.add(ident)
                deduped.append(node)
        return deduped

    def clean_and_rename(self, nodes: List[Node]):
        self.used_names.clear()
        self.name_counter.clear()

        for node in nodes:
            name = str(node.data.get('name') or 'node')
            # 1. 基础清理 (广告、Telegram 频道、不安全字符)
            for reg in CLEAN_AD_REGEXES:
                name = reg.sub('', name)

            # YAML Safety: 替换破坏 YAML 结构或引用的特殊字符及换行
            name = name.replace('\r', ' ').replace('\n', ' ')
            name = name.replace(':', '-').replace('[', '').replace(']', '')
            name = name.replace('not found', '').replace('Unnamed', '').strip()

            # 如果节点名称为空，使用保底名称
            if not name:
                name = f"Node-{node.type}-{node.data.get('server', 'unknown')}"

            # 2. 统一地区识别与国旗 Emoji 补全 (并持久化 _region 属性供下游直接使用)
            region_code = match_region(name)
            if region_code:
                node.data['_region'] = region_code
                flag = REGIONS_DB[region_code]['emoji']
                if flag not in name:
                    name = f"{flag} {name}"

            # 3. 避免与 Clash Policy Group 组名完全重名导致内核循环引用，并处理重名编号
            if name in GROUP_NAMES or name in self.used_names:
                count = max(1 if name in GROUP_NAMES else 2, self.name_counter[name] + 1)
                new_name = f"{name} #{count}"
                while new_name in self.used_names or new_name in GROUP_NAMES:
                    count += 1
                    new_name = f"{name} #{count}"
                self.name_counter[name] = count
                name = new_name
            else:
                self.name_counter[name] = 1

            self.used_names.add(name)
            node.data['name'] = name

    def filter_invalid(self, nodes: List[Node]) -> List[Node]:
        valid_nodes = []
        for node in nodes:
            n_data = node.data
            n_type = n_data.get('type', 'unknown')
            n_server = str(n_data.get('server', '')).strip()
            n_port = n_data.get('port')

            # 1. 基础字段验证：type, server 不能为空
            if n_type == 'unknown' or not n_server:
                continue

            # 过滤回环、占位或非法 server 地址
            if n_server.lower() in INVALID_SERVERS or any(c in n_server for c in (' ', '\n', '\r', '\t')):
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
