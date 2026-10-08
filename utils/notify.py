import sys
import os
import re
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Union

# 确保独立执行脚本时能正确导入项目根目录模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.regions import REGION_NAMES
from utils.logger import logger

def format_tg_summary(gen_stats: Dict[str, Any]) -> str:
    """根据统计字典格式化 Telegram 消息看板文案"""
    region_nodes = gen_stats.get('region_nodes', {})
    others = gen_stats.get('others', [])
    timestamp = gen_stats.get('timestamp', '')
    source_count = gen_stats.get('source_count', 0)
    raw_count = gen_stats.get('raw_count', 0)
    total_nodes = gen_stats.get('total_nodes', 0)
    elapsed_time = gen_stats.get('elapsed_time', 0.0)

    region_lines = []
    for key, nodes in region_nodes.items():
        name = REGION_NAMES.get(key, key)
        region_lines.append(f"{name} {len(nodes)}")
    if others:
        region_lines.append(f"🌍 其他 {len(others)}")

    region_str = " | ".join(region_lines)

    message = (
        f"🚀 <b>MetaFetch 节点自动抓取更新通知</b>\n\n"
        f"⏰ <b>更新时间：</b> <code>{timestamp}</code>\n"
        f"📡 <b>活跃源：</b> {source_count} 个\n"
        f"📦 <b>抓取节点：</b> {raw_count} 个\n"
        f"✅ <b>保留有效节点：</b> <b>{total_nodes}</b> 个 (耗时 {elapsed_time:.2f}s)\n\n"
        f"🌍 <b>节点地区分布：</b>\n"
        f"{region_str}\n\n"
        f"📥 <b>快捷订阅地址 (点击链接直连复制)：</b>\n"
        f"• <b>Clash / Mihomo:</b>\n<code>https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.meta.yml</code>\n"
        f"• <b>Shadowrocket / Base64:</b>\n<code>https://fastly.jsdelivr.net/gh/lanzm/MetaFetch@master/list.b64</code>\n\n"
        f"⭐ <b>GitHub 仓库：</b> <a href=\"https://github.com/lanzm/MetaFetch\">lanzm/MetaFetch</a>"
    )
    return message


def send_tg_notification(summary_or_text: Union[Dict[str, Any], str] = None) -> bool:
    raw_token = os.environ.get('TG_BOT_TOKEN', '')
    raw_chat_id = os.environ.get('TG_CHAT_ID', '')

    # 彻底过滤多余空格、换行符等控制字符
    token = re.sub(r'\s+', '', raw_token)
    chat_id = re.sub(r'\s+', '', raw_chat_id)

    # 自动切除可能误多复制的 'bot' 前缀
    if token.lower().startswith('bot'):
        token = token[3:]

    if not token or not chat_id:
        logger.info("TG_BOT_TOKEN or TG_CHAT_ID is missing in environment variables. Skipping Telegram notification.")
        return False

    text = ""
    if isinstance(summary_or_text, dict):
        text = format_tg_summary(summary_or_text)
    elif isinstance(summary_or_text, str):
        text = summary_or_text

    if not text:
        if os.path.exists("tg_summary.txt"):
            try:
                with open("tg_summary.txt", "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                text = ""
        if not text:
            logger.info("No notification text provided. Skipping Telegram notification.")
            return False

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
                return True
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
                    success = True
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8') if e.fp else str(e)
            logger.error(f"Telegram API HTTP Error {e.code}: {err_msg}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    return success

if __name__ == "__main__":
    send_tg_notification()
