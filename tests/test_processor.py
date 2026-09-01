# -*- coding: utf-8 -*-
import unittest
from core.parser import Node
from core.processor import NodeProcessor

class TestProcessor(unittest.TestCase):
    def test_processor_filter_invalid_servers(self):
        processor = NodeProcessor()
        nodes = [
            Node({"name": "Node_Valid", "type": "vmess", "server": "1.2.3.4", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Loopback1", "type": "vmess", "server": "127.0.0.1", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Loopback2", "type": "vmess", "server": "0.0.0.0", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_Localhost", "type": "vmess", "server": "localhost", "port": 443, "uuid": "a0000000-0000-0000-0000-000000000000"}),
            Node({"name": "Node_NoUUID", "type": "vmess", "server": "1.2.3.4", "port": 443}),
            Node({"name": "Node_BadPort", "type": "vmess", "server": "1.2.3.4", "port": -1, "uuid": "a0000000-0000-0000-0000-000000000000"}),
        ]
        valid = processor.filter_invalid(nodes)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].name, "Node_Valid")

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

if __name__ == "__main__":
    unittest.main()
