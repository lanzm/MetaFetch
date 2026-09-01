import unittest
from utils.common import b64encodes, b64decodes, b64decodes_safe

class TestCommon(unittest.TestCase):
    def test_b64encodes_and_decodes(self):
        raw = "hello world"
        encoded = b64encodes(raw)
        self.assertEqual(b64decodes(encoded), raw)

    def test_b64decodes_missing_padding(self):
        raw = "vmess://eyJhZGQiOiIxMjcuMC4wLjEiLCJwb3J0IjoiNDQzIn0"
        decoded = b64decodes(raw[8:])
        self.assertIn("127.0.0.1", decoded)

    def test_b64decodes_empty_or_invalid(self):
        self.assertEqual(b64decodes(""), "")
        self.assertEqual(b64decodes("!!!invalid_base64!!!"), "")

    def test_b64decodes_with_whitespace(self):
        raw = "hello whitespace test"
        encoded = "  \r\n" + b64encodes(raw) + " \n\r "
        self.assertEqual(b64decodes(encoded), raw)
        self.assertEqual(b64decodes_safe(encoded), raw)

if __name__ == "__main__":
    unittest.main()
