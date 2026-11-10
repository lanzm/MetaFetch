import os
import yaml
import tempfile
import unittest
from core.parser import Node
from core.generator import Generator, _yaml_v3_needs_quotes

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
                {"name": "✅ 手动选择", "type": "select", "proxies": []},
                {"name": "📢 订阅信息", "type": "select", "proxies": []}
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
                self.assertFalse("⚠️" in p)

            # 2. 验证瑞士是否独立建组 (count > 0)
            region_menu = groups["🗺️ 选择地区"]["proxies"]
            self.assertIn("🇨🇭 瑞士", region_menu)

            # 3. 验证单地区内部组是否为 fallback 模式
            nl_group = groups.get("⚡ 自动选择 | 🇳🇱 荷兰")
            self.assertIsNotNone(nl_group)
            self.assertEqual(nl_group["type"], "fallback")

            # 4. 验证 📢 订阅信息 组存在且包含 5 个提示节点
            info_group = groups.get("📢 订阅信息")
            self.assertIsNotNone(info_group)
            self.assertEqual(len(info_group["proxies"]), 5)
            self.assertTrue(any("⚠️" in p for p in info_group["proxies"]))

            # 5. 验证 ✅ 手动选择 仅包含真实节点，去除非代理信息节点
            manual_proxies = groups["✅ 手动选择"]["proxies"]
            self.assertFalse(any("⚠️" in p for p in manual_proxies))
            self.assertIn("🇨🇭 瑞士 #1", manual_proxies)

    def test_generator_private_nodes_and_quota(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            # 构造 15 个私有节点 (香港 10 个，日本 5 个) + 5 个公共节点
            nodes = []
            for i in range(10):
                n = Node({"name": f"👑 🇭🇰 私有香港 {i}", "type": "ss", "server": f"1.1.1.{i+10}", "port": 443})
                n.data['_is_private'] = True
                nodes.append(n)
            for i in range(5):
                n = Node({"name": f"👑 🇯🇵 私有日本 {i}", "type": "vmess", "server": f"2.2.2.{i+10}", "port": 443})
                n.data['_is_private'] = True
                nodes.append(n)
            for i in range(5):
                n = Node({"name": f"🇺🇸 公共美国 {i}", "type": "trojan", "server": f"3.3.3.{i+10}", "port": 443})
                nodes.append(n)

            pool_settings = {
                "core_regions": ["HK", "JP", "US", "SG"],
                "private": {
                    "max_total": 4,          # 限制私有最多 4 个
                    "core_per_region": 2,     # 核心地区每区 2 个
                    "other_per_region": 1
                },
                "public": {
                    "core_per_region": 3,
                    "other_per_region": 1
                },
                "min_pool_size": 5,
                "max_pool_size": 15
            }

            generator = Generator(template_path, pool_settings=pool_settings)
            generator.generate(nodes, output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            groups = {g["name"]: g for g in cfg["proxy-groups"]}

            # 1. 验证动态生成了 👑 私有节点 策略组与子测速组
            self.assertIn("👑 私有节点", groups)
            self.assertIn("⚡ 自动选择 | 👑 私有节点", groups)
            # 专属组应包含全部 15 个私有节点
            self.assertEqual(len(groups["👑 私有节点"]["proxies"]), 16) # 1 个 auto + 15 个节点

            # 2. 验证 🚀 选择代理 首页排在第一位的是 👑 私有节点
            top_proxies = groups["🚀 选择代理"]["proxies"]
            self.assertEqual(top_proxies[0], "👑 私有节点")

            # 3. 验证 ♻️ 自动选择 中，私有节点数量严格被限制在 max_total (4个) 内
            auto_proxies = groups["♻️ 自动选择"]["proxies"]
            priv_in_auto = [p for p in auto_proxies if p.startswith("👑")]
            self.assertLessEqual(len(priv_in_auto), 4)

            # 4. 验证私有节点排在公共节点前面
            self.assertTrue(auto_proxies[0].startswith("👑"))

    def test_pool_settings_empty_and_special_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            # 1 个私有节点，测试 max_total 为 0 (禁用)
            node_priv = Node({"name": "👑 🇭🇰 私有香港", "type": "ss", "server": "1.1.1.1", "port": 443})
            node_priv.data['_is_private'] = True
            node_pub = Node({"name": "🇯🇵 公共日本", "type": "ss", "server": "2.2.2.2", "port": 443})

            # max_total: 0 -> 私有节点不进自动选择
            gen_zero = Generator(template_path, pool_settings={"private": {"max_total": 0}})
            gen_zero.generate([node_priv, node_pub], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            groups = {g["name"]: g for g in cfg["proxy-groups"]}
            auto_proxies = groups["♻️ 自动选择"]["proxies"]
            self.assertNotIn("👑 🇭🇰 私有香港", auto_proxies)
            self.assertIn("🇯🇵 公共日本", auto_proxies)

    def test_generator_safedumper_quotes_and_deep_sanitize(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            # 包含纯数字密码、布尔伪装字符串、裸十六进制 hash 以及深层控制字符
            node = Node({
                "name": "Special_Quote_Node",
                "type": "ss",
                "server": "1.2.3.4",
                "port": 443,
                "cipher": "aes-128-gcm",
                "password": "true",
                "uuid": "123456",
                "plugin": "obfs",
                "plugin-opts": {
                    "mode": "tls",
                    "host": "evil\x9f\x87host.com",
                    "obfs-password": "87d72c2949c0ca85bbda09459244e374"
                }
            })

            generator = Generator(template_path)
            generator.generate([node], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                raw_yaml = f.read()

            # 1. 验证 password: "true", uuid: "123456" 带有双引号，防止被 Go 解析为布尔值或整数
            self.assertIn('password: "true"', raw_yaml)
            self.assertIn('uuid: "123456"', raw_yaml)
            # 2. 验证裸十六进制字符串 (如 MD5/hash) 不会加不必要的双引号
            self.assertIn('obfs-password: 87d72c2949c0ca85bbda09459244e374', raw_yaml)
            self.assertNotIn('obfs-password: "87d72c2949c0ca85bbda09459244e374"', raw_yaml)
            # 3. 验证控制字符被完全清洗
            self.assertNotIn("\x9f", raw_yaml)
            self.assertNotIn("\x87", raw_yaml)
            self.assertIn("evilhost.com", raw_yaml)
            # 4. 验证 allow_unicode=True 使中文与 Emoji 直接可读输出，不出现 \u 或 \U 转义序列
            self.assertIn("🚀 选择代理", raw_yaml)
            self.assertIn("♻️ 自动选择", raw_yaml)
            self.assertNotIn(r"\u9009\u62E9", raw_yaml)

    def test_yaml_v3_needs_quotes(self):
        # 需加引号的情况：布尔/特殊字面量
        for lit in ["true", "True", "false", "False", "null", "NULL", "~"]:
            self.assertTrue(_yaml_v3_needs_quotes(lit), f"{lit} should need quotes")
        # 纯数字
        self.assertTrue(_yaml_v3_needs_quotes("123456"))
        self.assertTrue(_yaml_v3_needs_quotes("0123"))
        # 显式带 0x/0o/0b 前缀的进制数字
        self.assertTrue(_yaml_v3_needs_quotes("0x1a2b"))
        self.assertTrue(_yaml_v3_needs_quotes("0o755"))
        self.assertTrue(_yaml_v3_needs_quotes("0b1010"))
        # 浮点数与时间戳
        self.assertTrue(_yaml_v3_needs_quotes("3.14"))
        self.assertTrue(_yaml_v3_needs_quotes("1e5"))
        self.assertTrue(_yaml_v3_needs_quotes("2026-10-19"))

        # 无需加引号的情况：裸十六进制字符串 (Reality short-id, MD5 hash, 随机密码等)
        self.assertFalse(_yaml_v3_needs_quotes("aebdb601b1371778"))
        self.assertFalse(_yaml_v3_needs_quotes("7eadc6dbe2ae"))
        self.assertFalse(_yaml_v3_needs_quotes("87d72c2949c0ca85bbda09459244e374"))
        # 普通字符串与空字符串
        self.assertFalse(_yaml_v3_needs_quotes("hello_world"))
        self.assertFalse(_yaml_v3_needs_quotes(""))

    def test_generator_max_pool_size_strict_cap_after_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            # 构造 20 个公共节点，均不属于 core_regions (比如均为未知/其它地区)，使得初筛 pub_selected 可能无法填满或为空
            nodes = [
                Node({"name": f"🏳️ 其它节点_{i}", "type": "ss", "server": f"8.8.8.{i+1}", "port": 443})
                for i in range(20)
            ]

            # 配置 max_pool_size 为 5，但 core/other 配额很小或触发了 fallback 补充
            pool_settings = {
                "core_regions": ["HK", "JP", "US"],
                "public": {
                    "core_per_region": 1,
                    "other_per_region": 0  # other 初筛为 0
                },
                "min_pool_size": 20,       # 故意设置大于 max_pool_size，要求补齐到 20 个
                "max_pool_size": 5         # 但硬性最大上限为 5
            }

            generator = Generator(template_path, pool_settings=pool_settings)
            generator.generate(nodes, output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            groups = {g["name"]: g for g in cfg["proxy-groups"]}
            auto_proxies = groups["♻️ 自动选择"]["proxies"]

            # 验证即使 fallback 兜底补齐尝试追加全部 20 个节点，最终进入自动选择的节点数也严格 <= 5
            self.assertEqual(len(auto_proxies), 5)

    def test_generator_private_china_node_excluded_from_smart_pool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            # 私有中国节点 (带 👑 和 🇨🇳 前缀，模拟已清洗重命名后的私有节点)
            cn_priv = Node({"name": "👑 🇨🇳 私有上海直连", "type": "ss", "server": "114.114.114.114", "port": 443})
            cn_priv.data['_is_private'] = True

            # 私有海外节点
            hk_priv = Node({"name": "👑 🇭🇰 私有香港高速", "type": "ss", "server": "1.1.1.1", "port": 443})
            hk_priv.data['_is_private'] = True

            # 公共海外节点
            us_pub = Node({"name": "🇺🇸 公共美国01", "type": "trojan", "server": "8.8.8.8", "port": 443})

            generator = Generator(template_path)
            generator.generate([cn_priv, hk_priv, us_pub], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            groups = {g["name"]: g for g in cfg["proxy-groups"]}
            auto_proxies = groups["♻️ 自动选择"]["proxies"]
            lowest_proxies = groups["🔰 延迟最低"]["proxies"]
            private_proxies = groups["👑 私有节点"]["proxies"]

            # 1. 验证私有中国节点坚决不进 ♻️ 自动选择 和 🔰 延迟最低
            self.assertNotIn("👑 🇨🇳 私有上海直连", auto_proxies)
            self.assertNotIn("👑 🇨🇳 私有上海直连", lowest_proxies)

            # 2. 验证私有海外节点正常进入 ♻️ 自动选择
            self.assertIn("👑 🇭🇰 私有香港高速", auto_proxies)

            # 3. 验证私有中国节点仍完整保留在 👑 私有节点 策略组供专属需要时选择
            self.assertIn("👑 🇨🇳 私有上海直连", private_proxies)

    def test_generator_zero_speed_nodes_demotion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            fast_node = Node({"name": "🇯🇵 日本高速|5.2MB/s", "type": "ss", "server": "1.1.1.1", "port": 443})
            normal_vless = Node({"name": "🇯🇵 日本普通VLESS", "type": "vless", "server": "1.1.1.2", "port": 443})
            normal_trojan = Node({"name": "🇯🇵 日本普通Trojan", "type": "trojan", "server": "1.1.1.3", "port": 443})
            zero_mb_node = Node({"name": "🇯🇵 日本失效|0.0MB/s", "type": "ss", "server": "1.1.1.4", "port": 443})
            zero_kb_node = Node({"name": "🇯🇵 日本失效|0KB/s", "type": "ss", "server": "1.1.1.5", "port": 443})

            generator = Generator(template_path)
            generator.generate([zero_mb_node, fast_node, normal_trojan, zero_kb_node, normal_vless], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            groups = {g["name"]: g for g in cfg["proxy-groups"]}
            jp_group = groups.get("⚡ 自动选择 | 🇯🇵 日本")
            self.assertIsNotNone(jp_group)
            proxies = jp_group["proxies"]

            # 1. 验证 5.2MB/s 获得最高分，排在第 1 位
            self.assertEqual(proxies[0], "🇯🇵 日本高速|5.2MB/s")
            # 2. 验证普通 VLESS (60分) 与 Trojan (50分) 位于中间梯队
            self.assertEqual(proxies[1], "🇯🇵 日本普通VLESS")
            self.assertEqual(proxies[2], "🇯🇵 日本普通Trojan")
            # 3. 验证 0.0MB/s 与 0KB/s 被大幅降权至 5 分，被排在最末尾垫底
            self.assertEqual(set(proxies[3:]), {"🇯🇵 日本失效|0.0MB/s", "🇯🇵 日本失效|0KB/s"})

    def test_is_china_node_whitelist_exemptions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            # 1. 纯境内节点 (应被排除出 自动选择)
            node_pure_cn = Node({"name": "🇨🇳 中国电信上海节点", "type": "ss", "server": "1.1.1.1", "port": 443})
            # 2. 带有 CN2-GIA / IPLC 等中转但明确标识海外落地 (白名单豁免，应进入 自动选择)
            node_cn2_hk = Node({"name": "🇨🇳 CN2-GIA 🇭🇰 香港 01", "type": "ss", "server": "1.1.1.2", "port": 443})
            node_iplc_jp = Node({"name": "🇨🇳 IPLC 🇯🇵 日本 01", "type": "ss", "server": "1.1.1.3", "port": 443})

            generator = Generator(template_path)
            generator.generate([node_pure_cn, node_cn2_hk, node_iplc_jp], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            groups = {g["name"]: g for g in cfg["proxy-groups"]}
            auto_proxies = groups["♻️ 自动选择"]["proxies"]
            self.assertIn("🇨🇳 CN2-GIA 🇭🇰 香港 01", auto_proxies)
            self.assertIn("🇨🇳 IPLC 🇯🇵 日本 01", auto_proxies)
            self.assertNotIn("🇨🇳 中国电信上海节点", auto_proxies)

    def test_generator_empty_nodes_direct_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "config.yaml")
            output_path = os.path.join(tmpdir, "output.yaml")
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.template_data, f)

            generator = Generator(template_path)
            # 空节点列表生成防崩溃测试
            stats = generator.generate([], output_path)
            self.assertEqual(stats['total_nodes'], 0)

            with open(output_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            groups = {g["name"]: g for g in cfg["proxy-groups"]}
            self.assertEqual(groups["♻️ 自动选择"]["proxies"], ['DIRECT'])
            self.assertEqual(groups["🔰 延迟最低"]["proxies"], ['DIRECT'])
            self.assertEqual(groups["🗺️ 选择地区"]["proxies"], ['DIRECT'])
            self.assertEqual(groups["✅ 手动选择"]["proxies"], ['DIRECT'])

    def test_generator_speed_regex_variants(self):
        from core.generator import _MB_SPEED_RE, _KB_SPEED_RE
        # 1. MB/s, M/s, Mbps
        m1 = _MB_SPEED_RE.search("US_1|50Mbps")
        self.assertIsNotNone(m1)
        self.assertEqual(m1.group(1), "50")

        m2 = _MB_SPEED_RE.search("HK_01|3.5M/s")
        self.assertIsNotNone(m2)
        self.assertEqual(m2.group(1), "3.5")

        m3 = _MB_SPEED_RE.search("JP_01|2.8MB/s")
        self.assertIsNotNone(m3)
        self.assertEqual(m3.group(1), "2.8")

        # 2. KB/s, K/s, kbps
        k1 = _KB_SPEED_RE.search("DE_01|800kbps")
        self.assertIsNotNone(k1)
        self.assertEqual(k1.group(1), "800")

        k2 = _KB_SPEED_RE.search("SG_01|512KB/s")
        self.assertIsNotNone(k2)
        self.assertEqual(k2.group(1), "512")

if __name__ == "__main__":
    unittest.main()


