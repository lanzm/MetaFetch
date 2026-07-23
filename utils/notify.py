import os
import urllib.request
import urllib.parse

def send_tg_notification():
    token = os.environ.get('TG_BOT_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    
    if not token or not chat_id:
        print("TG_BOT_TOKEN or TG_CHAT_ID is missing. Skipping Telegram notification.")
        return
        
    if not os.path.exists("tg_summary.txt"):
        print("tg_summary.txt not found. Skipping Telegram notification.")
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
    except Exception as e:
        print(f"[Error] Failed to send Telegram notification: {e}")

if __name__ == "__main__":
    send_tg_notification()
