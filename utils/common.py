import base64
import binascii

def b64encodes(s: str) -> str:
    """标准 Base64 编码"""
    return base64.b64encode(s.encode('utf-8')).decode('utf-8')

def b64decodes(s: str) -> str:
    """自动补齐 Padding 并支持标准与 URL-safe Base64 解码"""
    if not s:
        return ""
    s = s.strip()
    ss = s + '=' * ((4 - len(s) % 4) % 4)
    try:
        return base64.b64decode(ss.encode('utf-8')).decode('utf-8')
    except (UnicodeDecodeError, binascii.Error):
        try:
            return base64.urlsafe_b64decode(ss.encode('utf-8')).decode('utf-8')
        except Exception:
            return ""

def b64decodes_safe(s: str) -> str:
    """URL-safe Base64 解码"""
    if not s:
        return ""
    s = s.strip()
    ss = s + '=' * ((4 - len(s) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(ss.encode('utf-8')).decode('utf-8')
    except (UnicodeDecodeError, binascii.Error):
        return ""
