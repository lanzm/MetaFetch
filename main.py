import asyncio
import datetime
import os
import time
import yaml

from core.fetcher import parallel_fetch
from core.processor import NodeProcessor
from core.generator import Generator
from utils.stats import render_and_update_readme_source_stats

TEMPLATE_FILE = "config.yaml"
OUTPUT_FILE = "list.meta.yml"

async def main():
    # 1. Load Sources from YAML
    sources_file = "sources.yaml"
    if not os.path.exists(sources_file):
        print(f"Error: {sources_file} not found.")
        return

    now = datetime.datetime.now()
    source_infos = []
    with open(sources_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        sources_data = data.get('sources', [])
        
    # Append private sources from Environment Variable (GitHub Secrets)
    private_sources = os.getenv('PRIVATE_SOURCES')
    if private_sources:
        try:
            private_data = yaml.safe_load(private_sources)
            if isinstance(private_data, list):
                sources_data.extend(private_data)
                print(f"Loaded {len(private_data)} private sources from Secrets.")
        except Exception as e:
            print(f"Failed to parse PRIVATE_SOURCES: {e}")
            
    for s in sources_data:
        if isinstance(s, dict):
            url = s.get('url')
            if not url: continue
            name = s.get('name', '未命名源')
            
            # Handle date placeholders in URL
            url = url.replace('%Y', now.strftime('%Y'))
            url = url.replace('%m', now.strftime('%m'))
            url = url.replace('%d', now.strftime('%d'))
            
            # Translate recursive flag to * prefix
            if s.get('recursive'):
                url = '*' + url
            
            ignore = s.get('ignore')
            filters = {'ignore': ignore} if ignore else {}
            
            source_infos.append({
                'name': name,
                'url': url,
                'filters': filters
            })
    
    if not source_infos:
        print("No active sources found.")
        return

    start_time = time.time()
    
    # 获取来源数量用于统计
    active_source_count = len(source_infos)
    print(f"Starting fetching from {active_source_count} active sources...")
    
    # 2. Parallel fetching (单次全异步并发抓取，同时获取各源节点明细)
    all_raw_nodes, raw_source_results = await parallel_fetch(source_infos)
    raw_count = len(all_raw_nodes)
    print(f"Fetched {raw_count} raw nodes.")
    
    # 3. Processing (Deduplicate, Clean Names, Emoji Flags)
    processor = NodeProcessor()
    processed_nodes = processor.process_all(all_raw_nodes)
    
    # 4. Generate Output (Merge with template)
    if not os.path.exists(TEMPLATE_FILE):
        print(f"Warning: {TEMPLATE_FILE} not found. Using node list only.")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            yaml.dump({"proxies": [n.to_clash() for n in processed_nodes]}, f, allow_unicode=True)
    else:
        elapsed_time = time.time() - start_time
        generator = Generator(TEMPLATE_FILE)
        generator.generate(processed_nodes, OUTPUT_FILE, active_source_count, raw_count, elapsed_time)
        
        # 5. Update README Source Contribution Table (零二次网络开销，纯内存计算)
        try:
            source_stats = []
            for item in raw_source_results:
                valid_nodes = processor.filter_invalid(item.get('nodes', []))
                source_stats.append({
                    'name': item.get('name', '未命名源'),
                    'valid_count': len(valid_nodes)
                })
            render_and_update_readme_source_stats(source_stats, now)
        except Exception as e:
            print(f"Warning: Failed to update README source stats table: {e}")
    
    print(f"\n[OK] All done! Generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
