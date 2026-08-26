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

        # Sing-box 格式导出
        sb_cfg = node.to_singbox()
        self.assertEqual(sb_cfg["tag"], "Node_Vmess_Test")
        self.assertEqual(sb_cfg["type"], "vmess")

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

    def test_node_from_hysteria2_url(self):
        hy2_url = "hysteria2://password123@1.2.3.4:443?sni=example.com&insecure=1#Node_Hy2_Test"
        node = Node(hy2_url)
        self.assertEqual(node.type, "hysteria2")
        self.assertEqual(node.name, "Node_Hy2_Test")
        self.assertEqual(node.data["server"], "1.2.3.4")
        self.assertEqual(node.data["password"], "password123")

if __name__ == "__main__":
    unittest.main()
