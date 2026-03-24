import base64
import json
import binascii
from urllib.parse import urlparse, unquote, quote

def b64encodes(s: str) -> str:
    return base64.b64encode(s.encode('utf-8')).decode('utf-8')

def b64encodes_safe(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode('utf-8')).decode('utf-8')

def b64decodes(s: str) -> str:
    ss = s + '=' * ((4-len(s)%4)%4)
    try:
        return base64.b64decode(ss.encode('utf-8')).decode('utf-8')
    except (UnicodeDecodeError, binascii.Error):
        # Fail-safe or secondary try with urlsafe
        try:
            return base64.urlsafe_b64decode(ss.encode('utf-8')).decode('utf-8')
        except:
            return ""

def b64decodes_safe(s: str) -> str:
    ss = s + '=' * ((4-len(s)%4)%4)
    try:
        return base64.urlsafe_b64decode(ss.encode('utf-8')).decode('utf-8')
    except (UnicodeDecodeError, binascii.Error):
        return ""

def norm_url_fragment(url: str) -> str:
    if '#' in url:
        return unquote(url.split('#')[-1])
    return ""

def parse_url(url: str):
    # Custom URL parsing because standard urlparse might fail on some v2ray-style links
    if '://' not in url:
        return None
    scheme, rest = url.split('://', 1)
    # Standardize scheme
    if scheme == 'hy2': scheme = 'hysteria2'
    return scheme, rest
