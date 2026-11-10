import json
import unittest
from core.parser import Node
from utils.common import b64encodes, b64decodes

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
        self.assertTrue(clash_cfg["tls"])

    def test_node_from_vmess_tls_compatibility(self):
        base_dict = {
            "v": "2",
            "ps": "VMess_TLS_Test",
            "add": "1.2.3.4",
            "port": "443",
            "id": "a0000000-0000-0000-0000-000000000000",
            "net": "WS",
            "path": "/ws"
        }

        # 1. 各种代表开启 TLS 的取值
        for val in ("tls", "TLS", "true", "True", True, "1", 1):
            d = dict(base_dict, tls=val)
            node = Node("vmess://" + b64encodes(json.dumps(d)))
            self.assertTrue(node.data["tls"], f"Failed for tls={repr(val)}")
            self.assertEqual(node.data["network"], "ws")
            self.assertIn("ws-opts", node.data)

        # 2. 各种代表未开启 TLS 的取值
        for val in ("", "none", "false", False, "0", 0, None):
            d = dict(base_dict, tls=val)
            node = Node("vmess://" + b64encodes(json.dumps(d)))
            self.assertFalse(node.data["tls"], f"Failed for tls={repr(val)}")

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
        self.assertEqual(node.data["port"], 8388)

    def test_node_from_ss_url_with_trailing_slash(self):
        userinfo = b64encodes("aes-256-gcm:password123")
        
        # 1. 尾部直接带斜杠: server:port/#name
        url1 = f"ss://{userinfo}@1.2.3.4:8388/#Node_Slash"
        node1 = Node(url1)
        self.assertEqual(node1.type, "ss")
        self.assertEqual(node1.data["port"], 8388)
        self.assertEqual(node1.data["server"], "1.2.3.4")

        # 2. 带 query 参数并在 query 前带斜杠: server:port/?plugin=...#name
        url2 = f"ss://{userinfo}@1.2.3.4:8388/?plugin=obfs-local#Node_Query_Slash"
        node2 = Node(url2)
        self.assertEqual(node2.type, "ss")
        self.assertEqual(node2.data["port"], 8388)
        self.assertEqual(node2.data["server"], "1.2.3.4")
        self.assertEqual(node2.data.get("plugin"), "obfs")

        # 3. 整串 Base64 解码后带斜杠 (SIP002 标准)
        b64_full = b64encodes("aes-256-gcm:password123@1.2.3.4:8388/")
        url3 = f"ss://{b64_full}#Node_Full_B64_Slash"
        node3 = Node(url3)
        self.assertEqual(node3.type, "ss")
        self.assertEqual(node3.data["port"], 8388)
        self.assertEqual(node3.data["server"], "1.2.3.4")

        # 4. IPv6 地址带斜杠: [2001:db8::1]:8388/#name
        url4 = f"ss://{userinfo}@[2001:db8::1]:8388/#Node_IPv6_Slash"
        node4 = Node(url4)
        self.assertEqual(node4.type, "ss")
        self.assertEqual(node4.data["port"], 8388)
        self.assertEqual(node4.data["server"], "2001:db8::1")

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

    def test_none_nested_dicts_and_empty_port_strings(self):
        # 1. 节点字典中显式包含 null 嵌套字典
        raw_dict = {
            "name": "Node_Null_Opts",
            "type": "vmess",
            "server": "1.2.3.4",
            "port": 443,
            "uuid": "a0000000-0000-0000-0000-000000000000",
            "ws-opts": None,
            "grpc-opts": None,
            "reality-opts": None
        }
        node = Node(raw_dict)
        self.assertEqual(node.type, "vmess")
        # 验证 to_url 和 get_identity 不会抛出 AttributeError
        url = node.to_url()
        self.assertTrue(url.startswith("vmess://"))
        ident = node.get_identity()
        self.assertIn("vmess", ident)

        # 2. VMess JSON 中的 port / aid 为空字符串
        vmess_empty_port = {
            "v": "2", "ps": "VMess_Empty", "add": "1.2.3.4",
            "port": "", "id": "a0000000-0000-0000-0000-000000000000", "aid": ""
        }
        node_empty = Node("vmess://" + b64encodes(json.dumps(vmess_empty_port)))
        self.assertEqual(node_empty.data["port"], 0)
        self.assertEqual(node_empty.data["alterId"], 0)

    def test_node_type_normalization(self):
        # 验证大写与变体协议自动归一化
        node_vmess = Node({"name": "Test1", "type": "VMESS", "server": "1.1.1.1", "port": 443})
        self.assertEqual(node_vmess.type, "vmess")
        self.assertEqual(node_vmess.data["type"], "vmess")

        node_hy2 = Node({"name": "Test2", "type": "Hy2", "server": "1.1.1.1", "port": 443})
        self.assertEqual(node_hy2.type, "hysteria2")
        self.assertEqual(node_hy2.data["type"], "hysteria2")

    def test_vmess_to_url_none_fields(self):
        node = Node({"name": "Vmess_None", "type": "vmess", "server": "1.1.1.1", "port": None, "alterId": None})
        url = node.to_url()
        self.assertTrue(url.startswith("vmess://"))
        payload = json.loads(b64decodes(url[8:]))
        self.assertEqual(payload["port"], "443")
        self.assertEqual(payload["aid"], "0")
        self.assertNotEqual(payload["aid"], "None")

    def test_get_identity_with_plugin_and_obfs(self):
        # 1. 验证 SS 节点在带有插件时与无插件节点指纹互斥
        ss_base = {"name": "SS1", "type": "ss", "server": "1.2.3.4", "port": 8388, "cipher": "aes-256-gcm", "password": "pwd"}
        ss_plugin = dict(ss_base, plugin="obfs", **{"plugin-opts": {"mode": "http", "host": "bing.com"}})
        ss_v2ray = dict(ss_base, plugin="v2ray-plugin", **{"plugin-opts": {"mode": "websocket", "host": "example.com"}})

        node_base = Node(ss_base)
        node_plugin = Node(ss_plugin)
        node_v2ray = Node(ss_v2ray)

        self.assertNotEqual(node_base.get_identity(), node_plugin.get_identity())
        self.assertNotEqual(node_plugin.get_identity(), node_v2ray.get_identity())
        self.assertIn("plugin:obfs", node_plugin.get_identity())
        self.assertIn("pmod:http", node_plugin.get_identity())
        self.assertIn("phost:bing.com", node_plugin.get_identity())
        self.assertIn("plugin:v2ray-plugin", node_v2ray.get_identity())

        # 2. 验证 Hysteria2 节点在带有混淆时与无混淆节点指纹互斥
        hy2_base = {"name": "HY1", "type": "hysteria2", "server": "1.2.3.4", "port": 443, "password": "pwd"}
        hy2_obfs = dict(hy2_base, obfs="salamander", **{"obfs-password": "secret_password"})

        node_hy2_base = Node(hy2_base)
        node_hy2_obfs = Node(hy2_obfs)

        self.assertNotEqual(node_hy2_base.get_identity(), node_hy2_obfs.get_identity())
        self.assertIn("obfs:salamander", node_hy2_obfs.get_identity())
        self.assertIn("opwd:secret_password", node_hy2_obfs.get_identity())

        # 3. 相同特征的指纹完全一致且相等
        node_hy2_obfs_clone = Node(dict(hy2_obfs, name="HY_Different_Name"))
        self.assertEqual(node_hy2_obfs.get_identity(), node_hy2_obfs_clone.get_identity())
        self.assertEqual(node_hy2_obfs, node_hy2_obfs_clone)

    def test_sni_and_servername_unification(self):
        # 1. VLESS: sni 与 servername 双向同步且 to_url 完整导出
        vless_dict = {
            "name": "Vless_SNI", "type": "vless", "server": "1.2.3.4", "port": 443,
            "uuid": "a0000000-0000-0000-0000-000000000000", "tls": True, "sni": "vless.example.com"
        }
        node_vless = Node(vless_dict)
        self.assertEqual(node_vless.data["sni"], "vless.example.com")
        self.assertEqual(node_vless.data["servername"], "vless.example.com")
        self.assertIn("sni=vless.example.com", node_vless.to_url())

        # 2. Trojan: 输入 servername 自动同步至 sni 并在 to_url 导出
        trojan_dict = {
            "name": "Trojan_Servername", "type": "trojan", "server": "1.2.3.4", "port": 443,
            "password": "pwd", "servername": "trojan.example.com"
        }
        node_trojan = Node(trojan_dict)
        self.assertEqual(node_trojan.data["sni"], "trojan.example.com")
        self.assertIn("sni=trojan.example.com", node_trojan.to_url())

        # 3. Hysteria2: 输入 servername 自动同步并在 to_url 导出
        hy2_dict = {
            "name": "HY2_SNI", "type": "hysteria2", "server": "1.2.3.4", "port": 443,
            "password": "pwd", "servername": "hy2.example.com"
        }
        node_hy2 = Node(hy2_dict)
        self.assertEqual(node_hy2.data["sni"], "hy2.example.com")
        self.assertIn("sni=hy2.example.com", node_hy2.to_url())

        # 4. 指纹对齐：采用 sni 还是 servername 生成的去重指纹完全一致
        node_trojan_sni = Node(dict(trojan_dict, sni="trojan.example.com", servername=None))
        self.assertEqual(node_trojan.get_identity(), node_trojan_sni.get_identity())

    def test_trojan_with_reality_opts(self):
        url = "trojan://mypass@1.2.3.4:443?security=reality&sni=test.com&pbk=my_pub_key&sid=1234abcd#Trojan_Reality"
        node = Node(url)
        self.assertEqual(node.type, "trojan")
        self.assertTrue(node.data.get("tls"))
        ropts = node.data.get("reality-opts")
        self.assertIsNotNone(ropts)
        self.assertEqual(ropts["public-key"], "my_pub_key")
        self.assertEqual(ropts["short-id"], "1234abcd")

    def test_vmess_cipher_whitelist(self):
        # 1. 字典输入非法 cipher 回退至 auto
        node_bad = Node({"name": "bad", "type": "vmess", "cipher": "invalid-cipher-xyz"})
        self.assertEqual(node_bad.data["cipher"], "auto")

        # 2. 字典输入合法 cipher 保持原样
        node_good = Node({"name": "good", "type": "vmess", "cipher": "chacha20-poly1305"})
        self.assertEqual(node_good.data["cipher"], "chacha20-poly1305")

        # 3. URL 输入非法 scy 回退至 auto
        vmess_dict = {
            "v": "2", "ps": "test", "add": "1.2.3.4", "port": "443",
            "id": "a0000000-0000-0000-0000-000000000000", "scy": "unknown_crypto"
        }
        node_url = Node("vmess://" + b64encodes(json.dumps(vmess_dict)))
        self.assertEqual(node_url.data["cipher"], "auto")

    def test_identity_cache(self):
        node = Node({"name": "Test", "type": "ss", "server": "1.2.3.4", "port": 8388, "cipher": "aes-128-gcm", "password": "pwd"})
        self.assertIsNone(node._identity_cache)
        ident1 = node.get_identity()
        self.assertIsNotNone(node._identity_cache)
        self.assertEqual(node._identity_cache, ident1)
        # 第二次调用直接走缓存
        ident2 = node.get_identity()
        self.assertEqual(ident1, ident2)

    def test_vless_ws_host_and_grpc_service_name(self):
        # 1. VLESS WebSocket with host
        url_ws = "vless://uuid-123@example.com:443?type=ws&path=%2Fws-path&host=ws.example.com&security=tls#VlessWS"
        node_ws = Node(url_ws)
        self.assertEqual(node_ws.data["network"], "ws")
        self.assertEqual(node_ws.data["ws-opts"]["path"], "/ws-path")
        self.assertEqual(node_ws.data["ws-opts"]["headers"]["Host"], "ws.example.com")
        out_ws_url = node_ws.to_url()
        self.assertIn("host=ws.example.com", out_ws_url)
        self.assertIn("path=/ws-path", out_ws_url)

        # 2. VLESS gRPC with serviceName
        url_grpc = "vless://uuid-456@example.com:443?type=grpc&serviceName=api.v1.FeedS&security=tls#VlessGRPC"
        node_grpc = Node(url_grpc)
        self.assertEqual(node_grpc.data["network"], "grpc")
        self.assertEqual(node_grpc.data["grpc-opts"]["grpc-service-name"], "api.v1.FeedS")
        out_grpc_url = node_grpc.to_url()
        self.assertIn("serviceName=api.v1.FeedS", out_grpc_url)

    def test_trojan_ws_and_grpc(self):
        # Trojan WebSocket
        url_ws = "trojan://pwd123@example.com:443?type=ws&path=%2Ftrojan-ws&host=trojan.host#TrojanWS"
        node_ws = Node(url_ws)
        self.assertEqual(node_ws.data["network"], "ws")
        self.assertEqual(node_ws.data["ws-opts"]["path"], "/trojan-ws")
        self.assertEqual(node_ws.data["ws-opts"]["headers"]["Host"], "trojan.host")
        out_ws_url = node_ws.to_url()
        self.assertIn("type=ws", out_ws_url)
        self.assertIn("host=trojan.host", out_ws_url)

        # Trojan gRPC
        url_grpc = "trojan://pwd456@example.com:443?type=grpc&serviceName=trojan-service#TrojanGRPC"
        node_grpc = Node(url_grpc)
        self.assertEqual(node_grpc.data["network"], "grpc")
        self.assertEqual(node_grpc.data["grpc-opts"]["grpc-service-name"], "trojan-service")
        out_grpc_url = node_grpc.to_url()
        self.assertIn("serviceName=trojan-service", out_grpc_url)

    def test_hysteria2_auth_and_insecure(self):
        # Hysteria2 insecure=1 -> skip-cert-verify
        url_hy2 = "hy2://pwd789@example.com:443?insecure=1&sni=sni.com#Hy2Test"
        node_hy2 = Node(url_hy2)
        self.assertTrue(node_hy2.data.get("skip-cert-verify"))
        out_hy2_url = node_hy2.to_url()
        self.assertIn("insecure=1", out_hy2_url)

        # Hysteria2 with auth in dict (sing-box style)
        from core.processor import NodeProcessor
        p = NodeProcessor()
        valid = p.filter_invalid([Node({"name": "hy2-auth", "type": "hysteria2", "server": "1.2.3.4", "port": 443, "auth": "secret-auth"})])
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].data["password"], "secret-auth")

if __name__ == "__main__":
    unittest.main()

