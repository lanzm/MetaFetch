import os
import yaml
import tempfile
import unittest
from core.parser import Node
from core.generator import Generator

class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.template_data = {
            "mixed-port": 7890,
            "mode": "rule",
            "proxy-groups": [
                {"name": "🚀 选择代理", "type": "select", "proxies": ["♻️ 自动选择", "🗺️ 选择地区"]},
                {"name": "🗺️ 选择地区", "type": "select", "proxies": []},
                {"name": "♻️ 自动选择", "type": "fallback", "proxies": []},
                {"name": "🔰 延迟最低", "type": "url-test", "proxies": []},
                {"name": "✅ 手动选择", "type": "select", "proxies": []}
            ],
            "rules": ["MATCH,🚀 选择代理"]
        }

    def test_generator_smart_pool_and_regions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            nodes = [
                # 中国节点 (应被排除出自动选择)
                Node({"name": "🇨🇳 CN_speednode_0001", "type": "ss", "server": "1.1.1.1", "port": 443}),
                # 荷兰节点 (带 speednode)
                Node({"name": "🇳🇱 NL_speednode_0004", "type": "ss", "server": "1.1.1.2", "port": 443}),
                Node({"name": "🇳🇱 NL_speednode_0005", "type": "ss", "server": "1.1.1.3", "port": 443}),
                # 日本节点 (带 MB/s)
                Node({"name": "🇯🇵JP_1|5.9MB/s", "type": "vmess", "server": "1.1.1.4", "port": 443}),
                # 瑞士节点 (只有 1 个，应该能独立建组)
                Node({"name": "🇨🇭 瑞士 #1", "type": "trojan", "server": "1.1.1.5", "port": 443}),
            ]

            generator = Generator(template_path)
            generator.generate(nodes, output_path)

            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            groups = {g["name"]: g for g in cfg["proxy-groups"]}
            
            # 1. 验证 🇨🇳 是否被排除出 ♻️ 自动选择
            auto_proxies = groups["♻️ 自动选择"]["proxies"]
            for p in auto_proxies:
                self.assertFalse(p.startswith("🇨🇳"))

            # 2. 验证瑞士是否独立建组 (count > 0)
            region_menu = groups["🗺️ 选择地区"]["proxies"]
            self.assertIn("🇨🇭 瑞士", region_menu)

            # 3. 验证单地区内部组是否为 fallback 模式
            nl_group = groups.get("⚡ 自动选择 | 🇳🇱 荷兰")
            self.assertIsNotNone(nl_group)
            self.assertEqual(nl_group["type"], "fallback")

if __name__ == "__main__":
    unittest.main()
