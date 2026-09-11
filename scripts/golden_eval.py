"""
scripts/golden_eval.py — 金标评测 (P3-9)

用人工标注的"金标问题集"持续评测问答质量:
  - 每个问题有: 问题 / 期望要点 (人工写的正确答案要点)
  - 评测: 跑问答 → 检查回答是否覆盖期望要点 → 计算命中率
  - 质量门禁: 命中率 ≥80% 才算通过 (模型升级/提示词改动后跑)

金标集文件: data/golden_set.json (30-50 题, 人工标注)
格式:
[
  {
    "question": "算法备案的要求是什么?",
    "expect": ["算法备案", "大模型专项备案", "未备案即违规"],
    "domain": "合规法规",
    "source": "人工标注 2026-08-04"
  }
]

用法:
  uv run python -m scripts.golden_eval                # 全量评测
  uv run python -m scripts.golden_eval --quick        # 前 10 题
  uv run python -m scripts.golden_eval --json         # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 模块级预加载 compliance_qa (2026-08-14) ──────────────────────────
# 修复 torch dlopen 偶发崩: torch 2.6.0 cp310 wheel 链接 3.11+ 符号,
# flat namespace 下能否解析取决于进程先加载的库。函数内才 import 时
# 加载顺序不同 → symbol not found。模块级提前 import 稳定了顺序。
from scripts import compliance_qa  # noqa: F401

# ── Eval 模式环境 (2026-08-14 AR 试点) ───────────────────────────────
# 1. 熔断关闭: 循环熔断是防死循环设计, eval 是有界批量调用 (samples=2 同 query
#    重复 + 多轮运行累计 ≥5 次/10min 会被误伤)。审计仍完整记录, 不变量不受影响。
# 2. 注意: 本脚本必须用 `python scripts/golden_eval.py` (脚本模式) 运行 —
#    `python -m scripts.golden_eval` 包模式会触发 torch dlopen ABI 崩
#    (py3.10 venv + torch 2.6, _PyCode_GetVarnames 符号缺失)。
os.environ["LLM_AUDIT_FUSE"] = "off"
os.environ["LLM_AUDIT_EVAL"] = "1"   # 审计打 eval 标记: 循环检测/告警排除批量评测

GOLDEN_SET = Path(__file__).resolve().parent.parent / "data" / "golden_set.json"
PASS_THRESHOLD = 0.8


def load_golden() -> list[dict]:
    """加载金标集"""
    if not GOLDEN_SET.exists():
        print(f"❌ 金标集不存在: {GOLDEN_SET}")
        print("   请先创建 (见 data/golden_set.example.json 模板)")
        sys.exit(1)
    with open(GOLDEN_SET, encoding="utf-8") as f:
        return json.load(f)


def evaluate_question(q: dict, top_k: int = 5, samples: int = 2) -> dict:
    """评测单题: 跑问答 samples 次取最高命中 (消除模型随机性)"""
    # AR-05: 统一包导入 (scripts.compliance_qa) — 避免 compliance_qa 与
    # scripts.compliance_qa 双模块状态干扰 (偶发 0ms ERR: 模型/组件状态不一致)
    from scripts.compliance_qa import answer

    # 期望词归一化匹配: 去空白后匹配 ("72小时" 匹配 "72 小时" — 中文数字单位常带空格)
    def _norm(s: str) -> str:
        return re.sub(r"\s+", "", s)

    question = q["question"]
    expects = q["expect"]
    # A1 (2026-09-11 L3): flags.regression_watch 透传 — watch 题 miss 在 main() 汇总告警
    watch = bool((q.get("flags") or {}).get("regression_watch"))

    best: dict = {"hit_rate": 0.0, "question": question, "expect": expects,
                  "covered": [], "ms": 0, "success": False, "answer_head": "", "watch": watch}
    for _ in range(samples):
        t0 = time.time()
        resp = None
        success = False
        last_err = "unknown"
        for attempt in range(3):  # 偶发 dlopen (torch ABI) / 网络抖动 → 重试
            try:
                # use_cache=False: eval 必须测当前 prompt 的真实表现, 不走记忆缓存
                resp = answer(question, top_k=top_k, use_cache=False)
                success = True
                break
            except Exception as e:
                last_err = str(e)
                time.sleep(1)
        if resp is None:
            resp = f"ERROR: {last_err}"
        ms = (time.time() - t0) * 1000
        covered = [e for e in expects if _norm(e) in _norm(resp)] if success else []
        hit_rate = len(covered) / len(expects) if expects else 0
        if success and hit_rate > best["hit_rate"]:
            best = {
                "question": question,
                "expect": expects,
                "covered": covered,
                "hit_rate": round(hit_rate, 2),
                "ms": round(ms),
                "success": success,
                "answer_head": resp[:100],
                "watch": watch,
            }
        elif not success and best["answer_head"] == "":
            # 失败也留痕: 记录首条错误, 否则全失败时 JSON 只有空壳无法诊断
            best = {
                "question": question,
                "expect": expects,
                "covered": [],
                "hit_rate": 0.0,
                "ms": round(ms),
                "success": False,
                "answer_head": f"ERR: {resp[:120]}",
                "watch": watch,
            }

    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="只跑前 10 题")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--samples", type=int, default=2,
                        help="每题采样次数 (默认 2; 3 用于稳定性评估, 耗时 x1.5)")
    args = parser.parse_args()

    golden = load_golden()
    if args.quick:
        golden = golden[:10]

    # 2026-09-03: domain=客户制度 的题跳过 — 期望词来自客户库文档 (acme 制度),
    # 全局库答不出 (系统性低分污染基线)。客户制度验收归 customer_accept
    # (data/customers/<name>/golden_set.json), 全局集只管全局题。
    n_skip = sum(1 for q in golden if q.get("domain") == "客户制度")
    golden = [q for q in golden if q.get("domain") != "客户制度"]
    if n_skip:
        print(f"(跳过 {n_skip} 题 domain=客户制度 — 归客户验收集)", file=sys.stderr)

    print(f"=== 金标评测 ({len(golden)} 题, samples={args.samples}) ===", file=sys.stderr)
    results = []
    total_hit = 0.0

    for i, q in enumerate(golden, 1):
        r = evaluate_question(q, samples=args.samples)
        results.append(r)
        total_hit += r["hit_rate"]
        mark = "✅" if r["hit_rate"] >= 0.5 else "⚠️"
        print(f"{mark} [{i}/{len(golden)}] {r['question'][:40]}", file=sys.stderr)
        print(f"    命中 {len(r['covered'])}/{len(r['expect'])} ({r['hit_rate']*100:.0f}%) "
              f"{r['ms']}ms", file=sys.stderr)

    # 失败题补跑 (2026-09-03): 批量中偶发 0ms (torch dlopen 抖动/网络瞬时),
    # 同进程 3 次重试可能连败 → 批后给一次新进程级机会, 仍失败才是真问题
    for i, r in enumerate(results):
        if not r["success"]:
            print(f"↻ 补跑失败题 [{i+1}] {r['question'][:40]}...", file=sys.stderr)
            retry = evaluate_question(
                {"question": r["question"], "expect": r["expect"],
                 "flags": {"regression_watch": True} if r.get("watch") else {}},
                samples=1)
            if retry["success"] and retry["hit_rate"] > r["hit_rate"]:
                results[i] = retry
                total_hit += retry["hit_rate"] - r["hit_rate"]
                print(f"  补跑通过: {retry['hit_rate']*100:.0f}%", file=sys.stderr)

    avg = total_hit / len(results) if results else 0
    passed = avg >= PASS_THRESHOLD

    # ── 回归门禁 (2026-09-03, 提案 A1): 结果持久化 + 逐题 baseline diff ──
    # 背景: corpus 扩到 903 chunks/168 docs 后 top-k 稀释, 两题 08-14 基线 1.0 → 0.67
    # 静默回归。从此每次运行落盘 eval_reports/, 并与最近一次同集基线对比,
    # 单题降幅 ≥0.33 (如 1.0→0.67) 即告警 (stdout JSON 带 regressions 字段)。
    report_dir = Path(__file__).resolve().parent.parent / "eval_reports"
    report_dir.mkdir(exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    out_path = report_dir / f"golden-{today}.json"

    regressions = []
    # C1 修复 (2026-09-04, 提案 P-2026-09-04-C1): diff 锚点 = 固定基线文件优先,
    # 缺失才 fallback 上一份报告 — 原实现对比 prev report, 首日无 predecessor 即哑火,
    # 且平台期 (0.67→0.67) 永不告警。阈值含边界 (round 后 <= prev - 0.33)。
    baseline_candidates = []
    fixed_baseline = Path(__file__).resolve().parent.parent / "data" / "golden_baseline_20260814.json"
    if fixed_baseline.exists():
        baseline_candidates.append(fixed_baseline)
    prev_paths = sorted(report_dir.glob("golden-*.json"))
    prev_paths = [p for p in prev_paths if p.name != out_path.name]
    if prev_paths:
        baseline_candidates.append(prev_paths[-1])
    prev_map: dict = {}
    for cand in baseline_candidates:
        try:
            prev = json.loads(cand.read_text(encoding="utf-8"))
            m = {r["question"]: r["hit_rate"] for r in prev.get("results", [])}
            if m:
                prev_map = m
                break
        except Exception:  # noqa: S112 — 基线损坏跳过, 尝试下一候选
            continue
    for r in results:
        p = prev_map.get(r["question"])
        # 整数比较 (浮点精度坑: 1.0-0.33=0.66999... 导致 0.67<=0.67 判 False, 2026-09-04 实证)
        if p is not None and round(r["hit_rate"] * 100) <= round(p * 100) - 33:
            regressions.append({
                "question": r["question"],
                "prev": p, "now": r["hit_rate"],
                "expect": r["expect"], "covered": r.get("covered", []),
            })
    for rg in regressions:
        print(f"⚠️ 回归告警: {rg['question'][:40]} {rg['prev']:.2f} → {rg['now']:.2f}",
              file=sys.stderr)

    # ── corpus 版本戳 + 归因快照 (2026-09-11 L3: P-2026-09-10-C1 / 09-11-C2) ──
    corpus_meta: dict = {}
    try:
        import duckdb
        _db = Path(__file__).resolve().parent.parent / "data" / "compliance.duckdb"
        _con = duckdb.connect(str(_db), read_only=True)
        _row = _con.execute("SELECT COUNT(*) FROM compliance_chunks").fetchone()
        corpus_meta["chunks"] = int(_row[0]) if _row else 0
        _con.close()
    except Exception as e:
        corpus_meta["error"] = str(e)[:120]
    # 注: data/kb_refresh.log 停更 (mtime 2026-08-05), 以 DB 文件 mtime 为 corpus 最近写入戳
    _dbf = Path(__file__).resolve().parent.parent / "data" / "compliance.duckdb"
    if _dbf.exists():
        corpus_meta["last_write"] = time.strftime(
            "%Y-%m-%d %H:%M", time.localtime(_dbf.stat().st_mtime))
    # 归因: regression/watch 题 expect 词 corpus_hits 快照 (0=真缺料转补料; >0=检索漂移)
    _hits_fn = None
    try:
        from scripts.kb_gap import _corpus_hits as _hits_fn
    except Exception:
        _hits_fn = None
    if _hits_fn:
        for rg in regressions:
            rg["corpus_hits"] = {w: _hits_fn(w) for w in rg.get("expect", [])}
    # watch 题 miss (A1): 期望词未全中即告警
    watch_misses = [r for r in results if r.get("watch") and r["hit_rate"] < 1.0]
    if _hits_fn:
        for w in watch_misses:
            w["corpus_hits"] = {e: _hits_fn(e) for e in w.get("expect", [])}
    for w in watch_misses:
        print(f"⭐ watch 题 miss: {w['question'][:40]} {w['hit_rate']:.2f} covered={w.get('covered')}",
              file=sys.stderr)
    # 跌幅榜 Top3 (A2): 相对基线单题跌幅
    drop_board = []
    for r in results:
        pv = prev_map.get(r["question"])
        if pv is not None:
            d = round(pv * 100) - round(r["hit_rate"] * 100)
            if d > 0:
                drop_board.append({"question": r["question"], "prev": pv,
                                   "now": r["hit_rate"], "drop": round(d / 100, 2)})
    drop_board.sort(key=lambda x: -x["drop"])
    drop_board = drop_board[:3]
    # WARN 口径 (A2): avg 过线但有显著回归/watch miss → 状态降级 warn (passed 字段保持兼容)
    status = "fail" if not passed else ("warn" if (regressions or watch_misses) else "pass")
    _suffix = {"pass": "✅ 通过", "warn": "⚠️ WARN (回归/watch miss)", "fail": "❌ 未通过 (<80%)"}[status]
    if drop_board:
        _top = "; ".join(f"{d['question'][:24]} -{d['drop']:.2f}" for d in drop_board)
        print(f"跌幅榜 Top{len(drop_board)}: {_top}", file=sys.stderr)
    print(f"\n=== 平均命中率: {avg*100:.1f}% {_suffix} ===", file=sys.stderr)

    # stdout 只输出 JSON (进度走 stderr) — 2026-08-14 修复: 基线文件曾被进度文本污染
    report = {"avg_hit_rate": round(avg, 3), "passed": passed, "status": status,
              "regressions": regressions, "watch_misses": watch_misses,
              "drop_board": drop_board, "corpus": corpus_meta, "results": results}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.quick:
        print("(quick 模式: 不落盘当日报告)", file=sys.stderr)
    else:
        try:
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        except Exception:
            pass  # 报告落盘失败不阻断

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
