"""
scripts/customer_accept.py — 客户库一键验收 (onboarding 闭环最后一环)

从客户文档自动生成验收题 → 真实链路问答 → 命中率报告 (≥80% 门禁)。

闭环 (2026-09-02 补齐):
  onboard --name X (建库) → accept --name X (自动出题+验收) = 换文档即可复用

用法:
  uv run python -m scripts.customer_accept --name acme              # 全流程
  uv run python -m scripts.customer_accept --name acme --questions 6
  uv run python -m scripts.customer_accept --name acme --regen      # 强制重新出题

输出:
  data/customers/<name>/golden_set.json    # 自动生成的验收题 (LLM 提取文档要点)
  data/customers/<name>/ACCEPTANCE.md      # 验收报告 (命中率/失败明细)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# eval 模式环境 (与 golden_eval 一致: 熔断关闭 + eval 标记)
os.environ["LLM_AUDIT_FUSE"] = "off"
os.environ["LLM_AUDIT_EVAL"] = "1"
os.environ.setdefault("HF_HUB_OFFLINE", "1")

PASS_THRESHOLD = 0.80
GEN_MODEL = "deepseek-chat"  # 出题用便宜模型 (要点提取任务)
MAX_DOC_CHARS = 2500  # 每文档截取长度 (控制出题调用 token)


def _load_docs(name: str) -> list[dict]:
    """读客户 raw/ 文档 + parsed/ jsonl, 返回 [{doc, content}] (截断)"""
    cust = ROOT / "data" / "customers" / name
    raw = cust / "raw"
    docs: list[dict] = []
    if raw.exists():
        for f in sorted(raw.iterdir()):
            if f.suffix.lower() in (".md", ".txt"):
                try:
                    content = f.read_text(encoding="utf-8")
                except Exception:  # noqa: S112 — 坏文件跳过, 不阻断批量读取
                    continue
                docs.append({"doc": f.name, "content": content[:MAX_DOC_CHARS]})
    parsed = cust / "parsed"
    if parsed.exists():
        for f in sorted(parsed.glob("*.jsonl")):
            try:
                lines = f.read_text(encoding="utf-8").splitlines()[:80]
                content = "\n".join(
                    json.loads(ln).get("text", "")[:2000] for ln in lines if ln.strip()
                )
            except Exception:  # noqa: S112 — 坏 jsonl 跳过, 不阻断批量读取
                continue
            if content:
                docs.append({"doc": f.name.replace(".jsonl", ".pdf"), "content": content[:MAX_DOC_CHARS]})
    return docs


def _generate_questions(name: str, docs: list[dict], n: int) -> list[dict]:
    """LLM 从文档提取要点生成验收题 (JSON 数组)"""
    from pulse.llm_audit import audited_post

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        for env_path in (Path.home() / ".hermes" / ".env", ROOT / ".env"):
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("DEEPSEEK_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
            if key:
                break
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置")

    doc_block = "\n\n---\n\n".join(
        f"[文档: {d['doc']}]\n{d['content']}" for d in docs[:20]
    )
    prompt = f"""你是企业合规顾问。基于以下客户制度文档, 生成 {n} 道验收问题。
要求:
1. 覆盖客户文档里的: 制度触发条件/时限/责任主体/流程步骤/红线禁止
2. 问题要用客户视角提问 (如 "我们公司..."), 像真实业务人员会问的
3. expect 是 3-5 个短关键词 (每个 2-8 字, 如 "30日内" "出海合规评估" "双重标识"),
   从文档原文提取, 回答中出现即算命中; 严禁整句或长短语 (≤8字)
4. 只输出 JSON 数组, 不要多余文字

文档:
{doc_block[:60000]}

输出格式:
[{{"question": "...", "expect": ["关键词1", "关键词2", "关键词3"], "domain": "制度"}}]"""

    resp = audited_post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": GEN_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.4, "max_tokens": 2000},
        timeout=120,
        source="customer_accept.generate",
    )
    text = resp.json()["choices"][0]["message"]["content"]
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        raise RuntimeError(f"出题 LLM 输出无法解析: {text[:200]}")
    qs = json.loads(m.group(0))
    return [q for q in qs if q.get("question") and q.get("expect")][:n]


def _normalize(s: str) -> str:
    """去空白 (期望词匹配归一化: '72小时' ↔ '72 小时内')"""
    return re.sub(r"\s+", "", s)


def _run_acceptance(name: str, questions: list[dict]) -> list[dict]:
    """真实链路逐题问答 (use_cache=False), 返回带命中结果"""
    from compliance_qa import answer, set_customer_db

    set_customer_db(name)
    results = []
    for q in questions:
        t0 = time.time()
        try:
            resp = answer(q["question"], top_k=8, use_cache=False)
            ms = int((time.time() - t0) * 1000)
            norm = _normalize(resp)
            covered = [e for e in q["expect"] if _normalize(e) in norm]
            hit = len(covered) / max(len(q["expect"]), 1)
            success = bool(resp.strip())
            results.append({**q, "covered": covered, "hit_rate": hit,
                            "ms": ms, "success": success, "answer_head": resp[:120]})
        except Exception as e:
            results.append({**q, "covered": [], "hit_rate": 0.0, "ms": 0,
                            "success": False, "error": str(e), "answer_head": ""})
    return results


def accept(name: str, n: int = 8, regen: bool = False) -> dict:
    cust = ROOT / "data" / "customers" / name
    if not cust.exists():
        raise FileNotFoundError(f"客户库不存在: {name} (先跑 customer_onboard --name {name})")

    docs = _load_docs(name)
    if not docs:
        raise RuntimeError(f"{name} raw/ 无文档")

    # 1. 出题 (缓存 golden_set.json; --regen 强制重生成)
    gs_path = cust / "golden_set.json"
    questions = None
    if gs_path.exists() and not regen:
        try:
            questions = json.loads(gs_path.read_text(encoding="utf-8"))
        except Exception:
            questions = None
    if questions is None:
        questions = _generate_questions(name, docs, n)
        gs_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. 真实链路验收
    results = _run_acceptance(name, questions)
    hits = [r["hit_rate"] for r in results]
    avg = sum(hits) / len(hits) if hits else 0
    passed = avg >= PASS_THRESHOLD

    # 3. 报告
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"# 客户验收报告: {name}", "", f"> 生成时间: {ts} | 文档 {len(docs)} 份 | 题数 {len(results)}",
             "", f"## 结果: {'✅ 通过' if passed else '❌ 未通过'} (命中率 {avg:.0%} ≥ {PASS_THRESHOLD:.0%})", ""]
    for i, r in enumerate(results, 1):
        mark = "✅" if r["hit_rate"] >= 1.0 else ("⚠️" if r["hit_rate"] >= 0.5 else "❌")
        lines.append(f"{mark} [{i}/{len(results)}] {r['question']}")
        lines.append(f"   期望: {' / '.join(r['expect'])} | 覆盖: {r.get('covered', [])} | {r['ms']}ms")
        if not r["success"]:
            lines.append(f"   错误: {r.get('error', '空回答')}")
    lines.append("")
    (cust / "ACCEPTANCE.md").write_text("\n".join(lines), encoding="utf-8")

    return {"name": name, "docs": len(docs), "questions": len(results),
            "avg_hit_rate": round(avg, 3), "passed": passed,
            "golden_set": str(gs_path), "report": str(cust / "ACCEPTANCE.md")}


def main():
    parser = argparse.ArgumentParser(description="客户库一键验收 (自动出题+问答+报告)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--questions", type=int, default=8)
    parser.add_argument("--regen", action="store_true", help="强制重新生成验收题")
    args = parser.parse_args()
    r = accept(args.name, args.questions, args.regen)
    print(f"=== 客户验收: {r['name']} ===")
    print(f"文档 {r['docs']} | 题数 {r['questions']} | 命中率 {r['avg_hit_rate']:.0%}")
    print(f"结果: {'✅ 通过' if r['passed'] else '❌ 未通过'} (门禁 {PASS_THRESHOLD:.0%})")
    print(f"金标集: {r['golden_set']}")
    print(f"报告: {r['report']}")
    sys.exit(0 if r["passed"] else 1)


if __name__ == "__main__":
    main()
