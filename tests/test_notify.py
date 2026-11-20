import unittest
from unittest.mock import patch, MagicMock
from utils.notify import format_tg_summary, send_tg_notification

class TestNotify(unittest.TestCase):
    def test_format_tg_summary_normal(self):
        gen_stats = {
            'total_nodes': 950,
            'region_nodes': {'HK': ['n1', 'n2'], 'US': ['n3']},
            'others': ['n4'],
            'timestamp': '2026-10-19 08:30:00',
            'source_count': 12,
            'raw_count': 1600,
            'elapsed_time': 5.23,
        }
        text = format_tg_summary(gen_stats)
        self.assertIn("<b>950</b>", text)
        self.assertIn("<code>2026-10-19 08:30:00</code>", text)
        self.assertIn("🇭🇰 香港 2", text)
        self.assertIn("🇺🇸 美国 1", text)
        self.assertIn("🌍 其他 1", text)
        self.assertIn("https://github.com/lanzm/MetaFetch", text)

    def test_format_tg_summary_html_escaping(self):
        # 验证插入的特殊 HTML 字符不会破坏 Telegram HTML 解析，而是被正确转义
        gen_stats = {
            'total_nodes': 100,
            'region_nodes': {
                'CUSTOM': ['n1'],  # REGION_NAMES 中未包含，直接取 key 作为名字
            },
            'others': [],
            'timestamp': '2026-10-19 <UTC> & "alert"',
            'source_count': 1,
            'raw_count': 100,
            'elapsed_time': 1.0,
        }
        # 模拟自定义地区名包含特殊字符
        from utils.regions import REGION_NAMES
        REGION_NAMES['CUSTOM'] = '🏴 地区 <Test & Demo>'

        try:
            text = format_tg_summary(gen_stats)
            # 1. 验证时间戳中的 <, >, & 均被转义
            self.assertNotIn('<UTC>', text)
            self.assertIn('&lt;UTC&gt;', text)
            self.assertIn('&amp;', text)

            # 2. 验证地区名称中的 <, > 和 & 被正确转义
            self.assertNotIn('<Test & Demo>', text)
            self.assertIn('&lt;Test &amp; Demo&gt;', text)

            # 3. 验证既有的 Telegram 格式化标签未受影响
            self.assertIn('<b>MetaFetch 节点自动抓取更新通知</b>', text)
            self.assertIn('<code>', text)
            self.assertIn('</code>', text)
        finally:
            REGION_NAMES.pop('CUSTOM', None)

    @patch.dict('os.environ', {}, clear=True)
    def test_send_tg_notification_missing_env(self):
        # 缺少 TG_BOT_TOKEN 或 TG_CHAT_ID 时静默返回 False，不抛出任何异常
        self.assertFalse(send_tg_notification("test"))

    @patch.dict('os.environ', {'TG_BOT_TOKEN': '  bot123456:ABC-DEF  \n', 'TG_CHAT_ID': '  -10012345678  '}, clear=True)
    @patch('urllib.request.urlopen')
    def test_send_tg_notification_token_cleanup_and_mock_send(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true, "result": {"message_id": 999}}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = send_tg_notification("Hello MetaFetch Notification")
        self.assertTrue(res)

        # 验证 urlopen 请求的 URL 正确剥离了多余空白与 'bot' 前缀
        req = mock_urlopen.call_args[0][0]
        self.assertIn("api.telegram.org/bot123456:ABC-DEF/", req.full_url)
        self.assertTrue("sendMessage" in req.full_url or "editMessageText" in req.full_url)
        payload = req.data.decode('utf-8')
        self.assertIn('"chat_id": "-10012345678"', payload)

    @patch.dict('os.environ', {'TG_BOT_TOKEN': '123456:ABC', 'TG_CHAT_ID': '-100123'}, clear=True)
    @patch('time.sleep', return_value=None)
    @patch('urllib.request.urlopen')
    def test_send_tg_notification_existing_id_does_not_fallback(self, mock_urlopen, mock_sleep):
        # 当存在已有看板 ID 且 editMessageText 失败时，严禁 fallback 到 sendMessage 创建新消息
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection timed out")

        # 模拟存在已有 msg_id
        with patch('builtins.open', unittest.mock.mock_open(read_data="203")), \
             patch('os.path.exists', return_value=True):
            res = send_tg_notification("Test Content")

        self.assertFalse(res)
        # 验证调用了 3 次 editMessageText 重试，但绝未调用 sendMessage
        self.assertEqual(mock_urlopen.call_count, 3)
        for call in mock_urlopen.call_args_list:
            req = call[0][0]
            self.assertIn("editMessageText", req.full_url)
            self.assertNotIn("sendMessage", req.full_url)

    @patch.dict('os.environ', {'TG_BOT_TOKEN': '123456:ABC', 'TG_CHAT_ID': '-100123'}, clear=True)
    @patch('urllib.request.urlopen')
    def test_send_tg_notification_no_id_creates_new(self, mock_urlopen):
        # 当不存在 msg_id 时，调用 sendMessage 发送新消息并保存 ID
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true, "result": {"message_id": 300}}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        m_open = unittest.mock.mock_open(read_data="")
        with patch('builtins.open', m_open), patch('os.path.exists', return_value=False):
            res = send_tg_notification("Init Content")

        self.assertTrue(res)
        req = mock_urlopen.call_args[0][0]
        self.assertIn("sendMessage", req.full_url)
        # 验证新 ID 被写回文件
        m_open().write.assert_called_once_with("300")

if __name__ == '__main__':
    unittest.main()
