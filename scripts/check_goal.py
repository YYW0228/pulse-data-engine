"""
scripts/check_goal.py — Goal Contract 校验器

检查 .hermes/goal.md 的状态, 输出进度报告。
支持跨 session 恢复: 新 session 运行时自动报告未完成任务。

用法:
  uv run python -m scripts.check_goal
  uv run python -m scripts.check_goal --json
"""

import json
import re
from pathlib import Path

GOAL_PATH = Path(".hermes/goal.md")
INBOX_PATH = Path("data/telegram_inbox.jsonl")


def parse_goal(path: Path) -> dict:
    """解析 goal.md 返回结构化状态"""
    text = path.read_text(encoding="utf-8")

    goal = re.search(r"^## Goal\s*\n(.+)", text, re.MULTILINE)
    title = goal.group(1).strip() if goal else "?"

    steps = []
    for line in text.splitlines():
        m = re.match(r"- \[([ x])\] Step (\d+): (.+) → type:(\w+) \| verify:(\w+)", line)
        if m:
            steps.append({
                "id": int(m.group(2)),
                "title": m.group(3).strip(),
                "done": m.group(1) == "x",
                "type": m.group(4),
                "verify": m.group(5),
                "state": "completed" if m.group(1) == "x" else "pending",
            })

    state_section = False
    states = {}
    for line in text.splitlines():
        if line.strip() == "## State":
            state_section = True
            continue
        if state_section and ":" in line and not line.startswith("#"):
            parts = line.split(":", 1)
            states[parts[0].strip()] = parts[1].strip()

    return {
        "title": title,
        "total": len(steps),
        "done": sum(1 for s in steps if s["done"]),
        "steps": steps,
        "states": states,
    }


def check_telegram_inbox() -> list:
    """检查 Telegram 是否有新消息"""
    if not INBOX_PATH.exists():
        return []
    # 只返回未读的 (上次检查后的新行)
    offset_path = INBOX_PATH.with_suffix(".read_offset")
    offset = int(offset_path.read_text().strip()) if offset_path.exists() else 0

    lines = INBOX_PATH.read_text(encoding="utf-8").splitlines()
    new_msgs = []
    for i, line in enumerate(lines):
        if i < offset:
            continue
        try:
            msg = json.loads(line)
            new_msgs.append(msg)
        except json.JSONDecodeError:
            continue

    # 更新 offset
    offset_path.write_text(str(len(lines)))
    return new_msgs


def main():
    if not GOAL_PATH.exists():
        print("📋 无活跃 Goal Contract")
        return

    goal = parse_goal(GOAL_PATH)
    progress = f"{goal['done']}/{goal['total']}"

    print(f"📋 Goal: {goal['title']}")
    print(f"   进度: {progress} 步骤完成\n")

    for s in goal["steps"]:
        icon = "✅" if s["done"] else "⬜"
        print(f"  {icon} Step {s['id']}: {s['title']}")
        print(f"       type={s['type']} verify={s['verify']}")

    if goal.get("states"):
        print(f"\n  状态: {json.dumps(goal['states'], ensure_ascii=False)}")

    # 检查 Telegram
    msgs = check_telegram_inbox()
    if msgs:
        print(f"\n📨 Telegram 新消息 ({len(msgs)} 条):")
        for m in msgs:
            print(f"  [{m.get('from','?')}] {m.get('text','')[:100]}")

    # 检查 Dashboard
    import httpx
    try:
        r = httpx.get("http://localhost:8501", timeout=3)
        dashboard = "✅ 在线" if r.status_code == 200 else "❌ 离线"
    except Exception:
        dashboard = "❌ 离线"
    try:
        r = httpx.get("http://localhost:9464/metrics", timeout=3)
        metrics = "✅ 在线" if r.status_code == 200 else "❌ 离线"
    except Exception:
        metrics = "❌ 离线"

    print(f"\n📊 Dashboard: {dashboard}")
    print(f"📈 Metrics:   {metrics}")


if __name__ == "__main__":
    main()
