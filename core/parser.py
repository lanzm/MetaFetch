import json
import yaml
import traceback
from typing import Dict, Any, List, Union, Optional
from urllib.parse import urlparse, unquote, quote, parse_qsl
from utils.common import b64decodes, b64decodes_safe, b64encodes, b64encodes_safe

DEFAULT_UUID = '8' * 8 + '-8888' * 3 + '-' + '8' * 12
VMESS_TEMPLATE = {
    "v": "2", "ps": "", "add": "0.0.0.0", "port": "0", "aid": "0", "scy": "auto",
    "net": "tcp", "type": "none", "tls": "", "id": DEFAULT_UUID
}

class Node:
    def __init__(self, data: Union[Dict[str, Any], str]):
        self.data: Dict[str, Any] = {}
        if isinstance(data, dict):
            self.data = data.copy()
            self.type = data.get('type', 'unknown')
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
        if protocol == 'hy2': protocol = 'hysteria2'
        
        # 严格过滤非法协议（如 HTML 标签内嵌的 https 链接）
        allowed = ('vmess', 'vless', 'ss', 'trojan', 'hysteria2', 'ssr')
        if protocol.lower() not in allowed:
            return

        self.type = protocol.lower()
        loader = getattr(self, f'_load_{self.type}', None)
        if loader:
            loader(url, dt)
        else:
            # Fallback for recognized but not explicitly loaded protocols
            self.data['type'] = self.type
            if '#' in dt:
                self.data['name'] = unquote(dt.split('#')[-1])

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
            self.data = {
                'name': v.get('ps', 'vmess'),
                'server': v.get('add'),
                'port': int(v.get('port', 0)),
                'type': 'vmess',
                'uuid': v.get('id'),
                'alterId': int(v.get('aid', 0)),
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
        # Format: ss://base64(cipher:password)@server:port#name
        try:
            if '#' in dt:
                dt, name = dt.split('#', 1)
                self.data['name'] = unquote(name)
            
            if '@' in dt:
                userinfo, serverinfo = dt.split('@', 1)
                if ':' not in userinfo:
                    userinfo = b64decodes_safe(userinfo)
                cipher, password = userinfo.split(':', 1)
                server, port = serverinfo.split(':', 1)
                self.data.update({
                    'type': 'ss',
                    'server': server,
                    'port': int(port),
                    'cipher': cipher,
                    'password': password,
                    'udp': True
                })
        except Exception:
            pass

    def _load_trojan(self, url: str, dt: str):
        try:
            parsed = urlparse(url)
            self.data = {
                'name': unquote(parsed.fragment),
                'server': parsed.hostname,
                'port': parsed.port,
                'type': 'trojan',
                'password': unquote(parsed.username or ""),
                'udp': True
            }
            # Query params
            if parsed.query:
                params = dict(parse_qsl(parsed.query))
                if 'sni' in params: self.data['sni'] = params['sni']
                if 'allowInsecure' in params: self.data['skip-cert-verify'] = params['allowInsecure'] == '1'
                if 'security' in params:
                    if params['security'] in ('tls', 'reality'):
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
                'port': parsed.port,
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
        return self.data.copy()

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
                "host": self.data.get('ws-opts', {}).get('headers', {}).get('Host', '') or self.data.get('sni', '') or '',
                "path": self.data.get('ws-opts', {}).get('path', '') or self.data.get('grpc-opts', {}).get('grpc-service-name', '') or '',
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
            ws_path = self.data.get('ws-opts', {}).get('path')
            if ws_path:
                query.append("path=" + quote(ws_path))
            grpc_service = self.data.get('grpc-opts', {}).get('grpc-service-name')
            if grpc_service:
                query.append("path=" + quote(grpc_service))
            ropts = self.data.get('reality-opts')
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
            ropts = self.data.get('reality-opts')
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

    def to_singbox(self) -> Optional[Dict[str, Any]]:
        t = self.type.lower()
        server = self.data.get('server', '')
        port = self.data.get('port', 0)
        if not server or not port:
            return None

        sb_type = t
        if t == 'ss':
            sb_type = 'shadowsocks'
        elif t in ('hy2', 'hysteria2'):
            sb_type = 'hysteria2'

        outbound = {
            "type": sb_type,
            "tag": self.name,
            "server": server,
            "server_port": int(port)
        }

        tls_enabled = bool(self.data.get('tls'))
        sni = self.data.get('sni') or self.data.get('servername')
        insecure = bool(self.data.get('skip-cert-verify'))

        if t == 'ss':
            outbound['method'] = self.data.get('cipher', 'aes-128-gcm')
            outbound['password'] = self.data.get('password', '')

        elif t == 'vmess':
            outbound['uuid'] = self.data.get('uuid', '')
            outbound['security'] = self.data.get('cipher', 'auto')
            if self.data.get('alterId'):
                outbound['alter_id'] = int(self.data['alterId'])
            
            ws_opts = self.data.get('ws-opts')
            grpc_opts = self.data.get('grpc-opts')
            if ws_opts:
                outbound['transport'] = {
                    "type": "ws",
                    "path": ws_opts.get('path', '/'),
                    "headers": ws_opts.get('headers', {})
                }
            elif grpc_opts:
                outbound['transport'] = {
                    "type": "grpc",
                    "service_name": grpc_opts.get('grpc-service-name', '')
                }

        elif t == 'vless':
            outbound['uuid'] = self.data.get('uuid', '')
            if self.data.get('flow'):
                outbound['flow'] = self.data['flow']
            
            ws_opts = self.data.get('ws-opts')
            grpc_opts = self.data.get('grpc-opts')
            if ws_opts:
                outbound['transport'] = {
                    "type": "ws",
                    "path": ws_opts.get('path', '/'),
                    "headers": ws_opts.get('headers', {})
                }
            elif grpc_opts:
                outbound['transport'] = {
                    "type": "grpc",
                    "service_name": grpc_opts.get('grpc-service-name', '')
                }

        elif t == 'trojan':
            outbound['password'] = self.data.get('password', '')

        elif t in ('hysteria2', 'hy2'):
            outbound['type'] = 'hysteria2'
            outbound['password'] = self.data.get('password', '')
            tls_enabled = True
            if self.data.get('obfs'):
                outbound['obfs'] = {
                    "type": self.data['obfs'],
                    "password": self.data.get('obfs-password', '')
                }

        else:
            return None

        # TLS Configuration for Sing-box
        ropts = self.data.get('reality-opts')
        if tls_enabled or ropts:
            tls_cfg: Dict[str, Any] = {"enabled": True}
            if sni:
                tls_cfg["server_name"] = str(sni)
            if insecure:
                tls_cfg["insecure"] = True
            if ropts:
                reality_cfg: Dict[str, Any] = {"enabled": True}
                if ropts.get('public-key'):
                    reality_cfg["public_key"] = str(ropts['public-key'])
                if ropts.get('short-id'):
                    reality_cfg["short_id"] = str(ropts['short-id'])
                tls_cfg["reality"] = reality_cfg
                
                fp = self.data.get('client-fingerprint') or 'chrome'
                tls_cfg["utls"] = {
                    "enabled": True,
                    "fingerprint": str(fp)
                }
            outbound["tls"] = tls_cfg

        return outbound

    def __hash__(self):
        # 建立更精细的唯一标识 (Identity)，防止误删同 IP 不同路径的节点
        ident_parts = [
            str(self.type),
            str(self.data.get('server', '')),
            str(self.data.get('port', ''))
        ]
        
        # 1. 认证信息 (UUID / Password)
        auth = self.data.get('uuid') or self.data.get('password')
        if auth: ident_parts.append(str(auth))
        
        # 2. 传输层路径 (WS Path / gRPC Service Name)
        ws_path = self.data.get('ws-opts', {}).get('path')
        if ws_path: ident_parts.append(f"ws:{ws_path}")
        
        grpc_service = self.data.get('grpc-opts', {}).get('grpc-service-name')
        if grpc_service: ident_parts.append(f"grpc:{grpc_service}")
        
        # 3. 域名识别 (SNI / Host)
        sni = self.data.get('sni') or self.data.get('servername')
        if sni: ident_parts.append(f"sni:{sni}")
        
        # 4. Reality 公钥 (如果有)
        pbk = self.data.get('reality-opts', {}).get('public-key')
        if pbk: ident_parts.append(f"pbk:{pbk}")
        
        # 5. 流控信息 (flow: xtls-rprx-vision) - 非常关键，决定了性能差异
        flow = self.data.get('flow')
        if flow: ident_parts.append(f"flow:{flow}")

        identity = ":".join(ident_parts)
        return hash(identity)

    def __eq__(self, other):
        if not isinstance(other, Node): return False
        return hash(self) == hash(other)
