import datetime
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from utils.regions import REGION_NAMES


def build_overview_markdown(
    total_nodes: int,
    region_nodes: Dict[str, List[str]],
    others: List[str],
    timestamp: str,
    source_count: int,
    raw_count: int,
    elapsed_time: float,
) -> Tuple[str, str]:
    """生成状态徽章 Markdown 与地区分布统计表格 Markdown"""
    badge_content = (
        f"![Update](https://img.shields.io/badge/Updated-{timestamp.replace(' ', '--').replace(':', '%3A')}-green.svg?style=flat-square)\n"
        f"![Nodes](https://img.shields.io/badge/Valid_Nodes-{total_nodes}-orange.svg?style=flat-square)\n"
        f"![Sources](https://img.shields.io/badge/Active_Sources-{source_count}-blue.svg?style=flat-square)"
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
    table_content = f"{stats_summary}\n\n{table_markdown}"

    return badge_content, table_content


def build_source_stats_markdown(source_results: List[Dict[str, Any]], now: Optional[datetime.datetime] = None) -> str:
    """生成源贡献明细表格 Markdown"""
    if now is None:
        now = datetime.datetime.now()

    # 按有效节点数降序排序
    sorted_results = sorted(source_results, key=lambda x: x.get('valid_count', 0), reverse=True)
    total_valid = sum(item.get('valid_count', 0) for item in sorted_results)

    lines = [
        "### 📡 各订阅源贡献度明细",
        "",
        f"> 数据计算时间：`{now.strftime('%Y-%m-%d %H:%M:%S')}`",
        "",
        '<table width="100%"><tr><td>',
        "",
        '<div style="max-height: 260px; overflow-y: auto;">',
        "",
        "| 排名 | 订阅源名称 | 有效节点数 | 节点贡献占比 |",
        "| :---: | :--- | :---: | :---: |",
    ]

    for idx, item in enumerate(sorted_results, 1):
        v_count = item.get('valid_count', 0)
        pct = (v_count / total_valid * 100) if total_valid > 0 else 0
        lines.append(f"| {idx} | `{item.get('name', '未命名源')}` | **{v_count}** 个 | `{pct:.2f}%` |")

    lines.extend([
        f"| **-** | **总计 (包含跨源重合)** | **{total_valid}** 个 | `100.00%` |",
        "",
        "</div>",
        "",
        "</td></tr></table>",
    ])

    return "\n".join(lines)


def apply_readme_updates(
    content: str,
    gen_stats: Optional[Dict[str, Any]] = None,
    source_results: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime.datetime] = None,
) -> str:
    """在内存中对 README 文本一次性应用全部看板区块的正则替换（纯内存全量替换）"""
    if gen_stats:
        badge_content, table_content = build_overview_markdown(
            total_nodes=gen_stats.get('total_nodes', 0),
            region_nodes=gen_stats.get('region_nodes', {}),
            others=gen_stats.get('others', []),
            timestamp=gen_stats.get('timestamp', ''),
            source_count=gen_stats.get('source_count', 0),
            raw_count=gen_stats.get('raw_count', 0),
            elapsed_time=gen_stats.get('elapsed_time', 0.0),
        )

        content = re.sub(
            r'<!-- STATS_BADGE_START -->.*?<!-- STATS_BADGE_END -->',
            f'<!-- STATS_BADGE_START -->\n{badge_content}\n<!-- STATS_BADGE_END -->',
            content,
            flags=re.DOTALL,
        )

        content = re.sub(
            r'<!-- STATS_TABLE_START -->.*?<!-- STATS_TABLE_END -->',
            f'<!-- STATS_TABLE_START -->\n{table_content}\n<!-- STATS_TABLE_END -->',
            content,
            flags=re.DOTALL,
        )

    if source_results is not None:
        source_table_content = build_source_stats_markdown(source_results, now=now)
        content = re.sub(
            r'<!-- SOURCE_STATS_TABLE_START -->[\s\S]*?<!-- SOURCE_STATS_TABLE_END -->',
            f'<!-- SOURCE_STATS_TABLE_START -->\n{source_table_content}\n<!-- SOURCE_STATS_TABLE_END -->',
            content,
        )

    return content


def update_readme_all(
    gen_stats: Optional[Dict[str, Any]],
    source_results: Optional[List[Dict[str, Any]]],
    now: Optional[datetime.datetime] = None,
    readme_path: str = "README.md",
):
    """统一更新 README.md 中的所有看板（单次读取 -> 纯内存全量替换 -> 单次写回）"""
    if not os.path.exists(readme_path):
        return

    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = apply_readme_updates(content, gen_stats=gen_stats, source_results=source_results, now=now)

    if new_content != content:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(new_content)


def update_readme_overview(
    total_nodes: int,
    region_nodes: Dict[str, List[str]],
    others: List[str],
    timestamp: str,
    source_count: int,
    raw_count: int,
    elapsed_time: float,
    readme_path: str = "README.md",
):
    """兼容旧接口：单向更新 README 概览"""
    gen_stats = {
        'total_nodes': total_nodes,
        'region_nodes': region_nodes,
        'others': others,
        'timestamp': timestamp,
        'source_count': source_count,
        'raw_count': raw_count,
        'elapsed_time': elapsed_time,
    }
    update_readme_all(gen_stats, None, readme_path=readme_path)


def render_and_update_readme_source_stats(
    source_results: List[Dict[str, Any]],
    now: Optional[datetime.datetime] = None,
    readme_path: str = "README.md",
):
    """兼容旧接口：单向更新订阅源贡献表"""
    update_readme_all(None, source_results, now=now, readme_path=readme_path)
