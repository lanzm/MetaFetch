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
                if 'obfs' in params: self.data['obfs'] = params['obfs']
                if 'obfs-password' in params: self.data['obfs-password'] = params['obfs-password']
        except Exception:
            pass

    def to_clash(self) -> Dict[str, Any]:
        return self.data.copy()

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
