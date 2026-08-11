"""
agent_bus.py — Agent 间通信朴素实现 (VAS harness 层)

参照 wanman Supervisor 的语义, 用纯文件系统实现:
  inbox/      消息队列 (JSON 文件, 支持 steer/followUp 优先级)
  artifacts/  结构化产物 (研究摘要/计划/交付物)
  context/    共享键值上下文 (agent 间状态)

设计目标:
  - 零依赖, 纯 stdlib
  - 任何 agent (Hermes / Claude Code / Codex / 脚本) 都能读写
  - 文件即消息: 一条消息 = 一个 JSON 文件, 原子写 (tmp + rename)

用法:
  from pulse.agent_bus import AgentBus
  bus = AgentBus("~/.hermes/bus")
  bus.send("dev", "CEO", "实现 RAG 模块", priority="steer")
  msgs = bus.recv("dev")
  bus.artifact_put("research-001", "rag-arch", {"engine": "chroma"})
  bus.context_set("last_build", "ok")
"""

from __future__ import annotations

import datetime
import json
import time
import uuid
from pathlib import Path
from typing import Any


class AgentBus:
    """基于文件系统的 agent 消息/产物/上下文总线"""

    def __init__(self, root: str | Path = "~/.hermes/bus"):
        self.root = Path(root).expanduser().resolve()
        self.inbox_dir = self.root / "inbox"
        self.artifact_dir = self.root / "artifacts"
        self.context_dir = self.root / "context"
        self.log_dir = self.root / "logs"
        for d in (self.inbox_dir, self.artifact_dir, self.context_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ── 审计日志 (oplog) — 借鉴 sandbank AgentOp 模式 ──────────────

    def oplog(self, action: str, agent: str = "unknown",
              path: str | None = None, payload: dict | None = None,
              metadata: dict | None = None) -> str:
        """记录一次 agent 操作到审计日志 (按日期轮转: logs/<date>.jsonl)。

        action: 操作名 (如 collect/compute/export/verify)
        agent:  操作主体 (如 boom-monitor/intel-pipeline)
        path:   涉及路径 (可选)
        payload: 操作负载摘要 (可选, 禁止记录密钥类内容)
        返回 op id。
        """
        op_id = uuid.uuid4().hex[:12]
        entry = {
            "id": op_id,
            "action": action,
            "agent": agent,
            "path": path,
            "payload": payload or {},
            "metadata": metadata or {},
            "timestamp": int(time.time() * 1000),
        }
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        log_file = self.log_dir / f"{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return op_id

    def export_oplog(self, agent: str | None = None,
                     since: str | None = None) -> list[dict]:
        """导出审计日志。agent 过滤操作主体; since: ISO 日期 (含)。"""
        entries = []
        for f in sorted(self.log_dir.glob("*.jsonl")):
            if since and f.stem < since:
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if agent and e.get("agent") != agent:
                    continue
                entries.append(e)
        return entries

    # ── 消息 (inbox) ──────────────────────────────────────────────

    def send(self, to: str, sender: str, content: str,
             priority: str = "followUp", metadata: dict | None = None) -> str:
        """发送消息。priority: steer(打断) | followUp(排队)"""
        msg_id = uuid.uuid4().hex[:12]
        msg = {
            "id": msg_id,
            "from": sender,
            "to": to,
            "priority": priority,
            "content": content,
            "timestamp": int(time.time() * 1000),
            "delivered": False,
            "metadata": metadata or {},
        }
        # 原子写: tmp + rename
        tmp = self.inbox_dir / f".{msg_id}.tmp"
        final = self.inbox_dir / f"{msg_id}.json"
        tmp.write_text(json.dumps(msg, ensure_ascii=False, indent=2))
        tmp.rename(final)
        return msg_id

    def recv(self, agent: str, mark_delivered: bool = True) -> list[dict]:
        """收取某 agent 的待处理消息。steer 优先, 按时间排序。"""
        messages = []
        for f in sorted(self.inbox_dir.glob("*.json")):
            try:
                msg = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if msg.get("to") != agent or msg.get("delivered"):
                continue
            messages.append(msg)
            if mark_delivered:
                msg["delivered"] = True
                f.write_text(json.dumps(msg, ensure_ascii=False, indent=2))
        # steer 优先, 然后时间序
        messages.sort(key=lambda m: (0 if m.get("priority") == "steer" else 1,
                                     m.get("timestamp", 0)))
        return messages

    def pending_count(self, agent: str) -> int:
        return sum(1 for f in self.inbox_dir.glob("*.json")
                   if not json.loads(f.read_text()).get("delivered"))

    # ── 产物 (artifacts) ─────────────────────────────────────────

    def artifact_put(self, kind: str, name: str, content: Any,
                     metadata: dict | None = None) -> Path:
        """存储结构化产物。artifacts/<kind>/<name>.json"""
        kind_dir = self.artifact_dir / kind
        kind_dir.mkdir(parents=True, exist_ok=True)
        path = kind_dir / f"{name}.json"
        payload = {
            "kind": kind,
            "name": name,
            "content": content,
            "created_at": int(time.time()),
            "metadata": metadata or {},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return path

    def artifact_get(self, kind: str, name: str) -> dict | None:
        path = self.artifact_dir / kind / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def artifact_list(self, kind: str | None = None) -> list[dict]:
        results = []
        search_dir = self.artifact_dir / kind if kind else self.artifact_dir
        if not search_dir.exists():
            return results
        for f in sorted(search_dir.rglob("*.json")):
            try:
                results.append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
        return results

    # ── 上下文 (context) ─────────────────────────────────────────

    def context_set(self, key: str, value: Any, updated_by: str = "system") -> None:
        """共享键值上下文 (upsert)"""
        path = self.context_dir / f"{key}.json"
        payload = {
            "key": key,
            "value": value,
            "updatedBy": updated_by,
            "updatedAt": int(time.time() * 1000),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def context_get(self, key: str) -> Any | None:
        path = self.context_dir / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text()).get("value")

    def context_list(self) -> dict:
        result = {}
        for f in self.context_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                result[data["key"]] = data["value"]
            except (json.JSONDecodeError, OSError):
                continue
        return result

    # ── 任务 (task pool, 轻量) ───────────────────────────────────

    def task_create(self, title: str, owner: str = "", depends_on: list[str] | None = None,
                    priority: str = "normal") -> str:
        """创建任务。depends_on: 前置任务 ID 列表"""
        task_id = uuid.uuid4().hex[:10]
        task = {
            "id": task_id,
            "title": title,
            "owner": owner,
            "status": "pending",      # pending | in_progress | done | blocked
            "priority": priority,      # normal | high | urgent
            "depends_on": depends_on or [],
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        (self.context_dir.parent / "tasks").mkdir(exist_ok=True)
        path = self.context_dir.parent / "tasks" / f"{task_id}.json"
        path.write_text(json.dumps(task, ensure_ascii=False, indent=2))
        return task_id

    def task_update(self, task_id: str, **fields) -> None:
        path = self.context_dir.parent / "tasks" / f"{task_id}.json"
        if not path.exists():
            return
        task = json.loads(path.read_text())
        task.update(fields)
        task["updated_at"] = int(time.time())
        path.write_text(json.dumps(task, ensure_ascii=False, indent=2))

    def task_list(self, status: str | None = None) -> list[dict]:
        tasks = []
        tasks_dir = self.context_dir.parent / "tasks"
        if not tasks_dir.exists():
            return tasks
        for f in sorted(tasks_dir.glob("*.json")):
            task = json.loads(f.read_text())
            if status and task.get("status") != status:
                continue
            tasks.append(task)
        return tasks


def demo():
    """演示: CEO → dev 消息流 + artifact + context"""
    bus = AgentBus("/tmp/vas-bus-demo")
    print("1. CEO 发消息给 dev (steer 优先)")
    bus.send("dev", "CEO", "实现 RAG 模块, 用 chroma 做向量库", priority="steer")
    bus.send("dev", "CEO", "顺便更新 README", priority="followUp")
    bus.send("dev", "CEO", "下午 5 点前完成", priority="followUp")

    print("2. dev 收取 (steer 在前)")
    msgs = bus.recv("dev")
    for m in msgs:
        print(f"   [{m['priority']}] {m['from']} → {m['to']}: {m['content'][:30]}")

    print("3. dev 存产物")
    bus.artifact_put("research", "rag-arch", {"engine": "chroma", "chunk": 512})
    print(f"   artifact: {bus.artifact_get('research', 'rag-arch')['content']}")

    print("4. 共享上下文")
    bus.context_set("last_build", "ok", updated_by="dev")
    print(f"   last_build = {bus.context_get('last_build')}")

    print("5. 任务依赖")
    t1 = bus.task_create("设计 schema", owner="dev")
    bus.task_create("实现 RAG", owner="dev", depends_on=[t1])
    bus.task_update(t1, status="done")
    tasks = bus.task_list()
    for t in tasks:
        print(f"   [{t['status']}] {t['title']} (deps: {t['depends_on']})")

    import shutil
    shutil.rmtree("/tmp/vas-bus-demo")
    print("\n✅ 演示完成")


if __name__ == "__main__":
    demo()
