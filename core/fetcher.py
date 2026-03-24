import httpx
import yaml
import asyncio
from typing import List, Dict, Any, Union
from core.parser import Node
from utils.common import b64decodes

class Fetcher:
    def __init__(self, timeout: int = 30, max_concurrent: int = 10):
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x464) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://github.com/",
            "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="140", "Google Chrome";v="140"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1"
        }

    async def fetch_nodes(self, url: str, filters: Dict[str, Any] = None) -> List[Node]:
        is_recursive = url.startswith('*')
        if is_recursive:
            url = url[1:]
        
        # 更加健壮的 GitHub 镜像生成逻辑
        targets = [url]
        import re
        gh_match = re.match(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.*)', url)
        if gh_match:
            user, repo, branch, path = gh_match.groups()
            # 备选镜像 1: jsDelivr (极速稳定)
            targets.append(f"https://fastly.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}")
            # 备选镜像 2: gh-proxy (通用代理)
            targets.append(f"https://gh-proxy.com/{url}")

        async with self.semaphore:
            content = None
            for target_url in targets:
                try:
                    print(f"Fetching: {target_url}")
                    async with httpx.AsyncClient(headers=self.headers, verify=False, follow_redirects=True) as client:
                        response = await client.get(target_url, timeout=self.timeout)
                        if response.status_code == 200:
                            content = response.content.decode('utf-8', errors='ignore')
                            break
                        else:
                            print(f"  - Error HTTP {response.status_code} on {target_url}")
                except Exception as e:
                    print(f"  - Request Exception on {target_url}: {e}")
            
            if not content:
                print(f"  - Failed to get any content for {url}")
                return []
        
        if is_recursive:
            import re
            found_urls = re.findall(r'https?://[^\s)\]]+', content)
            sub_urls = []
            exclude_keywords = [
                'github.com/peasoft', 'license', 'readme', 'rules', 't.me/', 
                'twitter.com', 'youtube.com', 'facebook.com', 't.cn', 'j.mp'
            ]
            for u in found_urls:
                u_lower = u.lower()
                if any(x in u_lower for x in exclude_keywords):
                    continue
                sub_urls.append(u)
            
            if sub_urls:
                sub_urls = list(dict.fromkeys(sub_urls))
                print(f"  - Found {len(sub_urls)} sub-urls in {url}")
                tasks = [self.fetch_nodes(u, filters) for u in sub_urls]
                results = await asyncio.gather(*tasks)
                all_nodes = []
                for res in results:
                    all_nodes.extend(res)
                return all_nodes
        
        # 解析内容
        nodes = self.parse_content(content)
        
        # 协议过滤
        if filters and 'ignore' in filters:
            ignore_types = [t.strip().lower() for t in filters['ignore'].split(',')]
            original_count = len(nodes)
            nodes = [n for n in nodes if n.type.lower() not in ignore_types]
            if len(nodes) < original_count:
                # print(f"  - Filtered {original_count - len(nodes)} nodes (ignore={filters['ignore']}) from {url}")
                pass
        
        if nodes:
            print(f"  - Successfully parsed {len(nodes)} nodes from {url}")
        else:
            print(f"  - No nodes found in {url}")
            
        return nodes

    def parse_content(self, content: str) -> List[Node]:
        nodes = []
        
        # 0. 预检查：如果是 HTML 网页，直接跳过（防止报错）
        if '<!DOCTYPE' in content.upper() or '<HTML' in content.upper():
            print("  - Warning: Content looks like HTML/Webpage, skipping parser.")
            return []

        # 1. Try to parse as YAML (Clash style)
        try:
            # 尝试全文安全解析
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                plist = data.get("proxies") or data.get("Proxy")
                if isinstance(plist, list):
                    for p in plist:
                        if isinstance(p, dict):
                            nodes.append(Node(p))
            elif isinstance(data, list):
                # 某些源直接返回一个列表
                for p in data:
                    if isinstance(p, dict):
                        nodes.append(Node(p))
        except Exception:
            pass

        # 2. 如果 YAML 整体解析失败或节点太少，尝试正则表达式提取 (保底方案)
        if len(nodes) < 5:
            import re
            found_lines = re.findall(r'-\s*(\{.*?name:.*?\})', content, re.DOTALL)
            for line in found_lines:
                try:
                    clean_line = line.replace('\n', ' ').replace('\r', '')
                    p_data = yaml.safe_load(clean_line)
                    if isinstance(p_data, dict) and 'server' in p_data:
                        nodes.append(Node(p_data))
                except:
                    continue
        
        if nodes:
            return nodes

        # 3. Try to parse as Base64 (Standard V2Ray style)
        if len(content) > 10 and not any(s in content for s in ["server:", "port:", "type:"]):
            try:
                decoded = b64decodes(content)
                if decoded:
                    lines = decoded.splitlines()
                    for line in lines:
                        if line.strip():
                            nodes.append(Node(line.strip()))
            except:
                pass
                
        # 4. Try to parse as raw list (one URL per line)
        allowed_protocols = ('vmess://', 'vless://', 'ss://', 'trojan://', 'hy2://', 'hysteria2://')
        for line in content.splitlines():
            line = line.strip()
            if line.startswith(allowed_protocols):
                nodes.append(Node(line))
        
        return nodes

async def parallel_fetch(source_infos: List[Dict[str, Any]]) -> List[Node]:
    """
    接收格式化的 source_info 列表，包含 url 和 filters
    """
    fetcher = Fetcher()
    tasks = [fetcher.fetch_nodes(info['url'], info.get('filters')) for info in source_infos]
    results = await asyncio.gather(*tasks)
    
    all_nodes = []
    for res in results:
        all_nodes.extend(res)
    return all_nodes
