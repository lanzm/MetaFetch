import unittest
from core.fetcher import Fetcher

class TestFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = Fetcher()

    def test_parse_content_uppercase_protocols(self):
        content = """
VMESS://eyJhZGQiOiIxLjIuMy40IiwicG9ydCI6NDQzLCJpZCI6ImEwMDAwMDAwLTAwMDAtMDAwMC0wMDAwLTAwMDAwMDAwMDAwMCIsInBzIjoiVXBwZXJWbWVzcyJ9
HY2://pwd123@1.2.3.4:443#UpperHy2
VLESS://a0000000-0000-0000-0000-000000000000@1.2.3.4:443#UpperVless
SS://YWVzLTI1Ni1nY206cHdkMTIz@1.2.3.4:8388#UpperSS
"""
        nodes = self.fetcher.parse_content(content)
        self.assertEqual(len(nodes), 4)
        types = {n.type for n in nodes}
        self.assertIn("vmess", types)
        self.assertIn("hysteria2", types)
        self.assertIn("vless", types)
        self.assertIn("ss", types)

    def test_parse_content_html_skip(self):
        html_content = "<!DOCTYPE html><html><body>vmess://invalid</body></html>"
        nodes = self.fetcher.parse_content(html_content)
        self.assertEqual(len(nodes), 0)

    def test_parse_content_yaml(self):
        yaml_content = """
proxies:
  - name: YAML_Node_1
    type: vmess
    server: 1.2.3.4
    port: 443
    uuid: a0000000-0000-0000-0000-000000000000
"""
        nodes = self.fetcher.parse_content(yaml_content)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "YAML_Node_1")

if __name__ == "__main__":
    unittest.main()
