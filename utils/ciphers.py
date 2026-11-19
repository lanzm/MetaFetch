import base64
from urllib.parse import unquote
from typing import Optional

# Shadowsocks 常见非标准别名 -> Clash / Mihomo 官方标准名称映射表
SS_CIPHER_ALIASES: dict[str, str] = {
    # ChaCha20-Poly1305 变体（常见漏写 ietf）
    'chacha20-poly1305': 'chacha20-ietf-poly1305',
    'chacha20-ietf-poly-1305': 'chacha20-ietf-poly1305',
    'xchacha20-poly1305': 'xchacha20-ietf-poly1305',
    'xchacha20-ietf-poly-1305': 'xchacha20-ietf-poly1305',

    # AES-GCM 常见缺少连字符或别名
    'aes128-gcm': 'aes-128-gcm',
    'aes192-gcm': 'aes-192-gcm',
    'aes256-gcm': 'aes-256-gcm',

    # 常见流加密别名
    'rc4md5': 'rc4-md5',
    'rc4_md5': 'rc4-md5',
}

# Clash / Mihomo 内核支持的合法 Shadowsocks 加密算法集合
VALID_SS_CIPHERS: set[str] = {
    # AEAD Ciphers
    'aes-128-gcm',
    'aes-192-gcm',
    'aes-256-gcm',
    'chacha20-ietf-poly1305',
    'xchacha20-ietf-poly1305',

    # Shadowsocks 2022
    '2022-blake3-aes-128-gcm',
    '2022-blake3-aes-256-gcm',
    '2022-blake3-chacha20-poly1305',

    # Stream Ciphers (Legacy)
    'aes-128-cfb',
    'aes-192-cfb',
    'aes-256-cfb',
    'aes-128-ctr',
    'aes-192-ctr',
    'aes-256-ctr',
    'rc4-md5',
    'chacha20-ietf',
    'chacha20',
    'xchacha20',
}


def normalize_ss_cipher(cipher: Optional[str]) -> str:
    """
    归一化 Shadowsocks 加密算法名称。
    去除首尾空格、转换为小写，并将常见非标准别名（如 chacha20-poly1305）映射为标准名称。
    """
    if not cipher:
        return ''
    c = str(cipher).strip().lower()
    return SS_CIPHER_ALIASES.get(c, c)


def is_valid_ss_cipher(cipher: Optional[str]) -> bool:
    """
    校验加密算法是否为 Clash / Mihomo 支持的合法 Shadowsocks 加密方式。
    """
    if not cipher:
        return False
    norm = normalize_ss_cipher(cipher)
    return norm in VALID_SS_CIPHERS


# Shadowsocks 2022 官方算法对应的密钥字节长度要求
# 128 位算法需 16 字节密钥，256 位与 ChaCha20 算法需 32 字节密钥
SS_2022_KEY_LENGTHS: dict[str, int] = {
    '2022-blake3-aes-128-gcm': 16,
    '2022-blake3-aes-256-gcm': 32,
    '2022-blake3-chacha20-poly1305': 32,
}


def validate_and_normalize_ss_2022_key(cipher: Optional[str], password: Optional[str]) -> Optional[str]:
    """
    针对 Shadowsocks 2022 (SIP022) 协议进行密钥校验与格式规范化：
    1. 还原 URL 编码（如 %3D -> =），防止订阅转换或客户端导出时二次转义。
    2. 校验 Base64 语法并自动补全可能缺失的 '=' 填充符。
    3. 校验解码后的二进制密钥字节长度是否严格符合规范要求（16 字节或 32 字节）。
    4. 支持单用户密钥及以 ':' 分隔的多用户密钥 (server_key:user_key)。
    若合法则返回规范化后的标准 Base64 密钥字符串，否则返回 None（供下游直接剔除缺陷节点）。
    """
    if not cipher or not password:
        return None
    cipher_norm = normalize_ss_cipher(cipher)
    req_len = SS_2022_KEY_LENGTHS.get(cipher_norm)
    if not req_len:
        return None

    raw_pwd = unquote(str(password)).strip()
    if not raw_pwd:
        return None

    keys = raw_pwd.split(':')
    norm_keys = []
    for idx, key in enumerate(keys):
        k = key.strip()
        if not k:
            return None
        # 补齐可能在传输过程中丢失的 Base64 尾部 padding
        missing_padding = (4 - len(k) % 4) % 4
        k_padded = k + ('=' * missing_padding)
        try:
            # 严格使用标准 Base64 解码，确保不含非法字符（如残留的 % 等）
            decoded = base64.b64decode(k_padded, validate=True)
            # 主服务密钥必须满足算法指定长度；多用户分密钥为 16 或 32 字节
            if idx == 0:
                if len(decoded) != req_len:
                    return None
            else:
                if len(decoded) not in (16, 32):
                    return None
            norm_keys.append(k_padded)
        except Exception:
            return None

    return ":".join(norm_keys)
