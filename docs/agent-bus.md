# Agent Bus — Hermes Agent 间通信层 (VAS 落地)

> 参照 wanman Supervisor 语义的纯文件系统消息总线。
> 让 Hermes / Claude Code / Codex / 任意脚本可以互相发消息、共享产物和上下文。

## 位置

```
pulse/agent_bus.py   — AgentBus 实现 (纯 stdlib)
默认根目录: ~/.hermes/bus/
  ├── inbox/       消息队列 (JSON, steer/followUp 优先级)
  ├── artifacts/   结构化产物 (artifacts/<kind>/<name>.json)
  ├── context/     共享键值上下文 (context/<key>.json)
  └── tasks/       轻量任务池 (依赖感知)
```

## 与 wanman Supervisor 的映射

| wanman (TS) | AgentBus (Python) | 差异 |
|-------------|-------------------|------|
| MessageStore (SQLite) | `inbox/` JSON 文件 | 文件即消息, 任意 agent 可读写 |
| ContextStore | `context/` | 同语义 (upsert) |
| ArtifactStore | `artifacts/` | 同语义 |
| TaskPool | `tasks/` | 轻量版 (无 RPC, 无 UI) |
| Relay + steer | `send(priority="steer")` | 排序优先级相同 |
| JSON-RPC supervisor | 无 | 文件系统即接口 |

**设计哲学**: wanman 用 SQLite + RPC 是给"多进程常驻 agent 矩阵"用的；
我们的场景是"Hermes 会话 + 定时任务 + 一次性脚本"，文件系统足够且零运维。

## 使用场景

### 1. 跨会话消息 (Hermes CLI ↔ 定时任务)

```python
# cron 任务里: 向 Hermes 主会话投递消息
from pulse.agent_bus import AgentBus
bus = AgentBus()
bus.send("hermes-main", "intel-pipeline", "发现 3 条新法规, 需要深度分析", priority="steer")
```

### 2. 多 agent 协作 (CEO/规划 → 执行 → 质检)

```python
# 规划 agent
bus.send("builder", "CEO", "实现 RAG 模块, 参考 artifacts/research/rag-arch.json")

# 执行 agent (醒来时收消息)
msgs = bus.recv("builder")
# ... 工作完成后存产物 + 报告
bus.artifact_put("deliverable", "rag-module", {"files": [...], "tests": "14 passed"})
bus.send("CEO", "builder", "RAG 模块完成, 见 artifacts/deliverable/rag-module.json")
```

### 3. 共享状态 (构建结果/指标)

```python
bus.context_set("last_build", "ok", updated_by="ci")
bus.context_set("mrr", 12800, updated_by="finops")
```

### 4. 任务依赖编排

```python
t1 = bus.task_create("设计 schema", owner="dev")
t2 = bus.task_create("实现 RAG", owner="dev", depends_on=[t1])
# 检查: 只有 t1 done 才处理 t2
ready = [t for t in bus.task_list(status="pending")
         if all(dep_done(d) for d in t["depends_on"])]
```

## 集成约定 (Hermes 会话)

1. **任何 Hermes 会话启动时** (或需要时):
   ```python
   from pulse.agent_bus import AgentBus
   bus = AgentBus()          # ~/.hermes/bus/
   pending = bus.pending_count("hermes-main")
   if pending: msgs = bus.recv("hermes-main")
   ```
2. **agent 名字约定**: `hermes-main` (主会话), `l2-worker` (Mac Mini 深度分析),
   `intel-pipeline` (情报管道), `boom-monitor` (爆款监控), `finops` (成本核算)
3. **优先级语义**: `steer` = 打断当前工作优先处理; `followUp` = 排队

## 测试

```bash
.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('agent_bus', 'pulse/agent_bus.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.demo()
"
```

## 注意

- 文件即消息 → 消息不丢 (除非磁盘故障), 重启后仍可 recv
- 原子写 (tmp + rename) → 并发写安全
- 目录结构简单 → 任何语言/工具都能对接 (读 JSON 即可)
- 不要用于高频消息 (性能场景用 SQLite/Redis)
