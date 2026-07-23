import os
import re
import urllib.request
import urllib.parse

def send_tg_notification():
    raw_token = os.environ.get('TG_BOT_TOKEN', '')
    raw_chat_id = os.environ.get('TG_CHAT_ID', '')
    
    # 彻底过滤多余空格、换行符等控制字符
    token = re.sub(r'\s+', '', raw_token)
    chat_id = re.sub(r'\s+', '', raw_chat_id)
    
    # 自动切除可能误多复制的 'bot' 前缀
    if token.lower().startswith('bot'):
        token = token[3:]
        
    if not token or not chat_id:
        print("[WARNING] TG_BOT_TOKEN or TG_CHAT_ID is missing in environment variables. Skipping Telegram notification.")
        return
        
    if not os.path.exists("tg_summary.txt"):
        print("[WARNING] tg_summary.txt not found. Skipping Telegram notification.")
        return

    with open("tg_summary.txt", "r", encoding="utf-8") as f:
        text = f.read()

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': 'true'
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data)
    try:
        urllib.request.urlopen(req)
        print("[OK] Telegram notification sent successfully!")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8') if e.fp else str(e)
        print(f"[ERROR] Telegram API HTTP Error {e.code}: {err_msg}")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram notification: {e}")

if __name__ == "__main__":
    send_tg_notification()
