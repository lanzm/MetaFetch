import unittest
from utils.ciphers import (
    normalize_ss_cipher,
    is_valid_ss_cipher,
    validate_and_normalize_ss_2022_key,
    SS_CIPHER_ALIASES,
    VALID_SS_CIPHERS,
    SS_2022_KEY_LENGTHS,
)
from core.parser import Node
from core.processor import NodeProcessor

class TestCiphers(unittest.TestCase):
    def test_normalize_ss_cipher_aliases(self):
        # 常见漏写 ietf 的情况
        self.assertEqual(normalize_ss_cipher('chacha20-poly1305'), 'chacha20-ietf-poly1305')
        self.assertEqual(normalize_ss_cipher('CHACHA20-POLY1305'), 'chacha20-ietf-poly1305')
        self.assertEqual(normalize_ss_cipher('chacha20-ietf-poly-1305'), 'chacha20-ietf-poly1305')
        self.assertEqual(normalize_ss_cipher('xchacha20-poly1305'), 'xchacha20-ietf-poly1305')
        
        # 常见缺少连字符的情况
        self.assertEqual(normalize_ss_cipher('aes128-gcm'), 'aes-128-gcm')
        self.assertEqual(normalize_ss_cipher('aes256-gcm'), 'aes-256-gcm')
        self.assertEqual(normalize_ss_cipher('rc4md5'), 'rc4-md5')

    def test_normalize_ss_cipher_standard(self):
        # 原生合法标准算法保持不变
        self.assertEqual(normalize_ss_cipher('aes-128-gcm'), 'aes-128-gcm')
        self.assertEqual(normalize_ss_cipher('chacha20-ietf-poly1305'), 'chacha20-ietf-poly1305')
        self.assertEqual(normalize_ss_cipher('2022-blake3-aes-128-gcm'), '2022-blake3-aes-128-gcm')

    def test_normalize_empty_or_none(self):
        self.assertEqual(normalize_ss_cipher(''), '')
        self.assertEqual(normalize_ss_cipher(None), '')

    def test_is_valid_ss_cipher(self):
        self.assertTrue(is_valid_ss_cipher('chacha20-ietf-poly1305'))
        self.assertTrue(is_valid_ss_cipher('chacha20-poly1305'))  # 自动归一化后合法
        self.assertTrue(is_valid_ss_cipher('aes-256-gcm'))
        self.assertTrue(is_valid_ss_cipher('2022-blake3-aes-256-gcm'))
        self.assertFalse(is_valid_ss_cipher('unknown-cipher-xyz'))
        self.assertFalse(is_valid_ss_cipher(''))
        self.assertFalse(is_valid_ss_cipher(None))

    def test_node_init_dict_cipher_normalization(self):
        # 模拟从上游 Clash YAML 加载的字典节点（即用户遇到的报错场景）
        raw_dict = {
            'name': 'Test-SS-Node',
            'type': 'ss',
            'server': '78.38.246.150',
            'port': 8446,
            'cipher': 'chacha20-poly1305',
            'password': 'password123'
        }
        node = Node(raw_dict)
        self.assertEqual(node.data['cipher'], 'chacha20-ietf-poly1305')

    def test_node_load_url_cipher_normalization(self):
        # 模拟从 ss:// 链接加载
        # base64(chacha20-poly1305:password123) = Y2hhY2hhMjAtcG9seTEzMDU6cGFzc3dvcmQxMjM=
        url = 'ss://Y2hhY2hhMjAtcG9seTEzMDU6cGFzc3dvcmQxMjM=@78.38.246.150:8446#TestSS'
        node = Node(url)
        self.assertEqual(node.data['cipher'], 'chacha20-ietf-poly1305')

    def test_processor_filter_and_clean_ss_node(self):
        proc = NodeProcessor()
        
        # 1. 带非标准 cipher 的节点应成功修正并通过过滤
        node_bad_cipher = Node({
            'name': '🇺🇸 US-Test',
            'type': 'ss',
            'server': '78.38.246.150',
            'port': 8446,
            'cipher': 'chacha20-poly1305',
            'password': 'pwd'
        })
        # 2. 完全非法 cipher 的节点应被剔除
        node_invalid = Node({
            'name': 'Invalid-SS',
            'type': 'ss',
            'server': '1.2.3.4',
            'port': 8388,
            'cipher': 'totally-bogus-cipher',
            'password': 'pwd'
        })
        
        valid = proc.filter_invalid([node_bad_cipher, node_invalid])
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].data['cipher'], 'chacha20-ietf-poly1305')

        # 3. clean_and_rename 同样保证正确性
        cleaned = proc.clean_and_rename(valid)
        self.assertEqual(cleaned[0].data['cipher'], 'chacha20-ietf-poly1305')

    def test_ss_2022_key_validation_and_normalization(self):
        # 1. 测试真实报错用例：带 %3D 编码且符合 32 字节长度的 SS 2022 密钥
        raw_key = 'qG5HzrJO2OAzMFY6WDz991qHHonSP2ix6l6jKlHwokY%3D'
        expected_key = 'qG5HzrJO2OAzMFY6WDz991qHHonSP2ix6l6jKlHwokY='
        norm = validate_and_normalize_ss_2022_key('2022-blake3-chacha20-poly1305', raw_key)
        self.assertEqual(norm, expected_key)

        # 2. 测试丢失 padding 的情况（43 位，缺少最后的 =）
        unpadded_key = 'qG5HzrJO2OAzMFY6WDz991qHHonSP2ix6l6jKlHwokY'
        norm2 = validate_and_normalize_ss_2022_key('2022-blake3-chacha20-poly1305', unpadded_key)
        self.assertEqual(norm2, expected_key)

        # 3. 测试 128 位算法 (16 字节密钥)
        aes128_key = 'jUbDNsFamcyDfpm+rI3Zyw=='
        self.assertEqual(validate_and_normalize_ss_2022_key('2022-blake3-aes-128-gcm', aes128_key), aes128_key)

        # 4. 长度不符的情况（将 16 字节密钥用于 32 字节算法，或非法字符）
        self.assertIsNone(validate_and_normalize_ss_2022_key('2022-blake3-aes-256-gcm', aes128_key))
        self.assertIsNone(validate_and_normalize_ss_2022_key('2022-blake3-chacha20-poly1305', 'not-a-valid-base64!@#'))
        self.assertIsNone(validate_and_normalize_ss_2022_key('2022-blake3-chacha20-poly1305', ''))

    def test_processor_ss_2022_filter_and_sanitize(self):
        proc = NodeProcessor()
        # 模拟包含 %3D 的 SS 2022 缺陷节点
        node_escaped = Node({
            'name': 'US-SS2022',
            'type': 'ss',
            'server': '129.146.61.90',
            'port': 50356,
            'cipher': '2022-blake3-chacha20-poly1305',
            'password': 'qG5HzrJO2OAzMFY6WDz991qHHonSP2ix6l6jKlHwokY%3D'
        })
        # 模拟非法 key 的 SS 2022 节点
        node_broken_key = Node({
            'name': 'Broken-SS2022',
            'type': 'ss',
            'server': '1.1.1.1',
            'port': 1234,
            'cipher': '2022-blake3-chacha20-poly1305',
            'password': 'invalid_secret_key'
        })
        filtered = proc.filter_invalid([node_escaped, node_broken_key])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].data['password'], 'qG5HzrJO2OAzMFY6WDz991qHHonSP2ix6l6jKlHwokY=')

    def test_ss_url_load_with_escaped_password(self):
        # 模拟从 ss:// 导入包含 URL 编码 password 的情况
        url = 'ss://MjAyMi1ibGFrZTMtY2hhY2hhMjAtcG9seTEzMDU6cUc1SHpySk8yT0F6TUZZNldEejk5MXFISG9uU1AyaXg2bDZqS2xId29rWSUzRA==@129.146.61.90:50356#US-Test'
        node = Node(url)
        self.assertEqual(node.data['password'], 'qG5HzrJO2OAzMFY6WDz991qHHonSP2ix6l6jKlHwokY=')

if __name__ == '__main__':
    unittest.main()
