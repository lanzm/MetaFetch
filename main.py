import asyncio
import os
import yaml
from typing import List
from core.fetcher import parallel_fetch
from core.processor import NodeProcessor
from core.generator import Generator

SOURCES_FILE = "sources.list"
TEMPLATE_FILE = "config.yaml"
OUTPUT_FILE = "list.meta.yml"

import datetime

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
    
    for s in sources_data:
        if isinstance(s, dict):
            url = s.get('url')
            if not url: continue
            
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
                'url': url,
                'filters': filters
            })
    
    if not source_infos:
        print("No active sources found.")
        return

    import time
    start_time = time.time()
    
    # 获取来源数量用于统计
    active_source_count = len(source_infos)
    print(f"Starting fetching from {active_source_count} active sources...")
    
    # 2. Parallel fetching
    all_raw_nodes = await parallel_fetch(source_infos)
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
    
    print(f"\n✅ All done! Generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
