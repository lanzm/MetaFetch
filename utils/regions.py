import re
from typing import Dict, Any, Optional, Tuple, List

REGIONS_DB: Dict[str, Dict[str, Any]] = {
    'HK': {'name': '香港', 'emoji': '🇭🇰', 'keywords': ['HK', 'Hong Kong', 'HKG']},
    'TW': {'name': '台湾', 'emoji': '🇹🇼', 'keywords': ['TW', 'Taiwan', 'TWN', 'Taipei', '台北']},
    'JP': {'name': '日本', 'emoji': '🇯🇵', 'keywords': ['JP', 'Japan', 'JPN', 'Tokyo', 'Osaka', '东京', '大阪']},
    'US': {'name': '美国', 'emoji': '🇺🇸', 'keywords': ['US', 'United States', 'USA', 'Los Angeles', 'New York', 'Silicon Valley', '洛杉矶', '纽约', '硅谷']},
    'SG': {'name': '新加坡', 'emoji': '🇸🇬', 'keywords': ['SG', 'Singapore', 'SGP', '狮城']},
    'KR': {'name': '韩国', 'emoji': '🇰🇷', 'keywords': ['KR', 'Korea', 'KOR', 'Seoul', '首尔']},
    'DE': {'name': '德国', 'emoji': '🇩🇪', 'keywords': ['DE', 'Germany', 'DEU', 'Frankfurt', '法兰克福']},
    'GB': {'name': '英国', 'emoji': '🇬🇧', 'keywords': ['GB', 'UK', 'United Kingdom', 'London', '伦敦']},
    'FR': {'name': '法国', 'emoji': '🇫🇷', 'keywords': ['FR', 'France', 'FRA', 'Paris', '巴黎', '🇨🇵']},
    'RU': {'name': '俄罗斯', 'emoji': '🇷🇺', 'keywords': ['RU', 'Russia', 'RUS', 'Moscow', '莫斯科']},
    'CA': {'name': '加拿大', 'emoji': '🇨🇦', 'keywords': ['CA', 'Canada', 'CAN', 'Toronto', '多伦多']},
    'VN': {'name': '越南', 'emoji': '🇻🇳', 'keywords': ['VN', 'Vietnam', 'VNM']},
    'NL': {'name': '荷兰', 'emoji': '🇳🇱', 'keywords': ['NL', 'Netherlands', 'NLD', 'Amsterdam', '阿姆斯特丹']},
    'CH': {'name': '瑞士', 'emoji': '🇨🇭', 'keywords': ['CH', 'Switzerland', 'CHE', 'Zurich', '苏黎世']},
    'IN': {'name': '印度', 'emoji': '🇮🇳', 'keywords': ['IN', 'India', 'IND', 'Mumbai']},
    'TR': {'name': '土耳其', 'emoji': '🇹🇷', 'keywords': ['TR', 'Turkey', 'TUR', 'Istanbul', '伊斯坦布尔']},
    'AU': {'name': '澳大利亚', 'emoji': '🇦🇺', 'keywords': ['AU', 'Australia', 'AUS', 'Sydney', 'Melbourne', '悉尼', '墨尔本']},
    'TH': {'name': '泰国', 'emoji': '🇹🇭', 'keywords': ['TH', 'Thailand', 'Bangkok', '曼谷']},
    'PH': {'name': '菲律宾', 'emoji': '🇵🇭', 'keywords': ['PH', 'Philippines', 'Manila', '马尼拉']},
    'MY': {'name': '马来西亚', 'emoji': '🇲🇾', 'keywords': ['MY', 'Malaysia', 'Kuala Lumpur', '吉隆坡']},
    'ID': {'name': '印尼', 'emoji': '🇮🇩', 'keywords': ['ID', 'Indonesia', 'Jakarta', '雅加达']},
    'BR': {'name': '巴西', 'emoji': '🇧🇷', 'keywords': ['BR', 'Brazil', 'Sao Paulo']},
    'AR': {'name': '阿根廷', 'emoji': '🇦🇷', 'keywords': ['AR', 'Argentina', 'Buenos Aires']},
    'MX': {'name': '墨西哥', 'emoji': '🇲🇽', 'keywords': ['MX', 'Mexico']},
    'IT': {'name': '意大利', 'emoji': '🇮🇹', 'keywords': ['IT', 'Italy', 'Milan', 'Rome', '米兰', '罗马']},
    'ES': {'name': '西班牙', 'emoji': '🇪🇸', 'keywords': ['ES', 'Spain', 'Madrid', '马德里']},
    'CN': {'name': '中国', 'emoji': '🇨🇳', 'keywords': ['CN', 'China', 'CHN']},
    'RO': {'name': '罗马尼亚', 'emoji': '🇷🇴', 'keywords': ['RO', 'Romania', 'ROU', 'Bucharest']},
    'FI': {'name': '芬兰', 'emoji': '🇫🇮', 'keywords': ['FI', 'Finland', 'FIN', 'Helsinki', '赫尔辛基']},
    
    # 扩展新增常用国家
    'IE': {'name': '爱尔兰', 'emoji': '🇮🇪', 'keywords': ['IE', 'Ireland', 'IRL', 'Dublin']},
    'SE': {'name': '瑞典', 'emoji': '🇸🇪', 'keywords': ['SE', 'Sweden', 'SWE', 'Stockholm']},
    'PL': {'name': '波兰', 'emoji': '🇵🇱', 'keywords': ['PL', 'Poland', 'POL', 'Warsaw']},
    'CZ': {'name': '捷克', 'emoji': '🇨🇿', 'keywords': ['CZ', 'Czech', 'Czechia', 'Prague']},
    'AT': {'name': '奥地利', 'emoji': '🇦🇹', 'keywords': ['AT', 'Austria', 'AUT', 'Vienna', '维也纳']},
    'AE': {'name': '阿联酋', 'emoji': '🇦🇪', 'keywords': ['AE', 'UAE', 'Dubai', '迪拜']},
    'KZ': {'name': '哈萨克斯坦', 'emoji': '🇰🇿', 'keywords': ['KZ', 'Kazakhstan']},
    'CY': {'name': '塞浦路斯', 'emoji': '🇨🇾', 'keywords': ['CY', 'Cyprus']},
    'UA': {'name': '乌克兰', 'emoji': '🇺🇦', 'keywords': ['UA', 'Ukraine', 'UKR', 'Kyiv']},
    'NO': {'name': '挪威', 'emoji': '🇳🇴', 'keywords': ['NO', 'Norway', 'NOR', 'Oslo']},
    'DK': {'name': '丹麦', 'emoji': '🇩🇰', 'keywords': ['DK', 'Denmark', 'DNK', 'Copenhagen']},
    'PT': {'name': '葡萄牙', 'emoji': '🇵🇹', 'keywords': ['PT', 'Portugal', 'PRT', 'Lisbon']},
    'HU': {'name': '匈牙利', 'emoji': '🇭🇺', 'keywords': ['HU', 'Hungary', 'HUN', 'Budapest']},
    'BG': {'name': '保加利亚', 'emoji': '🇧🇬', 'keywords': ['BG', 'Bulgaria', 'BGR', 'Sofia']},
    'ZA': {'name': '南非', 'emoji': '🇿🇦', 'keywords': ['ZA', 'South Africa', 'ZAF']},
    'BZ': {'name': '伯利兹', 'emoji': '🇧🇿', 'keywords': ['BZ', 'Belize']},
}

# 预编译多级匹配规则（模块级单例缓存，极速匹配）
_EMOJI_MAP = {info['emoji']: key for key, info in REGIONS_DB.items() if info.get('emoji')}
_NAME_MAP = {info['name']: key for key, info in REGIONS_DB.items() if info.get('name')}

_LONG_KEYWORDS: List[Tuple[str, str]] = []
_SHORT_KEYWORD_PATTERNS: List[Tuple[str, re.Pattern]] = []

for key, info in REGIONS_DB.items():
    for kw in info['keywords']:
        if len(kw) > 2:
            _LONG_KEYWORDS.append((key, kw.lower()))
        else:
            # 2 字母短代码安全非字母边界匹配（避免匹配在单词中间）
            pat = re.compile(rf'(?<![a-zA-Z]){re.escape(kw)}(?![a-zA-Z])', re.IGNORECASE)
            _SHORT_KEYWORD_PATTERNS.append((key, pat))

def match_region(name: str) -> Optional[str]:
    """
    统一的地区识别算法，分 4 级瀑布流精准匹配：
    1. Emoji 国旗优先匹配 (最精准)
    2. 中文名称匹配
    3. 长关键词与城市匹配
    4. 2 字母短代码边界安全匹配
    """
    if not name:
        return None

    # Level 1: Emoji
    for emoji, key in _EMOJI_MAP.items():
        if emoji in name:
            return key

    # Level 2: 中文名
    for cname, key in _NAME_MAP.items():
        if cname in name:
            return key

    # Level 3: 长关键词与城市名
    name_lower = name.lower()
    for key, kw_lower in _LONG_KEYWORDS:
        if kw_lower in name_lower:
            return key

    # Level 4: 2 字母短代码
    for key, pat in _SHORT_KEYWORD_PATTERNS:
        if pat.search(name):
            return key

    return None
