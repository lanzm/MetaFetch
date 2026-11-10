import re
from collections import defaultdict
from typing import List, Set, Dict, Any
from core.parser import Node
from utils.regions import REGIONS_DB, match_region
from utils.ciphers import normalize_ss_cipher, is_valid_ss_cipher
from utils.logger import logger

# 清理广告与多余链接的预编译正则
CLEAN_AD_REGEXES = [
    re.compile(r'(?i)(tg频道|订阅|加入|获取|联系|Telegram|tg|Channel)[\s:：]*@\S+'),
    re.compile(r'(?i)(t\.me/\S+|https?://\S+)')
]

# 清理广告剥离后残留的首尾孤立标点符号 (如 "|", "-", "_", " / " 等) 模块级预编译
STRIP_PUNCT_REGEX = re.compile(r'^[\s\-_|/\\·:]+|[\s\-_|/\\·:]+$')

# 引入控制字符深度清洗工具（保留 CONTROL_CHARS_REGEX 与 deep_sanitize 导出兼容）
from utils.common import deep_sanitize, STRICT_CONTROL_REGEX as CONTROL_CHARS_REGEX


# 提示/公告/失效假节点过滤关键词
NOTICE_NODE_KEYWORDS = (
    '更新订阅', '节点不可用', '请更新', '到期时间', '剩余流量', '套餐到期',
    '官网', '发布页', '飞机群', '电报群', '官方群', '客服', '禁止测速', '请勿测速'
)

# 动态生成所有组名(地区组 + 自动选择组 + 模板静态组),防止节点名与组名冲突导致 Clash 循环引用
GROUP_NAMES = {f"{info['emoji']} {info['name']}" for info in REGIONS_DB.values()}
GROUP_NAMES.add('🌍 其他地区')
GROUP_NAMES.update([f"⚡ 自动选择 | {name}" for name in list(GROUP_NAMES)])
GROUP_NAMES.update({'🚀 选择代理', '🗺️ 选择地区', '♻️ 自动选择', '🔰 延迟最低', '✅ 手动选择', '📢 订阅信息', '👑 私有节点', '⚡ 自动选择 | 👑 私有节点', 'DIRECT', 'REJECT', 'PASS'})

# 引入通用网络地址与安全校验工具（防 SSRF，保留当前模块导出以保持兼容）
from utils.validators import is_invalid_or_private_server, INVALID_SERVERS
from utils.constants import ALLOWED_TYPES

class NodeProcessor:
    def __init__(self):
        self.used_names: Set[str] = set()
        self.name_counter: Dict[str, int] = defaultdict(int)

    def deduplicate(self, nodes: List[Node]) -> List[Node]:
        seen: Dict[str, Node] = {}
        for node in nodes:
            ident = node.get_identity()
            if ident not in seen:
                seen[ident] = node
            elif node.data.get('_is_private') and not seen[ident].data.get('_is_private'):
                # 私有节点优先级最高，覆盖已有的公共节点
                seen[ident] = node
        return list(seen.values())

    def clean_and_rename(self, nodes: List[Node]) -> List[Node]:
        self.used_names.clear()
        self.name_counter.clear()

        for node in nodes:
            name = str(node.data.get('name') or 'node')
            # 1. 基础清理 (广告、Telegram 频道、不安全字符)
            for reg in CLEAN_AD_REGEXES:
                name = reg.sub('', name)

            # YAML Safety: 彻底清除控制字符、破坏 YAML 结构或引用的特殊字符及换行
            name = CONTROL_CHARS_REGEX.sub('', name)
            name = name.replace(':', '-').replace('[', '').replace(']', '')
            name = name.replace('not found', '').replace('Unnamed', '').strip()
            # 清理广告剥离后残留的首尾孤立标点符号 (如 "|", "-", "_", " / " 等)
            name = STRIP_PUNCT_REGEX.sub('', name).strip()

            # 如果节点名称为空，使用保底名称
            if not name:
                name = f"Node-{node.type}-{node.data.get('server', 'unknown')}"

            # Shadowsocks 加密算法统一规范化
            if node.type == 'ss' and 'cipher' in node.data:
                node.data['cipher'] = normalize_ss_cipher(node.data.get('cipher'))

            # 2. 统一地区识别与国旗 Emoji 补全 (并持久化 _region 属性供下游直接使用，未匹配记为 None 避免二次全库遍历)
            region_code = match_region(name)
            node.data['_region'] = region_code
            if region_code:
                flag = REGIONS_DB[region_code]['emoji']
                if flag not in name:
                    name = f"{flag} {name}"

            # 3. 私有节点尊贵标识 (前缀 👑，防重复添加)
            if node.data.get('_is_private') and not name.startswith('👑'):
                name = f"👑 {name}"

            # 4. 避免与 Clash Policy Group 组名完全重名导致内核循环引用，并处理重名编号
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
        return nodes

    def filter_invalid(self, nodes: List[Node]) -> List[Node]:
        valid_nodes = []
        for node in nodes:
            try:
                n_data = node.data
                n_name = str(n_data.get('name', ''))

                # 过滤包含明显提示信息/公告/失效关键词的假节点
                if any(kw in n_name for kw in NOTICE_NODE_KEYWORDS):
                    continue

                n_type = str(n_data.get('type', 'unknown')).lower()
                n_server = str(n_data.get('server', '')).strip()
                n_port = n_data.get('port')

                # 1. 基础字段验证：白名单协议类型、server 不能为空
                if n_type not in ALLOWED_TYPES or not n_server:
                    continue

                # 过滤回环、占位、私有内网/云元数据或非法 server 地址 (防 SSRF)
                if is_invalid_or_private_server(n_server):
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
                    norm_cipher = normalize_ss_cipher(n_data.get('cipher'))
                    if not is_valid_ss_cipher(norm_cipher):
                        continue
                    n_data['cipher'] = norm_cipher
                    # 校验 Shadowsocks plugin
                    plugin = n_data.get('plugin')
                    if plugin:
                        if plugin in ('obfs-local', 'simple-obfs'):
                            plugin = 'obfs'

                        opts = n_data.get('plugin-opts') or {}
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
                            opts = n_data.get('plugin-opts') or {}
                            if not isinstance(opts, dict):
                                opts = {}
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
                    pwd = n_data.get('password') or n_data.get('auth')
                    if not pwd:
                        continue
                    n_data['password'] = pwd
                    # 校验 obfs 完整性：如果为 none 或无 obfs-password 时剔除孤立/非法的 obfs 字段
                    obfs = n_data.get('obfs')
                    if obfs:
                        if str(obfs).lower() == 'none' or not n_data.get('obfs-password'):
                            n_data.pop('obfs', None)
                            n_data.pop('obfs-password', None)

                valid_nodes.append(node)
            except Exception as e:
                logger.debug(f"Skipping malformed node during validation: {e}")
                continue
        return valid_nodes

    def process_all(self, nodes: List[Node]) -> List[Node]:
        # 0. 预处理：彻底清理所有节点属性（server, uuid, password, name等）中的不可见控制字符与零宽字符
        # 确保去重指纹计算与回环检测完全不受隐形字符污染
        for node in nodes:
            node.data = deep_sanitize(node.data)
            node._identity_cache = None
        nodes = self.filter_invalid(nodes)  # 1. 过滤无效节点
        nodes = self.deduplicate(nodes)     # 2. 精准去重
        nodes = self.clean_and_rename(nodes) # 3. 清洗命名
        return nodes
