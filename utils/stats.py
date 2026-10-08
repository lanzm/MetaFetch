import datetime
import os
import re
from typing import List, Dict, Any
from utils.regions import REGION_NAMES

def update_readme_overview(
    total_nodes: int,
    region_nodes: Dict[str, List[str]],
    others: List[str],
    timestamp: str,
    source_count: int,
    raw_count: int,
    elapsed_time: float,
    readme_path: str = "README.md"
):
    """更新 README.md 顶部的状态徽章与地区分布统计表格"""
    if not os.path.exists(readme_path):
        return

    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    badge_content = (
        f"![Update](https://img.shields.io/badge/Updated-{timestamp.replace(' ', '--').replace(':', '%3A')}-green.svg?style=flat-square)\n"
        f"![Nodes](https://img.shields.io/badge/Valid_Nodes-{total_nodes}-orange.svg?style=flat-square)\n"
        f"![Sources](https://img.shields.io/badge/Active_Sources-{source_count}-blue.svg?style=flat-square)"
    )
    content = re.sub(
        r'<!-- STATS_BADGE_START -->.*?<!-- STATS_BADGE_END -->',
        f'<!-- STATS_BADGE_START -->\n{badge_content}\n<!-- STATS_BADGE_END -->',
        content,
        flags=re.DOTALL
    )

    header_row = ["地区分布"]
    value_row = ["**数量**"]

    for key in region_nodes:
        count = len(region_nodes[key])
        name = REGION_NAMES.get(key, key)
        header_row.append(name.replace(' ', ''))
        value_row.append(str(count))

    if others:
        header_row.append("🌍其他")
        value_row.append(str(len(others)))

    header_row.append("**总计**")
    value_row.append(f"**{total_nodes}**")

    table_markdown = (
        f"<div style=\"overflow-x: auto;\">\n\n"
        f"| {' | '.join(header_row)} |\n"
        f"| {' | '.join([':---:']*len(header_row))} |\n"
        f"| {' | '.join(value_row)} |\n\n"
        f"</div>"
    )
    stats_summary = (
        f"> 更新时间：`{timestamp}`\n"
        f"> 运行分析：从 `{source_count}` 个活跃源中抓取 `{raw_count}` 个节点，耗时 `{elapsed_time:.2f}s`。去重后保留 `{total_nodes}` 个有效节点。"
    )

    content = re.sub(
        r'<!-- STATS_TABLE_START -->.*?<!-- STATS_TABLE_END -->',
        f'<!-- STATS_TABLE_START -->\n{stats_summary}\n\n{table_markdown}\n<!-- STATS_TABLE_END -->',
        content,
        flags=re.DOTALL
    )

    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)


def render_and_update_readme_source_stats(source_results: List[Dict[str, Any]], now: datetime.datetime = None, readme_path: str = "README.md"):
    """
    根据传入的源统计数据直接渲染并更新 README.md 中的贡献明细表格（纯内存操作，零网络开销）
    """
    if now is None:
        now = datetime.datetime.now()
    if not os.path.exists(readme_path):
        return

    # 按有效节点数降序排序
    sorted_results = sorted(source_results, key=lambda x: x.get('valid_count', 0), reverse=True)
    total_valid = sum(item.get('valid_count', 0) for item in sorted_results)

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

    for idx, item in enumerate(sorted_results, 1):
        v_count = item.get('valid_count', 0)
        pct = (v_count / total_valid * 100) if total_valid > 0 else 0
        lines.append(f"| {idx} | `{item.get('name', '未命名源')}` | **{v_count}** 个 | `{pct:.2f}%` |")

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


def update_readme_all(gen_stats: Dict[str, Any], source_results: List[Dict[str, Any]], now: datetime.datetime = None, readme_path: str = "README.md"):
    """统一更新 README.md 中的所有看板（顶部徽章、地区表与源贡献表）"""
    if gen_stats:
        update_readme_overview(
            total_nodes=gen_stats.get('total_nodes', 0),
            region_nodes=gen_stats.get('region_nodes', {}),
            others=gen_stats.get('others', []),
            timestamp=gen_stats.get('timestamp', ''),
            source_count=gen_stats.get('source_count', 0),
            raw_count=gen_stats.get('raw_count', 0),
            elapsed_time=gen_stats.get('elapsed_time', 0.0),
            readme_path=readme_path
        )
    if source_results:
        render_and_update_readme_source_stats(source_results, now=now, readme_path=readme_path)
