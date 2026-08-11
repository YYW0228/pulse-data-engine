#!/usr/bin/env python3
"""
vas_goal.py — VAS 目标驱动开发 CLI (wanman takeover 模式)

给一个 repo + 一个 goal, harness 自动:
  analyze → plan → execute(verify loop) → commit → report

用法:
  python scripts/vas_goal.py --repo <path> --goal "<描述>" [--engine hermes|claude]
  python scripts/vas_goal.py --repo <path> --goal "..." --dry-run   # 只分析+规划

执行引擎:
  --engine hermes  → 用 hermes CLI (Hermes 自己作为 agent)
  --engine claude  → 用 Claude Code CLI

依赖: 纯 stdlib + 已安装的 agent CLI。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════


@dataclass
class GoalStep:
    """计划中的一步 (对应 Pattern 13 plan.md 状态机)"""
    id: str
    title: str
    description: str
    step_type: str = "code"       # code | test | config | document | generic
    status: str = "pending"       # pending | in_progress | verifying | completed | blocked
    retries: int = 0
    verify_gate: str = ""         # 验证命令 (可空)


@dataclass
class GoalResult:
    goal: str
    repo: Path
    steps: list[GoalStep]
    started_at: float
    finished_at: Optional[float] = None
    engine: str = "hermes"
    commits: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    cost_estimate: float = 0.0

    @property
    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    @property
    def blocked_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "blocked")


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120,
            capture: bool = True) -> tuple[int, str]:
    """运行命令, 返回 (exit_code, output)"""
    try:
        r = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                           capture_output=capture, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT after {timeout}s"
    except FileNotFoundError as e:
        return -2, f"command not found: {e}"


def repo_snapshot(repo: Path) -> str:
    """生成 repo 结构快照 (给 agent 看)"""
    lines = []
    for root, dirs, files in os.walk(repo):
        # 跳过 .git / node_modules / venv / __pycache__ / .venv
        dirs[:] = [d for d in dirs if d not in
                   (".git", "node_modules", "venv", ".venv", "__pycache__",
                    ".mypy_cache", ".ruff_cache", "dist", "build")]
        depth = root[len(str(repo)):].count(os.sep)
        if depth > 3:
            continue
        rel = os.path.relpath(root, repo)
        indent = "  " * depth
        name = os.path.basename(root) if depth > 0 else "."
        lines.append(f"{indent}{name}/")
        for f in sorted(files):
            if f.startswith("."):
                continue
            fp = Path(root) / f
            try:
                size = fp.stat().st_size
            except OSError:
                size = 0
            lines.append(f"{indent}  {f} ({size}B)")
    return "\n".join(lines[:120])  # 限制长度


def read_file_head(path: Path, max_lines: int = 60) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
        return "\n".join(lines[:max_lines])
    except OSError:
        return "(unreadable)"


def build_repo_context(repo: Path, goal: str) -> str:
    """构建 repo + goal 上下文 (给执行 agent 的自包含 prompt 素材)"""
    parts = [f"# Repository: {repo.name}", "", "## Structure", "```",
             repo_snapshot(repo), "```"]
    # README
    for name in ("README.md", "README", "AGENTS.md", "CLAUDE.md"):
        p = repo / name
        if p.exists():
            parts.append(f"\n## {name}\n```\n{read_file_head(p, 40)}\n```")
            break
    # 主要源码文件 (前 5 个)
    src_files = []
    for pattern in ("*.py", "*.ts", "*.js", "*.go", "*.rs", "*.sh"):
        src_files.extend(repo.glob(pattern))
    src_files = [f for f in src_files if "node_modules" not in str(f)][:5]
    if src_files:
        parts.append("\n## Key source files")
        for f in src_files:
            parts.append(f"\n### {f.name}\n```\n{read_file_head(f, 50)}\n```")
    parts.append(f"\n# Goal\n{goal}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# Phase 1: 分析 + 规划 (调 agent 生成 plan)
# ═══════════════════════════════════════════════════════════════════

PLAN_PROMPT = """你是 VAS 目标驱动开发的规划器。分析下面的仓库和 goal，产出一个可执行的分步计划。

要求:
1. 输出纯 JSON (不要 markdown 代码块)
2. JSON 结构: {{"steps": [{{"id": "s1", "title": "...", "description": "具体做什么(含文件路径)", "step_type": "code|test|config|document|generic", "verify_gate": "验证命令或留空"}}]}}
3. 每步描述必须自包含 (执行 agent 无记忆, 只看到这一步)
4. 3-6 步, 每步聚焦一个可验证的改动
5. step_type: code=写代码, test=写测试, config=改配置, document=改文档, generic=其他
6. ⚠ verify_gate 必须是**可直接在 bash 执行的单条命令** (如 \"python3 -m pytest tests/\"), 禁止自然语言描述 (如 \"确认注释已移除\"), 禁止含中文, 没有合适命令就留空字符串

{context}
"""


def _strip_ansi(text: str) -> str:
    """剥离 ANSI 转义码 (框线/颜色)"""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _extract_json_blocks(text: str) -> list[str]:
    """用括号配平提取所有候选 JSON 对象, 容忍 AN SI 框线/前缀噪音"""
    text = _strip_ansi(text)
    blocks: list[str] = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        # 从 { 开始括号配平
        depth = 0
        j = i
        in_str = False
        esc = False
        while j < len(text):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        blocks.append(text[i:j + 1])
                        break
            j += 1
        i = max(i + 1, j + 1)
    return blocks


def _strip_box_chars(text: str) -> str:
    """删除框线字符 (JSON 中不可能合法出现的装饰字符)"""
    return re.sub(r"[│┌┐└┘─╭╮╰╯╱╲]", "", text)


def _parse_steps_regex(cleaned: str) -> list[GoalStep]:
    """正则容错解析: 容忍 verify_gate/description 内嵌未转义引号"""
    # 逐 step 提取: description 以 '", "step_type"' 为终止标记 (容忍内部引号)
    step_re = re.compile(
        r'\{\s*"id":\s*"([^"]+)"\s*,\s*"title":\s*"([^"]+)"\s*,\s*'
        r'"description":\s*"(.*?)"\s*,\s*"step_type":\s*"([^"]+)"'
        r'(?:\s*,\s*"verify_gate":\s*"(.*?)"\s*\})?\s*\}',
        re.DOTALL,
    )
    steps: list[GoalStep] = []
    for m in step_re.finditer(cleaned):
        steps.append(GoalStep(
            id=m.group(1),
            title=m.group(2),
            description=m.group(3),
            step_type=m.group(4),
            verify_gate=m.group(5) or "",
        ))
    return steps


def parse_plan(raw: str) -> list[GoalStep]:
    """解析 agent 返回的 plan JSON (容忍 CLI 输出噪音/ANSI 框线/未转义引号)"""
    cleaned = raw.strip()
    # 去除可能的 markdown 代码块
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    # 1. 先试标准 JSON 解析 (括号配平提取候选块)
    candidates = _extract_json_blocks(cleaned)
    if not candidates:
        candidates = [cleaned]

    for cand in candidates:
        cand = _strip_box_chars(cand).strip()
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            continue
        steps_raw = data.get("steps") if isinstance(data, dict) else None
        if not isinstance(steps_raw, list) or not steps_raw:
            continue
        steps = []
        for i, s in enumerate(steps_raw):
            steps.append(GoalStep(
                id=s.get("id", f"s{i+1}") if isinstance(s, dict) else f"s{i+1}",
                title=s.get("title", f"Step {i+1}") if isinstance(s, dict) else f"Step {i+1}",
                description=s.get("description", "") if isinstance(s, dict) else str(s),
                step_type=s.get("step_type", "code") if isinstance(s, dict) else "code",
                verify_gate=s.get("verify_gate", "") if isinstance(s, dict) else "",
            ))
        if steps:
            return steps

    # 2. 标准解析失败 → 正则容错 (处理未转义引号)
    regex_steps = _parse_steps_regex(_strip_box_chars(cleaned))
    if regex_steps:
        return regex_steps

    raise ValueError(f"plan JSON 解析失败 (找不到有效 steps)\n原始: {raw[:500]}")


# ═══════════════════════════════════════════════════════════════════
# Phase 2: 执行 (调 agent 完成单步 + 验证)
# ═══════════════════════════════════════════════════════════════════

EXEC_PROMPT = """你是 VAS 的执行 agent。仓库在: {repo}

你的任务 (只做这一件事):
{step_description}

要求:
1. 只修改完成任务必需的文件
2. 完成后运行验证命令: {verify_gate}
3. 最后输出一行: DONE:{{简短的完成说明}} 或 FAIL:{{原因}}
4. 不要提交 git, 不要碰其他文件

仓库关键上下文:
{context}
"""


def run_agent(engine: str, prompt: str, repo: Path, timeout: int = 300) -> tuple[int, str]:
    """调用执行引擎 (hermes / claude)"""
    if engine == "hermes":
        # -Q: 禁用渲染框 (框线+折行会破坏 JSON 字符串 → Invalid control character)
        return run_cmd(["hermes", "chat", "-q", prompt, "--yolo", "-Q"], cwd=repo, timeout=timeout)
    elif engine == "claude":
        return run_cmd(["claude", "-p", prompt, "--dangerously-skip-permissions"], cwd=repo, timeout=timeout)
    else:
        return -3, f"unknown engine: {engine}"


def _is_valid_shell_gate(gate: str) -> bool:
    """校验 verify_gate 是否是可执行的真实命令 (2026-08-11 修复: 自然语言 gate 导致 git 误报)"""
    if not gate:
        return False
    # 含 CJK 或明显自然语言特征 → 无效
    if re.search(r"[\u4e00-\u9fff]", gate):
        return False
    first = gate.split()[0].lstrip("$")
    # 首词必须是已知可执行命令
    known = {"git", "python", "python3", "pytest", "uv", "npm", "npx", "bun", "node",
             "echo", "ls", "cat", "head", "tail", "grep", "cd", "make", "mkdir", "rm",
             "cp", "mv", "test", "true", "false", "pwd", "sed", "awk", "curl", "wget",
             "find", "diff", "bash", "sh", "cargo", "go", "rustc", "tsc", "eslint",
             "python3.11", "python3.12", "python3.13", "python3.14"}
    return first in known


def _normalize_gate_for_uv(gate: str, repo: Path) -> str:
    """uv 项目 (pyproject.toml 存在): python/pytest 前缀命令自动加 uv run (2026-08-12 VAS 实战教训:
    agent 生成 verify_gate 用裸 python3.14 无 pytest → 验证假失败)"""
    if not (repo / "pyproject.toml").exists():
        return gate
    first = gate.split()[0]
    if first in ("python", "python3", "pytest") or first.startswith("python3."):
        return "uv run " + gate
    return gate


def verify_step(step: GoalStep, repo: Path) -> tuple[bool, str]:
    """验证单步完成质量 (Pattern 12 verification gate)"""
    gate = step.verify_gate.strip()
    if not gate or not _is_valid_shell_gate(gate):
        # 无有效 gate: 检查 repo 是否有未提交改动 (说明 agent 动了文件)
        if gate:
            print(f"  ⚠ verify_gate 非有效命令, 降级为文件改动检查: {gate[:60]}")
        rc, out = run_cmd(["git", "status", "--porcelain"], cwd=repo, timeout=30)
        if rc == 0 and out.strip():
            return True, "文件有改动 (无有效 gate)"
        return False, "无有效 gate 且无文件改动"
    # 有有效 gate: 运行验证命令 (uv 项目自动加 uv run 前缀)
    gate = _normalize_gate_for_uv(gate, repo)
    rc, out = run_cmd(["bash", "-c", gate], cwd=repo, timeout=120)
    if rc == 0:
        return True, out.strip()[-300:]
    return False, out.strip()[-300:]


def render_plan_md(result: GoalResult, workdir: Path) -> Path:
    """渲染 plan.md (Pattern 13 状态机格式)"""
    lines = [f"# Goal: {result.goal}", ""]
    for s in result.steps:
        mark = {"completed": "x", "blocked": "!", "pending": " ",
                "in_progress": ">", "verifying": "?"}[s.status]
        lines.append(f"- [{mark}] {s.id}: {s.title}  → type:{s.step_type}")
        if s.status == "blocked":
            lines.append(f"    ⚠ blocked after {s.retries} retries")
    path = workdir / "plan.md"
    path.write_text("\n".join(lines))
    return path


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="VAS 目标驱动开发")
    parser.add_argument("--repo", required=True, help="目标 repo 路径")
    parser.add_argument("--goal", required=True, help="目标描述")
    parser.add_argument("--engine", choices=["hermes", "claude"], default="hermes")
    parser.add_argument("--dry-run", action="store_true", help="只分析+规划, 不执行")
    parser.add_argument("--max-retries", type=int, default=2, help="单步最大重试次数")
    parser.add_argument("--workdir", default=None, help="工作目录 (默认 /tmp/vas-<repo>-<ts>)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"❌ repo 不存在: {repo}")
        sys.exit(1)

    # 检查 git
    rc, out = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo, timeout=15)
    if rc != 0:
        print(f"❌ 不是 git repo: {repo}")
        sys.exit(1)

    # 工作目录
    workdir = Path(args.workdir) if args.workdir else Path(
        f"/tmp/vas-{repo.name}-{int(time.time())}")
    workdir.mkdir(parents=True, exist_ok=True)

    result = GoalResult(goal=args.goal, repo=repo, started_at=time.time(),
                        engine=args.engine, steps=[])

    print(f"🎯 Goal: {args.goal}")
    print(f"📂 Repo: {repo} (engine: {args.engine})")
    print(f"📁 Workdir: {workdir}")
    print()

    # ── Phase 1: 分析 + 规划 ──
    print("── Phase 1: 分析 + 规划 ──")
    context = build_repo_context(repo, args.goal)
    plan_prompt = PLAN_PROMPT.format(context=context)
    rc, out = run_agent(args.engine, plan_prompt, repo, timeout=args.max_retries and 300)
    if rc != 0:
        print(f"❌ 规划 agent 失败: {out[:500]}")
        sys.exit(1)
    try:
        result.steps = parse_plan(out)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    print(f"✅ 计划生成: {len(result.steps)} 步")
    for s in result.steps:
        print(f"   {s.id}: {s.title} [{s.step_type}]")
    plan_path = render_plan_md(result, workdir)
    print(f"📄 plan.md: {plan_path}")

    if args.dry_run:
        print("\n🔍 dry-run 模式: 不执行")
        sys.exit(0)

    # ── Phase 2: 循环执行 ──
    print("\n── Phase 2: 执行 (verify loop) ──")
    for step in result.steps:
        while step.status != "completed" and step.retries <= args.max_retries:
            step.status = "in_progress"
            render_plan_md(result, workdir)
            print(f"\n▶ {step.id}: {step.title} (retry {step.retries}/{args.max_retries})")

            # 执行
            exec_prompt = EXEC_PROMPT.format(
                repo=repo, step_description=step.description,
                verify_gate=step.verify_gate or "(无)", context=repo_snapshot(repo)[:2000])
            rc, out = run_agent(args.engine, exec_prompt, repo)
            if rc != 0:
                print(f"  ⚠ agent 执行异常 (rc={rc}): {out[-300:]}")
                step.retries += 1
                continue

            # 验证
            step.status = "verifying"
            ok, vout = verify_step(step, repo)
            if ok:
                step.status = "completed"
                render_plan_md(result, workdir)
                print(f"  ✅ 验证通过: {vout[:120]}")
                break
            else:
                print(f"  ❌ 验证失败: {vout[:200]}")
                step.retries += 1
                step.status = "pending"

        if step.status != "completed":
            step.status = "blocked"
            print(f"  ⛔ {step.id} blocked (retries exhausted)")

        # 每步后提交 (只提交本次改动; blocked 步骤不 commit, 保留工作区供人工检查)
        if step.status != "completed":
            print(f"  ⏭ {step.id} 未完成, 跳过 commit")
            continue
        rc, out = run_cmd(["git", "add", "-A"], cwd=repo, timeout=30)
        rc2, out2 = run_cmd(
            ["git", "-c", "user.email=vas@local", "-c", "user.name=VAS",
             "commit", "-m", f"vas: {step.id} — {step.title[:50]}"],
            cwd=repo, timeout=30)
        if rc2 == 0:
            result.commits.append(f"{step.id}: {step.title[:50]}")
            rc3, out3 = run_cmd(["git", "log", "--oneline", "-1"], cwd=repo, timeout=15)
            print(f"  📦 committed: {out3.strip()}")
        # 记录文件变更
        rc4, out4 = run_cmd(["git", "show", "--stat", "--oneline", "HEAD"], cwd=repo, timeout=15)
        if rc4 == 0:
            for line in out4.splitlines():
                m = re.match(r"\s+(\S+)\s+\|", line)
                if m and m.group(1) not in result.files_changed \
                        and "__pycache__" not in m.group(1):
                    result.files_changed.append(m.group(1))

    result.finished_at = time.time()

    # ── Phase 3: 报告 ──
    print("\n── 结果报告 ──")
    print(f"Goal: {result.goal}")
    print(f"步骤: {result.completed_count}/{len(result.steps)} 完成, "
          f"{result.blocked_count} blocked")
    if result.files_changed:
        print(f"文件变更: {', '.join(result.files_changed[:10])}")
    if result.commits:
        print(f"提交: {len(result.commits)} 个")
    elapsed = result.finished_at - result.started_at
    print(f"耗时: {elapsed:.0f}s")
    # 成本估算 (粗略: 每 agent 调用 ~2000 tokens)
    calls = len(result.steps) * (1 + sum(s.retries for s in result.steps))
    print(f"agent 调用: {calls} 次 (~{calls * 2000 / 1e6:.2f}M tokens)")
    plan_path = render_plan_md(result, workdir)
    print(f"\n📄 plan.md 最终状态: {plan_path}")
    print(f"   {plan_path.read_text()}")


if __name__ == "__main__":
    main()
