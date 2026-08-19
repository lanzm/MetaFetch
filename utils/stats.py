import asyncio
import datetime
import yaml
import sys
import os
import re

sys.path.insert(0, os.getcwd())

from core.fetcher import Fetcher
from core.processor import NodeProcessor

async def update_readme_source_stats():
    now = datetime.datetime.now()
    sources_file = "sources.yaml"
    readme_path = "README.md"
    
    if not os.path.exists(sources_file) or not os.path.exists(readme_path):
        return
        
    with open(sources_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    sources = data.get("sources", [])
    fetcher = Fetcher(timeout=15)
    processor = NodeProcessor()
    
    source_results = []
    
    for s in sources:
        raw_url = s.get('url', '')
        name = s.get('name', '未命名源')
        if not raw_url: continue
        
        url = now.strftime(raw_url)
        if s.get('recursive'): url = '*' + url
        ignore = s.get('ignore')
        filters = {'ignore': ignore} if ignore else {}
        
        try:
            nodes = await fetcher.fetch_nodes(url, filters)
            valid_nodes = processor.filter_invalid(nodes)
            source_results.append({
                "name": name,
                "valid_count": len(valid_nodes)
            })
        except Exception:
            source_results.append({
                "name": name,
                "valid_count": 0
            })
            
    source_results.sort(key=lambda x: x['valid_count'], reverse=True)
    total_valid = sum(item['valid_count'] for item in source_results)
    
    lines = []
    lines.append("### 📡 各订阅源贡献度明细")
    lines.append("")
    lines.append(f"> 数据计算时间：`{now.strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append("")
    lines.append('<table width="100%"><tr><td>')
    lines.append("")
    lines.append('<div style="max-height: 260px; overflow-y: auto;">')
    lines.append("")
    lines.append("| 排名 | 订阅源名称 | 有效节点数 | 节点贡献占比 |")
    lines.append("| :---: | :--- | :---: | :---: |")
    
    for idx, item in enumerate(source_results, 1):
        pct = (item['valid_count'] / total_valid * 100) if total_valid > 0 else 0
        lines.append(f"| {idx} | `{item['name']}` | **{item['valid_count']}** 个 | `{pct:.2f}%` |")
        
    lines.append(f"| **-** | **总计 (包含跨源重合)** | **{total_valid}** 个 | `100.00%` |")
    lines.append("")
    lines.append("</div>")
    lines.append("")
    lines.append("</td></tr></table>")
    
    table_content = "\n".join(lines)
    
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()
        
    pattern = r"<!-- SOURCE_STATS_TABLE_START -->[\s\S]*?<!-- SOURCE_STATS_TABLE_END -->"
    replacement = f"<!-- SOURCE_STATS_TABLE_START -->\n{table_content}\n<!-- SOURCE_STATS_TABLE_END -->"
    
    if "<!-- SOURCE_STATS_TABLE_START -->" in readme:
        new_readme = re.sub(pattern, replacement, readme)
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_readme)

if __name__ == "__main__":
    asyncio.run(update_readme_source_stats())
