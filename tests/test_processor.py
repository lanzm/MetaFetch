# -*- coding: utf-8 -*-
import unittest
from core.parser import Node
from core.processor import NodeProcessor, is_invalid_or_private_server

class TestProcessor(unittest.TestCase):
    def test_processor_filter_invalid_servers(self):
        processor = NodeProcessor()
        nodes = [
            Node({"name": "Node_Valid", "type": "vmess", "server": "1.2.3.4", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Valid_IPv6", "type": "vmess", "server": "[2606:4700:4700::1111]", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Loopback1", "type": "vmess", "server": "127.0.0.1", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Loopback2", "type": "vmess", "server": "0.0.0.0", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Localhost", "type": "vmess", "server": "localhost", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_IPv6_Loopback_Bracket", "type": "vmess", "server": "[::1]", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_IPv6_Loopback_Plain", "type": "vmess", "server": "::1", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Loopback_53", "type": "vmess", "server": "127.0.0.53", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Private_10", "type": "vmess", "server": "10.0.0.1", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Private_172", "type": "vmess", "server": "172.16.0.1", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Private_192", "type": "vmess", "server": "192.168.1.1", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Cloud_Metadata", "type": "vmess", "server": "169.254.169.254", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_CGNAT", "type": "vmess", "server": "100.64.0.1", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_IPv6_LinkLocal", "type": "vmess", "server": "[fe80::1]", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_IPv6_ULA", "type": "vmess", "server": "[fc00::1]", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Valid_Domain", "type": "ss", "server": "my-proxy.fastnode.org", "port": 443, "cipher": "aes-128-gcm", "password": "pwd"}),
            Node({"name": "Node_NoUUID", "type": "vmess", "server": "1.2.3.4", "port": 443}),
            Node({"name": "Node_BadPort", "type": "vmess", "server": "1.2.3.4", "port": -1, "uuid": "a0000000-0000-0000-0000-000000000000"}),
        ]
        valid = processor.filter_invalid(nodes)
        self.assertEqual(len(valid), 3)
        valid_names = {n.name for n in valid}
        self.assertEqual(valid_names, {"Node_Valid", "Node_Valid_IPv6", "Node_Valid_Domain"})

    def test_is_invalid_or_private_server(self):
        # 无效与占位
        self.assertTrue(is_invalid_or_private_server(""))
        self.assertTrue(is_invalid_or_private_server("0.0.0.0"))
        self.assertTrue(is_invalid_or_private_server("localhost"))
        self.assertTrue(is_invalid_or_private_server("example.com"))
        self.assertTrue(is_invalid_or_private_server("bad server space"))

        # 回环 (127.0.0.0/8, ::1)
        self.assertTrue(is_invalid_or_private_server("127.0.0.1"))
        self.assertTrue(is_invalid_or_private_server("127.0.0.53"))
        self.assertTrue(is_invalid_or_private_server("127.255.255.255"))
        self.assertTrue(is_invalid_or_private_server("::1"))
        self.assertTrue(is_invalid_or_private_server("[::1]"))

        # RFC 1918 私有内网
        self.assertTrue(is_invalid_or_private_server("10.0.0.1"))
        self.assertTrue(is_invalid_or_private_server("172.16.0.1"))
        self.assertTrue(is_invalid_or_private_server("172.31.255.254"))
        self.assertTrue(is_invalid_or_private_server("192.168.1.1"))

        # 云元数据 / 链路本地 (169.254.0.0/16, fe80::/10)
        self.assertTrue(is_invalid_or_private_server("169.254.169.254"))
        self.assertTrue(is_invalid_or_private_server("fe80::1"))
        self.assertTrue(is_invalid_or_private_server("[fe80::1]"))

        # CGNAT (100.64.0.0/10) 与 IPv6 ULA
        self.assertTrue(is_invalid_or_private_server("100.64.0.1"))
        self.assertTrue(is_invalid_or_private_server("fc00::1"))
        self.assertTrue(is_invalid_or_private_server("[fc00::1]"))

        # 合法公网 IP 与正常域名 (安全放行)
        self.assertFalse(is_invalid_or_private_server("1.2.3.4"))
        self.assertFalse(is_invalid_or_private_server("8.8.8.8"))
        self.assertFalse(is_invalid_or_private_server("2606:4700:4700::1111"))
        self.assertFalse(is_invalid_or_private_server("[2606:4700:4700::1111]"))
        self.assertFalse(is_invalid_or_private_server("hk.node.example.org"))

    def test_processor_deduplicate(self):
        processor = NodeProcessor()
        node1 = Node({"name": "NodeA", "type": "ss", "server": "example.com", "port": 8388, "cipher": "aes-256-gcm", "password": "pwd"})
        # 大小写域名与重复节点
        node2 = Node({"name": "NodeA_dup_upper", "type": "ss", "server": "EXAMPLE.COM", "port": 8388, "cipher": "aes-256-gcm", "password": "pwd"})
        node3 = Node({"name": "NodeB_diff_port", "type": "ss", "server": "example.com", "port": 8389, "cipher": "aes-256-gcm", "password": "pwd"})

        deduped = processor.deduplicate([node1, node2, node3])
        self.assertEqual(len(deduped), 2)

    def test_processor_flag_and_clean_names(self):
        processor = NodeProcessor()
        node_us = Node({"name": "US Fast Server", "type": "vmess", "server": "1.2.3.4", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        node_jp = Node({"name": "Tokyo Japan VIP", "type": "vmess", "server": "1.2.3.5", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        
        processed = processor.process_all([node_us, node_jp])
        self.assertEqual(len(processed), 2)
        self.assertTrue(processed[0].name.startswith("🇺🇸"))
        self.assertTrue(processed[1].name.startswith("🇯🇵"))

    def test_processor_strip_control_characters(self):
        processor = NodeProcessor()
        # 包含 \u200d, \u200e, \ufe0f, \x00 等控制字符
        bad_name = "US\u200d\u200e\ufe0f Fast\x00 Server\t"
        node = Node({"name": bad_name, "type": "vmess", "server": "1.2.3.4", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        processed = processor.process_all([node])
        self.assertEqual(len(processed), 1)
        # 控制字符应该被完全清除
        for bad_ch in ('\u200d', '\u200e', '\x00'):
            self.assertNotIn(bad_ch, processed[0].name)

    def test_processor_filter_notice_nodes(self):
        processor = NodeProcessor()
        node_ad1 = Node({"name": "飞机群-官方通知", "type": "vmess", "server": "1.2.3.4", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        node_ad2 = Node({"name": "节点不可用请更新订阅", "type": "vmess", "server": "1.2.3.5", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        node_ad3 = Node({"name": "流量耗尽请去官网充值", "type": "vmess", "server": "1.2.3.7", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        node_ad4 = Node({"name": "全节点禁止BT下载", "type": "vmess", "server": "1.2.3.8", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        node_ok = Node({"name": "US Normal Node", "type": "vmess", "server": "1.2.3.6", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"})
        processed = processor.process_all([node_ad1, node_ad2, node_ad3, node_ad4, node_ok])
        self.assertEqual(len(processed), 1)
        self.assertIn("US Normal Node", processed[0].name)

    def test_processor_deep_sanitize_nested_attributes(self):
        processor = NodeProcessor()
        # 模拟包含 C1 控制字符 (0x9F, 0x87) 的深层嵌套字段 (如 Shadowsocks obfs host)
        node = Node({
            "name": "US Fast SS",
            "type": "ss",
            "server": "88.210.36.106",
            "port": 2377,
            "cipher": "chacha20-ietf-poly1305",
            "password": "pwd",
            "plugin": "obfs",
            "plugin-opts": {
                "mode": "tls",
                "host": "(Telegram\x9F\x87 @WangCai2)f6e348d:70852"
            }
        })
        processed = processor.process_all([node])
        self.assertEqual(len(processed), 1)
        host_val = processed[0].data.get("plugin-opts", {}).get("host", "")
        self.assertNotIn("\x9F", host_val)
        self.assertNotIn("\x87", host_val)
        self.assertIn("@WangCai2", host_val)

    def test_private_node_anti_overwrite_and_crown_prefix(self):
        processor = NodeProcessor()
        # 公共节点与私有节点具有相同 identity
        public_node = Node({"name": "HK Public Node", "type": "ss", "server": "1.2.3.4", "port": 8388, "cipher": "aes-128-gcm", "password": "pwd"})
        private_node = Node({"name": "HK VIP Private", "type": "ss", "server": "1.2.3.4", "port": 8388, "cipher": "aes-128-gcm", "password": "pwd"})
        private_node.data['_is_private'] = True

        # 验证去重时私有节点优先保留
        deduped = processor.deduplicate([public_node, private_node])
        self.assertEqual(len(deduped), 1)
        self.assertTrue(deduped[0].data.get('_is_private'))

        # 验证命名清洗后带有 👑 标识
        processed = processor.process_all([private_node])
        self.assertTrue(processed[0].name.startswith("👑"))

    def test_processor_ss_plugin_opts_none_safety(self):
        processor = NodeProcessor()
        # 1. plugin-opts 显式为 None 的 v2ray-plugin 节点
        node_v2ray_none = Node({
            "name": "SS v2ray plugin with None opts",
            "type": "ss",
            "server": "1.2.3.4",
            "port": 8388,
            "cipher": "aes-128-gcm",
            "password": "pwd",
            "plugin": "v2ray-plugin",
            "plugin-opts": None
        })
        # 2. plugin-opts 显式为 None 的 obfs 节点
        node_obfs_none = Node({
            "name": "SS obfs with None opts",
            "type": "ss",
            "server": "1.2.3.5",
            "port": 8388,
            "cipher": "aes-128-gcm",
            "password": "pwd",
            "plugin": "obfs",
            "plugin-opts": None
        })
        # 3. 字段类型严重损毁的异常节点（验证 per-node try-except 容灾保护）
        node_corrupted = Node({
            "name": "Corrupted Node",
            "type": "ss",
            "server": "1.2.3.6",
            "port": 8388,
            "cipher": "aes-128-gcm",
            "password": "pwd",
            "plugin": 12345,  # 非法非字符串类型
            "plugin-opts": "invalid_string_not_dict"
        })

        valid = processor.filter_invalid([node_v2ray_none, node_obfs_none, node_corrupted])
        # 必须全部稳定处理，绝不发生 AttributeError 崩溃
        self.assertGreaterEqual(len(valid), 2)
        # v2ray-plugin 节点的 plugin-opts 应被安全修复为字典
        self.assertIsInstance(valid[0].data.get('plugin-opts'), dict)
        self.assertEqual(valid[0].data['plugin-opts'].get('mode'), 'websocket')

    def test_processor_process_all_step0_deep_sanitize_deduplication(self):
        processor = NodeProcessor()
        # 1. 验证带有零宽空格 \u200b 的相同节点能被精准去重
        node1 = Node({"name": "HK Node 1", "type": "ss", "server": "1.2.3.4", "port": 8388, "cipher": "aes-128-gcm", "password": "pwd"})
        # node2 在 server 属性末尾带有肉眼不可见的 \u200b 零宽空格
        node2 = Node({"name": "HK Node 2", "type": "ss", "server": "1.2.3.4\u200b", "port": 8388, "cipher": "aes-128-gcm", "password": "pwd"})

        processed = processor.process_all([node1, node2])
        # 经过 Step 0 预清洗后，两者 server 一致，去重后只应保留 1 个节点
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].data['server'], "1.2.3.4")

        # 2. 验证带有隐形字符的回环地址 127.0.0.1\u200b 无法绕过过滤
        node_evil = Node({"name": "Evil Node", "type": "ss", "server": "127.0.0.1\u200b", "port": 8388, "cipher": "aes-128-gcm", "password": "pwd"})
        processed_evil = processor.process_all([node_evil])
        self.assertEqual(len(processed_evil), 0)

    def test_strip_punct_regex(self):
        from core.processor import STRIP_PUNCT_REGEX
        test_cases = [
            ("| - _ / hello world / _ - |", "hello world"),
            ("···::node_name::···", "node_name"),
            ("   leading and trailing   ", "leading and trailing"),
            ("|/\\-·:_", "")
        ]
        for inp, expected in test_cases:
            self.assertEqual(STRIP_PUNCT_REGEX.sub('', inp).strip(), expected)

    def test_region_persistence_for_unmatched(self):
        processor = NodeProcessor()
        node_unmatched = Node({"name": "xyz_completely_random_node_123", "type": "ss", "server": "8.8.8.8", "port": 443, "cipher": "aes-128-gcm", "password": "p"})
        processor.clean_and_rename([node_unmatched])
        # 未匹配地区必须被明确持久化为 None，避免下游二次触发全量地区扫描
        self.assertIn('_region', node_unmatched.data)
        self.assertIsNone(node_unmatched.data['_region'])

    def test_port_boundaries_in_filter_invalid(self):
        processor = NodeProcessor()
        # 1. 有效端口：1, 65535, 字符串 "443"
        valid_nodes = [
            Node({"name": "P1", "type": "ss", "server": "8.8.4.4", "port": 1, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "P65535", "type": "ss", "server": "8.8.4.4", "port": 65535, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "PStr", "type": "ss", "server": "8.8.4.4", "port": "443", "cipher": "aes-128-gcm", "password": "p"}),
        ]
        res_valid = processor.filter_invalid(valid_nodes)
        self.assertEqual(len(res_valid), 3)
        self.assertEqual(res_valid[2].data['port'], 443)  # 转为整型

        # 2. 非法边界端口：0, 65536, -1, None, 异常字符串
        invalid_nodes = [
            Node({"name": "P0", "type": "ss", "server": "8.8.4.4", "port": 0, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "P65536", "type": "ss", "server": "8.8.4.4", "port": 65536, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "PNeg", "type": "ss", "server": "8.8.4.4", "port": -1, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "PNone", "type": "ss", "server": "8.8.4.4", "port": None, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "PBadStr", "type": "ss", "server": "8.8.4.4", "port": "not_a_port", "cipher": "aes-128-gcm", "password": "p"}),
        ]
        res_invalid = processor.filter_invalid(invalid_nodes)
        self.assertEqual(len(res_invalid), 0)

    def test_ipv6_loopback_in_filter_invalid(self):
        processor = NodeProcessor()
        # 拦截各类 IPv6 回环与未指定地址
        loopback_nodes = [
            Node({"name": "IPv6 Loopback 1", "type": "ss", "server": "::1", "port": 8388, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "IPv6 Loopback 2", "type": "ss", "server": "[::1]", "port": 8388, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "IPv6 Unspecified 1", "type": "ss", "server": "::", "port": 8388, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "IPv6 Unspecified 2", "type": "ss", "server": "[::]", "port": 8388, "cipher": "aes-128-gcm", "password": "p"}),
            Node({"name": "IPv4 Loopback DNS", "type": "ss", "server": "127.0.0.53", "port": 8388, "cipher": "aes-128-gcm", "password": "p"}),
        ]
        filtered = processor.filter_invalid(loopback_nodes)
        self.assertEqual(len(filtered), 0)

    def test_processor_group_names_anti_collision(self):
        from core.processor import GROUP_NAMES
        self.assertIn("👑 私有节点", GROUP_NAMES)
        self.assertIn("⚡ 自动选择 | 👑 私有节点", GROUP_NAMES)

        processor = NodeProcessor()
        # 节点原名与策略组完全重名
        conflict_node = Node({"name": "👑 私有节点", "type": "ss", "server": "8.8.4.4", "port": 443, "cipher": "aes-128-gcm", "password": "p"})
        processed = processor.process_all([conflict_node])
        self.assertEqual(len(processed), 1)
        # 必须被自动重命名，绝不能与 GROUP_NAMES 中的名字相同
        self.assertNotIn(processed[0].name, GROUP_NAMES)
        self.assertEqual(processed[0].name, "👑 私有节点 #1")

if __name__ == "__main__":
    unittest.main()
