import json
import unittest
from core.parser import Node
from utils.common import b64encodes

class TestParser(unittest.TestCase):
    def test_node_from_vmess_url(self):
        vmess_dict = {
            "v": "2",
            "ps": "Node_Vmess_Test",
            "add": "1.2.3.4",
            "port": "443",
            "id": "a0000000-0000-0000-0000-000000000000",
            "aid": "0",
            "net": "ws",
            "type": "none",
            "host": "example.com",
            "path": "/ws",
            "tls": "tls"
        }
        raw_url = "vmess://" + b64encodes(json.dumps(vmess_dict))
        
        node = Node(raw_url)
        self.assertEqual(node.name, "Node_Vmess_Test")
        self.assertEqual(node.type, "vmess")
        self.assertEqual(node.data["server"], "1.2.3.4")
        self.assertEqual(node.data["port"], 443)

        # Clash 格式导出
        clash_cfg = node.to_clash()
        self.assertEqual(clash_cfg["name"], "Node_Vmess_Test")
        self.assertEqual(clash_cfg["type"], "vmess")
        self.assertEqual(clash_cfg["server"], "1.2.3.4")
        self.assertEqual(clash_cfg["uuid"], "a0000000-0000-0000-0000-000000000000")

    def test_node_from_vless_url(self):
        vless_url = "vless://a0000000-0000-0000-0000-000000000000@1.2.3.4:443?encryption=none&security=reality&sni=yahoo.com&fp=chrome&pbk=123456&type=tcp#Node_Vless_Test"
        node = Node(vless_url)
        self.assertEqual(node.type, "vless")
        self.assertEqual(node.name, "Node_Vless_Test")
        self.assertEqual(node.data["server"], "1.2.3.4")
        self.assertEqual(node.data["port"], 443)
        self.assertEqual(node.data.get("reality-opts", {}).get("public-key"), "123456")

    def test_node_from_ss_url(self):
        userinfo = b64encodes("aes-256-gcm:password123")
        ss_url = f"ss://{userinfo}@1.2.3.4:8388#Node_SS_Test"
        node = Node(ss_url)
        self.assertEqual(node.type, "ss")
        self.assertEqual(node.name, "Node_SS_Test")
        self.assertEqual(node.data["server"], "1.2.3.4")
        self.assertEqual(node.data["cipher"], "aes-256-gcm")
        self.assertEqual(node.data["password"], "password123")

    def test_node_from_trojan_url(self):
        trojan_url = "trojan://password123@1.2.3.4:443?sni=example.com#Node_Trojan_Test"
        node = Node(trojan_url)
        self.assertEqual(node.type, "trojan")
        self.assertEqual(node.name, "Node_Trojan_Test")
        self.assertEqual(node.data["server"], "1.2.3.4")
        self.assertEqual(node.data["password"], "password123")

    def test_protocol_case_insensitivity(self):
        # 1. 大写 HY2:// 协议正常加载
        hy2_url = "HY2://password123@1.2.3.4:443#Uppercase_HY2"
        node = Node(hy2_url)
        self.assertEqual(node.type, "hysteria2")
        self.assertEqual(node.data["server"], "1.2.3.4")

        # 2. 混合大小写 Hy2://
        hy2_mixed = "Hy2://password123@1.2.3.4:443#Mixed_HY2"
        node_mixed = Node(hy2_mixed)
        self.assertEqual(node_mixed.type, "hysteria2")

        # 3. 大写 VLESS://
        vless_upper = "VLESS://a0000000-0000-0000-0000-000000000000@1.2.3.4:443#Upper_VLESS"
        node_vless = Node(vless_upper)
        self.assertEqual(node_vless.type, "vless")

    def test_omitted_port_default_443(self):
        # Trojan 省略端口
        trojan_no_port = "trojan://password123@example.com?sni=example.com#Trojan_No_Port"
        node_trojan = Node(trojan_no_port)
        self.assertEqual(node_trojan.data["port"], 443)
        self.assertTrue(node_trojan.data["tls"])

        # VLESS 省略端口
        vless_no_port = "vless://a0000000-0000-0000-0000-000000000000@example.com#Vless_No_Port"
        node_vless = Node(vless_no_port)
        self.assertEqual(node_vless.data["port"], 443)

if __name__ == "__main__":
    unittest.main()
