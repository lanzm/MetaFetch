import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
import httpx
import yaml

from core.parser import Node
from utils.common import b64decodes
from utils.logger import logger

# 模块级预编译正则
GITHUB_RAW_PATTERN = re.compile(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.*)')
URL_EXTRACT_PATTERN = re.compile(r'https?://[^\s)\]]+')
YAML_FALLBACK_PATTERN = re.compile(r'-\s*(\{.*?name:.*?\})', re.DOTALL)
ALLOWED_PROTOCOLS = ('vmess://', 'vless://', 'ss://', 'trojan://', 'hy2://', 'hysteria2://')

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
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

EXCLUDE_RECURSIVE_KEYWORDS = (
    'github.com/peasoft', 'license', 'readme', 'rules', 't.me/',
    'twitter.com', 'youtube.com', 'facebook.com', 't.cn', 'j.mp'
)

class Fetcher:
    def __init__(self, timeout: int = 10, max_concurrent: int = 15, client: Optional[httpx.AsyncClient] = None):
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.headers = DEFAULT_HEADERS
        self._external_client = client is not None
        self.client = client

    async def __aenter__(self):
        if self.client is None:
            # 复用连接池、开启 Keep-Alive 与连接限制
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
            self.client = httpx.AsyncClient(
                headers=self.headers,
                verify=False,
                follow_redirects=True,
                trust_env=True,
                limits=limits,
                timeout=self.timeout
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._external_client and self.client:
            await self.client.aclose()
            self.client = None

    async def fetch_nodes(self, url: str, filters: Optional[Dict[str, Any]] = None) -> List[Node]:
        async with self.semaphore:
            return await self._fetch_nodes_internal(url, filters)

    async def _fetch_nodes_internal(self, url: str, filters: Optional[Dict[str, Any]] = None) -> List[Node]:
        is_recursive = url.startswith('*')
        if is_recursive:
            url = url[1:]

        # 更加健壮的 GitHub 镜像生成逻辑
        targets = [url]
        gh_match = GITHUB_RAW_PATTERN.match(url)
        if gh_match:
            user, repo, branch, path = gh_match.groups()
            # 备选镜像 1: jsDelivr (极速稳定)
            targets.append(f"https://fastly.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}")
            # 备选镜像 2: gh-proxy (通用代理)
            targets.append(f"https://gh-proxy.com/{url}")

        content = None
        # 确保 client 实例可用
        client = self.client
        close_client_after = False
        if client is None:
            client = httpx.AsyncClient(headers=self.headers, verify=False, follow_redirects=True, timeout=self.timeout)
            close_client_after = True

        try:
            for target_url in targets:
                try:
                    logger.debug(f"Fetching: {target_url}")
                    response = await client.get(target_url, timeout=self.timeout)
                    if response.status_code == 200:
                        content = response.content.decode('utf-8', errors='ignore')
                        break
                    else:
                        logger.debug(f"  - Error HTTP {response.status_code} on {target_url}")
                except Exception as e:
                    logger.debug(f"  - Request Exception on {target_url}: {e}")
        finally:
            if close_client_after:
                await client.aclose()

        if not content:
            logger.warning(f"  - Failed to get any content for {url}")
            return []

        if is_recursive:
            found_urls = URL_EXTRACT_PATTERN.findall(content)
            sub_urls = []
            for u in found_urls:
                u_lower = u.lower()
                if any(x in u_lower for x in EXCLUDE_RECURSIVE_KEYWORDS):
                    continue
                sub_urls.append(u)

            if sub_urls:
                sub_urls = list(dict.fromkeys(sub_urls))
                logger.info(f"  - Found {len(sub_urls)} sub-urls in {url}")
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
            nodes = [n for n in nodes if n.type.lower() not in ignore_types]

        if nodes:
            logger.info(f"  - Successfully parsed {len(nodes)} nodes from {url}")
        else:
            logger.warning(f"  - No nodes found in {url}")

        return nodes

    def parse_content(self, content: str) -> List[Node]:
        nodes = []

        # 0. 预检查：如果是 HTML 网页，直接跳过（防止报错）
        if '<!DOCTYPE' in content.upper() or '<HTML' in content.upper():
            logger.debug("  - Warning: Content looks like HTML/Webpage, skipping parser.")
            return []

        # 1. Try to parse as YAML (Clash style)
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                plist = data.get("proxies") or data.get("Proxy")
                if isinstance(plist, list):
                    for p in plist:
                        if isinstance(p, dict):
                            nodes.append(Node(p))
            elif isinstance(data, list):
                for p in data:
                    if isinstance(p, dict):
                        nodes.append(Node(p))
        except Exception:
            pass

        # 2. 如果 YAML 整体解析失败或节点太少，尝试正则表达式提取 (保底方案)
        if len(nodes) < 5:
            found_lines = YAML_FALLBACK_PATTERN.findall(content)
            for line in found_lines:
                try:
                    clean_line = line.replace('\n', ' ').replace('\r', '')
                    p_data = yaml.safe_load(clean_line)
                    if isinstance(p_data, dict) and 'server' in p_data:
                        nodes.append(Node(p_data))
                except Exception:
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
                        line_s = line.strip()
                        if line_s:
                            nodes.append(Node(line_s))
            except Exception:
                pass

        # 4. Try to parse as raw list (one URL per line)
        for line in content.splitlines():
            line_s = line.strip()
            if line_s.startswith(ALLOWED_PROTOCOLS):
                nodes.append(Node(line_s))

        return nodes

async def parallel_fetch(source_infos: List[Dict[str, Any]]) -> Tuple[List[Node], List[Dict[str, Any]]]:
    """
    接收格式化的 source_info 列表，包含 name, url 和 filters
    使用全局连接池高效并行抓取，返回 (全量节点列表, 按源归类的明细列表)
    """
    async with Fetcher() as fetcher:
        tasks = [fetcher.fetch_nodes(info['url'], info.get('filters')) for info in source_infos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_nodes = []
        source_results = []
        for info, res in zip(source_infos, results):
            s_name = info.get('name', '未命名源')
            if isinstance(res, Exception) or not res:
                source_results.append({
                    'name': s_name,
                    'nodes': []
                })
            else:
                all_nodes.extend(res)
                source_results.append({
                    'name': s_name,
                    'nodes': res
                })
        return all_nodes, source_results
