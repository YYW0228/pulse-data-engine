"""
scripts/telegram_poller.py — Telegram 消息轮询器 (后台用)

每60秒检查 Telegram bot 新消息, 写入 data/telegram_inbox.jsonl
供 CLI 会话自动读取。

用法:
  nohup uv run python -m scripts.telegram_poller &
"""
import json
import logging
import os
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_poller")

INBOX_PATH = Path("data/telegram_inbox.jsonl")
POLL_INTERVAL = 60  # 秒


def get_token() -> str | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


def poll() -> None:
    import httpx

    token = get_token()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN 未设置")
        return

    # 记录已处理的 update_id
    offset_path = INBOX_PATH.with_suffix(".offset")
    offset = 0
    if offset_path.exists():
        try:
            offset = int(offset_path.read_text().strip())
        except ValueError:
            offset = 0

    try:
        resp = httpx.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset + 1, "timeout": 30, "limit": 10},
            timeout=35,
        )
        data = resp.json()
        if not data.get("ok"):
            return

        for update in data.get("result", []):
            msg = update.get("message") or update.get("channel_post")
            if msg and msg.get("text"):
                entry = {
                    "source": "telegram",
                    "timestamp": time.time(),
                    "from": msg["from"].get("first_name", "?"),
                    "text": msg["text"],
                    "chat_id": msg["chat"]["id"],
                }
                INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
                with INBOX_PATH.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                logger.info(f"新消息: [{entry['from']}] {entry['text'][:60]}")

            offset = max(offset, update["update_id"])

        offset_path.write_text(str(offset))
    except Exception as e:
        logger.debug(f"轮询失败: {e}")


def main():
    logger.info(f"Telegram 轮询启动 (每{POLL_INTERVAL}s), 收件箱: {INBOX_PATH}")
    while True:
        poll()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
