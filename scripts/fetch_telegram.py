"""
scripts/fetch_telegram.py — 读取 Telegram bot 最新消息

让 Hermes CLI 会话能主动读取 Telegram 消息,
而不是依赖 Gateway 异步转发。

用法:
  uv run python -m scripts.fetch_telegram          # 最近5条
  uv run python -m scripts.fetch_telegram --limit 10  # 最近10条
  
依赖:
  pip install python-telegram-bot
"""

import argparse
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("fetch_telegram")

def fetch_messages(limit: int = 5) -> list[dict]:
    """通过 Telegram Bot API 获取最近消息"""
    import httpx

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        # 从 .env 读取
        env_path = Path.home() / ".hermes" / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip("'\"")
                    break

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN 未设置")
        return []

    resp = httpx.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"timeout": 10, "limit": limit},
        timeout=15,
    )
    data = resp.json()

    if not data.get("ok"):
        logger.error(f"Telegram API 错误: {data.get('description', 'unknown')}")
        return []

    messages = []
    for update in data.get("result", []):
        msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
        if msg:
            messages.append({
                "update_id": update["update_id"],
                "chat_id": msg["chat"]["id"],
                "from": msg["from"].get("first_name", "?"),
                "text": msg.get("text", ""),
                "date": msg["date"],
            })

    return messages


def main():
    parser = argparse.ArgumentParser(description="读取 Telegram bot 最新消息")
    parser.add_argument("--limit", type=int, default=5, help="消息数")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    msgs = fetch_messages(limit=args.limit)

    if not msgs:
        print("📭 暂无未读消息")
        return

    if args.format == "json":
        print(json.dumps(msgs, ensure_ascii=False, indent=2))
    else:
        print(f"📨 Telegram 最近 {len(msgs)} 条消息:\n")
        for m in reversed(msgs):
            print(f"  [{m['from']}] {m['text'][:200]}")
            print()


if __name__ == "__main__":
    main()
