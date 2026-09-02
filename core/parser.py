import json
from typing import Dict, Any, Union, Optional
from urllib.parse import urlparse, unquote, quote, parse_qsl
from utils.common import b64decodes, b64decodes_safe, b64encodes

class Node:
    def __init__(self, data: Union[Dict[str, Any], str]):
        self.data: Dict[str, Any] = {}
        if isinstance(data, dict):
            self.data = data.copy()
            self.type = self.data.get('type', 'unknown')
            self._clean_dict_fields()
        elif isinstance(data, str):
            self.load_url(data)
        
        # Ensure name exists
        if not self.data.get('name'):
            self.data['name'] = "Unnamed"
        
        # Standardize type
        self.type = self.data.get('type', 'unknown')

    @property
    def name(self):
        return self.data.get('name', 'Unnamed')

    def load_url(self, url: str):
        if '://' not in url:
            return
        
        protocol, dt = url.split("://", 1)
        protocol = protocol.strip().lower()
        if protocol == 'hy2': protocol = 'hysteria2'
        
        # 严格过滤非法协议（如 HTML 标签内嵌的 https 链接）
        allowed = ('vmess', 'vless', 'ss', 'trojan', 'hysteria2')
        if protocol not in allowed:
            return

        self.type = protocol
        loader = getattr(self, f'_load_{self.type}', None)
        if loader:
            loader(url, dt)

    def _validate_short_id(self, sid: str) -> Optional[str]:
        if not sid: return None
        # 移除非 16 进制字符
        sid = "".join(c for c in sid if c.lower() in "0123456789abcdef")
        if not sid: return None
        # 确保长度为偶数 (Clash 要求)
        if len(sid) % 2 != 0:
            sid = sid[:-1]
        if not sid: return None
        return sid[:16]

    def _clean_dict_fields(self):
        # 1. Clean cipher for VMess
        if self.type == 'vmess':
            cipher = str(self.data.get('cipher') or '').strip().lower()
            if cipher not in ('auto', 'aes-128-gcm', 'chacha20-poly1305', 'none', 'zero'):
                cipher = 'auto'
            self.data['cipher'] = cipher
            
        # 2. Clean Reality options for VLESS/Trojan
        if self.type in ('vless', 'trojan'):
            ropts = self.data.get('reality-opts')
            if isinstance(ropts, dict):
                pbk = ropts.get('public-key')
                if pbk:
                    ropts['public-key'] = unquote(str(pbk))
                sid = ropts.get('short-id') or ropts.get('shortId')
                if sid:
                    valid_sid = self._validate_short_id(str(sid))
                    if valid_sid:
                        ropts['short-id'] = valid_sid
                    else:
                        ropts.pop('short-id', None)
                        ropts.pop('shortId', None)

    def _load_vmess(self, url: str, dt: str):
        try:
            content = b64decodes(dt)
            v = json.loads(content)
            cipher = str(v.get('scy') or '').strip().lower()
            if cipher not in ('auto', 'aes-128-gcm', 'chacha20-poly1305', 'none', 'zero'):
                cipher = 'auto'
            port_raw = v.get('port')
            port_val = int(port_raw) if port_raw not in (None, '') else 0
            aid_raw = v.get('aid')
            aid_val = int(aid_raw) if aid_raw not in (None, '') else 0

            self.data = {
                'name': v.get('ps', 'vmess'),
                'server': v.get('add'),
                'port': port_val,
                'type': 'vmess',
                'uuid': v.get('id'),
                'alterId': aid_val,
                'cipher': cipher,
                'network': v.get('net', 'tcp'),
                'tls': v.get('tls') == 'tls',
                'sni': v.get('sni'),
                'udp': True
            }
            if v.get('net') == 'ws':
                self.data['ws-opts'] = {
                    'path': v.get('path', '/'),
                    'headers': {'Host': v.get('host', '')}
                }
            elif v.get('net') == 'grpc':
                self.data['grpc-opts'] = {'grpc-service-name': v.get('path', '')}
        except Exception:
            pass

    def _load_ss(self, url: str, dt: str):
        # Format 1: ss://base64(cipher:password)@server:port#name
        # Format 2: ss://base64(cipher:password@server:port)[?plugin=...]#name (SIP002)
        try:
            if '#' in dt:
                dt, name = dt.split('#', 1)
                self.data['name'] = unquote(name)
            
            # 解析 query 参数（如 plugin）
            query_params = {}
            if '?' in dt:
                dt, query = dt.split('?', 1)
                query_params = dict(parse_qsl(query))

            # 如果未解码前不含 @，尝试整串 Base64 解码 (SIP002 标准)
            if '@' not in dt:
                decoded = b64decodes_safe(dt)
                if '@' in decoded:
                    dt = decoded

            if '@' in dt:
                userinfo, serverinfo = dt.split('@', 1)
                if ':' not in userinfo:
                    userinfo = b64decodes_safe(userinfo)
                
                if ':' in userinfo and ':' in serverinfo:
                    cipher, password = userinfo.split(':', 1)
                    # 处理可能带端口的 serverinfo（支持 IPv6 [::1]:port）
                    server, port_str = serverinfo.rsplit(':', 1)
                    server = server.strip('[]')
                    
                    self.data.update({
                        'type': 'ss',
                        'server': server,
                        'port': int(port_str),
                        'cipher': cipher,
                        'password': password,
                        'udp': True
                    })
                    
                    # 支持 SIP003 插件解析（如 v2ray-plugin / obfs）
                    if 'plugin' in query_params:
                        plugin_raw = query_params['plugin']
                        if ';' in plugin_raw:
                            parts = plugin_raw.split(';')
                            p_name = parts[0].strip()
                            if p_name in ('obfs-local', 'simple-obfs'):
                                p_name = 'obfs'
                            
                            p_opts = {}
                            for part in parts[1:]:
                                if not part: continue
                                if '=' in part:
                                    k, v = part.split('=', 1)
                                    k, v = k.strip(), v.strip()
                                    if k in ('tls', 'skip-cert-verify', 'mux'):
                                        p_opts[k] = (v.lower() in ('1', 'true', 'yes') or (k == 'mux' and v not in ('0', 'false', 'no', '')))
                                    else:
                                        p_opts[k] = v
                                else:
                                    flag = part.strip()
                                    if flag in ('tls', 'skip-cert-verify', 'mux'):
                                        p_opts[flag] = True
                                    elif flag:
                                        p_opts['mode'] = flag
                                        
                            if p_name:
                                self.data['plugin'] = p_name
                                if p_opts:
                                    self.data['plugin-opts'] = p_opts
                        else:
                            p_name = plugin_raw.strip()
                            if p_name in ('obfs-local', 'simple-obfs'):
                                p_name = 'obfs'
                            self.data['plugin'] = p_name
        except Exception:
            pass

    def _load_trojan(self, url: str, dt: str):
        try:
            parsed = urlparse(url)
            self.data = {
                'name': unquote(parsed.fragment),
                'server': parsed.hostname,
                'port': parsed.port or 443,
                'type': 'trojan',
                'password': unquote(parsed.username or ""),
                'tls': True,
                'udp': True
            }
            # Query params
            if parsed.query:
                params = dict(parse_qsl(parsed.query))
                if 'sni' in params: self.data['sni'] = params['sni']
                if 'allowInsecure' in params: self.data['skip-cert-verify'] = params['allowInsecure'] == '1'
                if 'security' in params:
                    if params['security'] == 'none':
                        self.data['tls'] = False
                    elif params['security'] in ('tls', 'reality'):
                        self.data['tls'] = True
                if 'fp' in params: self.data['client-fingerprint'] = params['fp']
                if 'type' in params: self.data['network'] = params['type']
                
                # Reality options
                if 'pbk' in params:
                    self.data['tls'] = True
                    self.data['reality-opts'] = {'public-key': params['pbk']}
                    sid = self._validate_short_id(params.get('sid') or params.get('shortId'))
                    if sid:
                        self.data['reality-opts']['short-id'] = sid
        except Exception:
            pass

    def _load_vless(self, url: str, dt: str):
        try:
            parsed = urlparse(url)
            self.data = {
                'name': unquote(parsed.fragment),
                'server': parsed.hostname,
                'port': parsed.port or 443,
                'type': 'vless',
                'uuid': unquote(parsed.username or ""),
                'tls': False,
                'udp': True
            }
            if parsed.query:
                params = dict(parse_qsl(parsed.query))
                if 'sni' in params: self.data['servername'] = params['sni']
                if 'security' in params:
                    if params['security'] in ('tls', 'reality'):
                        self.data['tls'] = True
                if 'flow' in params: self.data['flow'] = params['flow']
                if 'fp' in params: self.data['client-fingerprint'] = params['fp']
                if 'type' in params: self.data['network'] = params['type']
                if 'path' in params:
                    if params.get('type') == 'ws':
                        self.data['ws-opts'] = {'path': params['path']}
                    elif params.get('type') == 'grpc':
                        self.data['grpc-opts'] = {'grpc-service-name': params['path']}
                
                # Reality options
                if 'pbk' in params:
                    self.data['tls'] = True
                    self.data['reality-opts'] = {'public-key': params['pbk']}
                    sid = self._validate_short_id(params.get('sid') or params.get('shortId'))
                    if sid:
                        self.data['reality-opts']['short-id'] = sid
        except Exception:
            pass

    def _load_hysteria2(self, url: str, dt: str):
        try:
            parsed = urlparse(url)
            self.data = {
                'name': unquote(parsed.fragment),
                'server': parsed.hostname,
                'port': parsed.port or 443,
                'type': 'hysteria2',
                'password': unquote(parsed.username or ""),
                'udp': True
            }
            if parsed.query:
                params = dict(parse_qsl(parsed.query))
                if 'sni' in params: self.data['sni'] = params['sni']
                
                # 只有当 obfs 存在且 obfs-password 不为空时才保留 obfs 混淆设置
                # 避免产生有 obfs 但无 obfs-password 的缺陷节点导致 Clash 抛出 missing obfs password 错误
                obfs_type = params.get('obfs')
                if obfs_type and obfs_type != 'none':
                    obfs_pwd = params.get('obfs-password') or params.get('obfs_password')
                    if obfs_pwd:
                        self.data['obfs'] = obfs_type
                        self.data['obfs-password'] = obfs_pwd
        except Exception:
            pass

    def to_clash(self) -> Dict[str, Any]:
        return {k: v for k, v in self.data.items() if not k.startswith('_')}

    def to_url(self) -> str:
        t = self.type.lower()
        tag = quote(self.name)
        server = self.data.get('server', '')
        port = self.data.get('port', '')

        if t == 'ss':
            cipher = self.data.get('cipher', '')
            pwd = self.data.get('password', '')
            userinfo = b64encodes(f"{cipher}:{pwd}")
            return f"ss://{userinfo}@{server}:{port}#{tag}"

        elif t == 'vmess':
            ws_opts = self.data.get('ws-opts') or {}
            ws_headers = ws_opts.get('headers') or {}
            grpc_opts = self.data.get('grpc-opts') or {}

            v_json = {
                "v": "2",
                "ps": self.name,
                "add": server,
                "port": str(port),
                "id": self.data.get('uuid', ''),
                "aid": str(self.data.get('alterId', 0)),
                "scy": self.data.get('cipher', 'auto'),
                "net": self.data.get('network', 'tcp'),
                "type": "none",
                "host": ws_headers.get('Host', '') or self.data.get('sni', '') or '',
                "path": ws_opts.get('path', '') or grpc_opts.get('grpc-service-name', '') or '',
                "tls": "tls" if self.data.get('tls') else "",
                "sni": self.data.get('sni') or self.data.get('servername', '') or ''
            }
            return "vmess://" + b64encodes(json.dumps(v_json, ensure_ascii=False))

        elif t == 'vless':
            uuid = self.data.get('uuid', '')
            query = []
            if self.data.get('tls'):
                query.append("security=" + ("reality" if self.data.get('reality-opts') else "tls"))
            if self.data.get('servername'):
                query.append("sni=" + quote(str(self.data.get('servername'))))
            if self.data.get('network'):
                query.append("type=" + str(self.data.get('network')))
            if self.data.get('flow'):
                query.append("flow=" + str(self.data.get('flow')))
            if self.data.get('client-fingerprint'):
                query.append("fp=" + str(self.data.get('client-fingerprint')))
            ws_opts = self.data.get('ws-opts') or {}
            ws_path = ws_opts.get('path')
            if ws_path:
                query.append("path=" + quote(ws_path))
            grpc_opts = self.data.get('grpc-opts') or {}
            grpc_service = grpc_opts.get('grpc-service-name')
            if grpc_service:
                query.append("path=" + quote(grpc_service))
            ropts = self.data.get('reality-opts') or {}
            if ropts:
                if ropts.get('public-key'): query.append("pbk=" + quote(str(ropts['public-key'])))
                if ropts.get('short-id'): query.append("sid=" + quote(str(ropts['short-id'])))
            qstr = "?" + "&".join(query) if query else ""
            return f"vless://{uuid}@{server}:{port}{qstr}#{tag}"

        elif t == 'trojan':
            pwd = quote(str(self.data.get('password', '')))
            query = []
            if self.data.get('sni'):
                query.append("sni=" + quote(str(self.data.get('sni'))))
            if self.data.get('network'):
                query.append("type=" + str(self.data.get('network')))
            if self.data.get('skip-cert-verify'):
                query.append("allowInsecure=1")
            ropts = self.data.get('reality-opts') or {}
            if ropts:
                query.append("security=reality")
                if ropts.get('public-key'): query.append("pbk=" + quote(str(ropts['public-key'])))
                if ropts.get('short-id'): query.append("sid=" + quote(str(ropts['short-id'])))
            qstr = "?" + "&".join(query) if query else ""
            return f"trojan://{pwd}@{server}:{port}{qstr}#{tag}"

        elif t in ('hysteria2', 'hy2'):
            pwd = quote(str(self.data.get('password', '')))
            query = []
            if self.data.get('sni'):
                query.append("sni=" + quote(str(self.data.get('sni'))))
            if self.data.get('obfs'):
                query.append("obfs=" + str(self.data.get('obfs')))
            if self.data.get('obfs-password'):
                query.append("obfs-password=" + str(self.data.get('obfs-password')))
            qstr = "?" + "&".join(query) if query else ""
            return f"hy2://{pwd}@{server}:{port}{qstr}#{tag}"

        return ""

    def get_identity(self) -> str:
        """建立精确且不区分大小写的唯一标识 (Identity)，防止误删或漏去重"""
        server = str(self.data.get('server', '')).strip().lower()
        port = str(self.data.get('port', '')).strip()
        t = str(self.type).strip().lower()
        
        ident_parts = [t, server, port]
        
        # 1. 认证信息 (UUID 转小写, Password 保持原样)
        if self.data.get('uuid'):
            ident_parts.append(str(self.data['uuid']).strip().lower())
        elif self.data.get('password'):
            ident_parts.append(str(self.data['password']).strip())
            
        # 2. 加密方式 (针对 Shadowsocks 等)
        if self.data.get('cipher'):
            ident_parts.append(f"cipher:{str(self.data['cipher']).lower()}")
        
        # 3. 传输层路径与 Host 标头 (区分共享 CDN IP 的不同节点)
        ws_opts = self.data.get('ws-opts') or {}
        if ws_opts.get('path'):
            ident_parts.append(f"ws:{ws_opts['path']}")
        ws_headers = ws_opts.get('headers') or {}
        ws_host = ws_headers.get('Host') or ws_headers.get('host')
        if ws_host:
            ident_parts.append(f"wshost:{str(ws_host).lower()}")
        
        grpc_opts = self.data.get('grpc-opts') or {}
        grpc_service = grpc_opts.get('grpc-service-name')
        if grpc_service:
            ident_parts.append(f"grpc:{grpc_service}")
        
        # 4. 域名识别 (SNI / servername 统一转小写)
        sni = self.data.get('sni') or self.data.get('servername')
        if sni:
            ident_parts.append(f"sni:{str(sni).lower()}")
        
        # 5. Reality 公钥 (如果有)
        ropts = self.data.get('reality-opts') or {}
        pbk = ropts.get('public-key')
        if pbk:
            ident_parts.append(f"pbk:{pbk}")
        
        # 6. 流控信息 (flow: xtls-rprx-vision)
        flow = self.data.get('flow')
        if flow:
            ident_parts.append(f"flow:{flow}")

        return ":".join(ident_parts)

    def __hash__(self):
        return hash(self.get_identity())

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.get_identity() == other.get_identity()
