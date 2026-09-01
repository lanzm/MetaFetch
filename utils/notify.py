import os
import re
import json
import urllib.request
import urllib.error
from utils.logger import logger

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
        logger.warning("TG_BOT_TOKEN or TG_CHAT_ID is missing in environment variables. Skipping Telegram notification.")
        return
        
    if not os.path.exists("tg_summary.txt"):
        logger.warning("tg_summary.txt not found. Skipping Telegram notification.")
        return

    with open("tg_summary.txt", "r", encoding="utf-8") as f:
        text = f.read()

    msg_id_file = "tg_msg_id.txt"
    msg_id = None
    if os.path.exists(msg_id_file):
        try:
            with open(msg_id_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.isdigit():
                    msg_id = int(content)
        except Exception:
            pass

    success = False

    # 1. 优先尝试原地编辑已有看板消息
    if msg_id:
        edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
        data = json.dumps({
            'chat_id': chat_id,
            'message_id': msg_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }).encode('utf-8')
        req = urllib.request.Request(edit_url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if result.get('ok'):
                    logger.info(f"Telegram dashboard message (ID: {msg_id}) updated successfully via editMessageText!")
                    success = True
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8') if e.fp else str(e)
            # 内容无变化时 Telegram 会报 "message is not modified"，视为成功无需重发
            if "message is not modified" in err_msg.lower():
                logger.info(f"Telegram dashboard message (ID: {msg_id}) content is unchanged.")
                return
            logger.info(f"editMessageText failed ({e.code}: {err_msg}), will create a new message.")
        except Exception as e:
            logger.warning(f"Failed to edit message: {e}, will fallback to sending a new message.")

    # 2. 若无历史 message_id 或编辑失败（如原消息被删），则发送新消息并记录 ID
    if not success:
        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }).encode('utf-8')
        req = urllib.request.Request(send_url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if result.get('ok'):
                    new_msg_id = result.get('result', {}).get('message_id')
                    logger.info(f"New Telegram dashboard message created! Message ID: {new_msg_id}")
                    if new_msg_id:
                        with open(msg_id_file, "w", encoding="utf-8") as f:
                            f.write(str(new_msg_id))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8') if e.fp else str(e)
            logger.error(f"Telegram API HTTP Error {e.code}: {err_msg}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

if __name__ == "__main__":
    send_tg_notification()
