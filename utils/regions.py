import re
from typing import Dict, Any, Optional, Tuple, List

REGIONS_DB: Dict[str, Dict[str, Any]] = {
    'HK': {'name': '香港', 'emoji': '🇭🇰', 'keywords': ['HK', 'Hong Kong', 'HongKong', 'HKG', '九龙', 'Kowloon']},
    'TW': {'name': '台湾', 'emoji': '🇹🇼', 'keywords': ['TW', 'Taiwan', 'TWN', 'Taipei', '台北', 'Taichung', '台中', 'Kaohsiung', '高雄']},
    'JP': {'name': '日本', 'emoji': '🇯🇵', 'keywords': ['JP', 'Japan', 'JPN', 'Tokyo', 'Osaka', '东京', '大阪', 'Nagoya', '名古屋', 'Fukuoka', '福冈', 'Kawasaki', '川崎', 'Yokohama', '横滨', '千叶', 'Chiba', '埼玉', 'Saitama', '神户', 'Kobe']},
    'US': {'name': '美国', 'emoji': '🇺🇸', 'keywords': ['US', 'United States', 'UnitedStates', 'USA', 'Los Angeles', 'New York', 'Silicon Valley', '洛杉矶', '纽约', '硅谷', 'Seattle', '西雅图', 'Chicago', '芝加哥', 'San Jose', '圣何塞', 'Dallas', '达拉斯', 'Miami', '迈阿密', 'Phoenix', '凤凰城', '菲尼克斯', 'Atlanta', '亚特兰大', 'Houston', '休斯顿', 'Denver', '丹佛', 'Ashburn', '阿什本', 'Portland', '波特兰', 'Santa Clara', '波士顿', 'Boston', '拉斯维加斯', 'Las Vegas']},
    'SG': {'name': '新加坡', 'emoji': '🇸🇬', 'keywords': ['SG', 'Singapore', 'SGP', '狮城', '星加坡']},
    'KR': {'name': '韩国', 'emoji': '🇰🇷', 'keywords': ['KR', 'Korea', 'KOR', 'South Korea', 'SouthKorea', 'Seoul', '首尔', 'Busan', '釜山', 'Incheon', '仁川', '春川', 'Chuncheon', '大田', 'Daejeon']},
    'DE': {'name': '德国', 'emoji': '🇩🇪', 'keywords': ['DE', 'Germany', 'DEU', 'Frankfurt', '法兰克福', 'Berlin', '柏林', 'Munich', '慕尼黑', 'Dusseldorf', '杜塞尔多夫', '汉堡', 'Hamburg', '斯图加特', 'Stuttgart']},
    'GB': {'name': '英国', 'emoji': '🇬🇧', 'keywords': ['GB', 'UK', 'United Kingdom', 'UnitedKingdom', 'London', '伦敦', 'Manchester', '曼彻斯特', '伯明翰', 'Birmingham']},
    'FR': {'name': '法国', 'emoji': '🇫🇷', 'keywords': ['FR', 'France', 'FRA', 'Paris', '巴黎', 'Marseille', '马赛']},
    'RU': {'name': '俄罗斯', 'emoji': '🇷🇺', 'keywords': ['RU', 'Russia', 'RUS', 'Moscow', '莫斯科', '圣彼得堡', 'Saint Petersburg', 'St. Petersburg']},
    'CA': {'name': '加拿大', 'emoji': '🇨🇦', 'keywords': ['CA', 'Canada', 'CAN', 'Toronto', '多伦多', 'Vancouver', '温哥华', 'Montreal', '蒙特利尔']},
    'VN': {'name': '越南', 'emoji': '🇻🇳', 'keywords': ['VN', 'Vietnam', 'VNM']},
    'NL': {'name': '荷兰', 'emoji': '🇳🇱', 'keywords': ['NL', 'Netherlands', 'NLD', 'Amsterdam', '阿姆斯特丹']},
    'CH': {'name': '瑞士', 'emoji': '🇨🇭', 'keywords': ['CH', 'Switzerland', 'CHE', 'Zurich', '苏黎世']},
    'IN': {'name': '印度', 'emoji': '🇮🇳', 'keywords': ['IN', 'India', 'IND', 'Mumbai']},
    'TR': {'name': '土耳其', 'emoji': '🇹🇷', 'keywords': ['TR', 'Turkey', 'TUR', 'Istanbul', '伊斯坦布尔']},
    'AU': {'name': '澳大利亚', 'emoji': '🇦🇺', 'keywords': ['AU', 'Australia', 'AUS', 'Sydney', 'Melbourne', '悉尼', '墨尔本', 'Brisbane', '布里斯班', 'Perth', '珀斯']},
    'NZ': {'name': '新西兰', 'emoji': '🇳🇿', 'keywords': ['NZ', 'New Zealand', 'NewZealand', 'NZL', 'Auckland', '奥克兰', 'Wellington', '惠灵顿', 'Christchurch', '基督城']},
    'TH': {'name': '泰国', 'emoji': '🇹🇭', 'keywords': ['TH', 'Thailand', 'Bangkok', '曼谷']},
    'PH': {'name': '菲律宾', 'emoji': '🇵🇭', 'keywords': ['PH', 'Philippines', 'Manila', '马尼拉']},
    'MY': {'name': '马来西亚', 'emoji': '🇲🇾', 'keywords': ['MY', 'Malaysia', 'Kuala Lumpur', '吉隆坡']},
    'ID': {'name': '印尼', 'emoji': '🇮🇩', 'keywords': ['ID', 'Indonesia', 'Jakarta', '雅加达']},
    'BR': {'name': '巴西', 'emoji': '🇧🇷', 'keywords': ['BR', 'Brazil', 'Sao Paulo', '圣保罗']},
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
    'AE': {'name': '阿联酋', 'emoji': '🇦🇪', 'keywords': ['AE', 'UAE', 'Dubai', '迪拜', '阿布扎比', 'Abu Dhabi']},
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
    'EE': {'name': '爱沙尼亚', 'emoji': '🇪🇪', 'keywords': ['EE', 'Estonia', 'EST', 'Tallinn', '塔林']},
}

# 预编译多级匹配规则（模块级单例缓存，极速匹配）
REGION_NAMES: Dict[str, str] = {
    code: f"{info['emoji']} {info['name']}"
    for code, info in REGIONS_DB.items()
}

_EMOJI_MAP = {info['emoji']: key for key, info in REGIONS_DB.items() if info.get('emoji')}
_EMOJI_MAP['🇨🇵'] = 'FR'  # 兼容法国海外属地克利珀顿岛旗帜

_CHINESE_KEYWORDS: List[Tuple[str, str]] = []
_LONG_KEYWORDS: List[Tuple[str, str]] = []
_CODE_PATTERNS: List[Tuple[re.Pattern, str]] = []

# 容易与英语高频单词/缩写发生冲突的短代码（必须严格大写匹配，且 ID 排除 ID: 或 ID= 等标号）
AMBIGUOUS_CODES = {'NO', 'ID', 'IN', 'IT', 'AT', 'US', 'MY', 'CAN', 'EE'}

for key, info in REGIONS_DB.items():
    if info.get('name'):
        _CHINESE_KEYWORDS.append((info['name'], key))
    for kw in info['keywords']:
        if re.search(r'[\u4e00-\u9fa5]', kw):
            _CHINESE_KEYWORDS.append((kw, key))
        elif len(kw) >= 4:
            _LONG_KEYWORDS.append((kw.lower(), key))
        else:
            # 2 字母或 3 字母短代码（如 HK, JP, US, USA, AUS, IND, RUS 等）
            if kw.upper() in AMBIGUOUS_CODES:
                if kw.upper() == 'ID':
                    pat = re.compile(rf'(?<![a-zA-Z]){kw}(?![a-zA-Z:=0-9])')
                    pat_delim = re.compile(rf'(?:^|[\-_|/:\d\[\(])({re.escape(kw.lower())})(?=[\-_|/:\d\]\)]|$)(?![a-zA-Z:=0-9])')
                else:
                    pat = re.compile(rf'(?<![a-zA-Z]){kw}(?![a-zA-Z])')
                    # 小写时必须紧邻代理符号或数字边界（如 us-01, us_01, [us], us|01），避免误伤英文单词（如 join us）
                    pat_delim = re.compile(rf'(?:^|[\-_|/:\d\[\(])({re.escape(kw.lower())})(?=[\-_|/:\d\]\)]|$)')
                _CODE_PATTERNS.append((pat, key))
                _CODE_PATTERNS.append((pat_delim, key))
            else:
                pat = re.compile(rf'(?<![a-zA-Z]){re.escape(kw)}(?![a-zA-Z])', re.IGNORECASE)
                _CODE_PATTERNS.append((pat, key))

# 核心优化：按关键词长度倒序排列，优先匹配最长完整名称（例如 Austria 优先于 AUS，Indonesia 优先于 IND）
_CHINESE_KEYWORDS.sort(key=lambda x: len(x[0]), reverse=True)
_LONG_KEYWORDS.sort(key=lambda x: len(x[0]), reverse=True)

def match_region(name: str) -> Optional[str]:
    """
    统一的地区识别算法（右侧优先 / 落地优先）：
    找出名称中出现的所有地区标识（国旗 Emoji、中文名与城市、英文全称、2/3字母短代码），
    取在字符串中最靠右（出现位置最大，即落地出口端）的匹配项。
    对于单国家节点，该位置为唯一位置，100% 自然兼容；对于中转多国家节点，精准匹配落地出口。
    """
    if not name:
        return None

    best_key = None
    best_pos = -1
    best_len = 0

    # Level 1: Emoji 国旗扫描（记录最靠右的 Emoji）
    for emoji, key in _EMOJI_MAP.items():
        pos = name.rfind(emoji)
        if pos != -1:
            if pos > best_pos or (pos == best_pos and len(emoji) > best_len):
                best_pos = pos
                best_len = len(emoji)
                best_key = key

    # Level 2: 中文名及中文城市扫描
    for cname, key in _CHINESE_KEYWORDS:
        pos = name.rfind(cname)
        if pos != -1:
            if pos > best_pos or (pos == best_pos and len(cname) > best_len):
                best_pos = pos
                best_len = len(cname)
                best_key = key

    # Level 3: 英文全称及完整城市名 (>=4 字符，不区分大小写)
    name_lower = name.lower()
    for kw_lower, key in _LONG_KEYWORDS:
        pos = name_lower.rfind(kw_lower)
        if pos != -1:
            if pos > best_pos or (pos == best_pos and len(kw_lower) > best_len):
                best_pos = pos
                best_len = len(kw_lower)
                best_key = key

    # Level 4: 2/3 字母短代码边界安全匹配
    for pat, key in _CODE_PATTERNS:
        for m in pat.finditer(name):
            pos = m.start(1) if m.lastindex else m.start()
            mlen = len(m.group(1)) if m.lastindex else (m.end() - m.start())
            if pos > best_pos or (pos == best_pos and mlen > best_len):
                best_pos = pos
                best_len = mlen
                best_key = key

    return best_key
