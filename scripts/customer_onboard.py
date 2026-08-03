"""
scripts/customer_onboard.py — 客户文档模板化 + 一键独立索引库

试点交付工具: 新客户 5 分钟完成数据接入
  1. 创建客户目录结构 (data/customers/<name>/raw/)
  2. 复制文档模板 (README/目录说明)
  3. 索引 raw/ 下所有文档 → 独立 DuckDB (数据隔离)
  4. 生成接入报告 (文档数/块数/字符数)

用法:
  uv run python -m scripts.customer_onboard --name acme
  uv run python -m scripts.customer_onboard --name acme --source /path/to/docs
  uv run python -m scripts.customer_onboard --list        # 列出已接入客户

目录结构:
  data/customers/acme/
    raw/          ← 客户文档放这里 (md/pdf/docx/txt)
    acme.duckdb   ← 独立向量库 (自动生成)
    REPORT.md     ← 接入报告 (自动生成)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUSTOMERS = ROOT / "data" / "customers"

TEMPLATE_README = """# 客户数据接入说明

> 请将客户的制度/法规/合同/手册等文档放入 `raw/` 目录。
> 支持格式: .md .txt .pdf .docx (pdf/docx 会被 doc_parser 解析)

## 建议
- 20-50 份文档覆盖客户核心业务
- 文档命名清晰 (如: 信息安全管理制度.md)
- 敏感文档脱敏后再提供 (手机号/身份证/内部金额)

## 接入流程 (我们执行)
1. 文档放入 raw/
2. 运行: uv run python -m scripts.customer_onboard --name <客户名>
3. 输出: 独立向量库 + 接入报告 (REPORT.md)
4. 验收: 30-50 道金标问题 → 命中率 ≥80%
"""

TEMPLATE_REPORT = """# 客户接入报告: {name}

> 生成时间: {ts}

## 数据概况
| 指标 | 值 |
|------|-----|
| 文档数 | {docs} |
| 分块数 | {chunks} |
| 字符数 | {chars:,} |
| 独立库 | {db_path} |

## 下一步
1. 定义 30-50 道金标验收问题
2. 运行问答验证: `uv run python -m scripts.compliance_qa --query "..."` (需先 set_customer_db)
3. 调整分块/检索参数直到金标命中 ≥80%
"""


def onboard(name: str, source: str | None = None) -> dict:
    """创建客户库 + 索引文档, 返回接入报告"""
    cust_dir = CUSTOMERS / name
    raw_dir = cust_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. 复制模板 README (首次)
    readme = cust_dir / "README.md"
    if not readme.exists():
        readme.write_text(TEMPLATE_README, encoding="utf-8")

    # 2. 复制客户文档 (若提供 source)
    copied = 0
    if source:
        src = Path(source)
        if src.is_dir():
            for f in src.rglob("*"):
                if f.is_file() and f.suffix.lower() in (".md", ".txt", ".pdf", ".docx", ".jsonl"):
                    shutil.copy2(f, raw_dir / f.name)
                    copied += 1
        elif src.is_file():
            shutil.copy2(src, raw_dir / src.name)
            copied += 1

    # 3. 索引 → 独立库 (先解析 pdf/docx)
    parse_jsonl = _parse_docs(raw_dir, cust_dir)

    cmd = [
        sys.executable, "-m", "scripts.compliance_index",
        "--source", str(raw_dir), "--rebuild", "--include-jsonl",
        "--db", name,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=600)
    out = r.stdout + r.stderr

    docs = chunks = chars = 0
    for line in out.splitlines():
        if "文档:" in line:
            docs = int(line.split(":")[1].strip().replace("个", ""))
        if "分块:" in line:
            chunks = int(line.split(":")[1].strip().replace("个", ""))
        if "字符:" in line:
            chars = int(line.split(":")[1].strip().replace(",", ""))

    # 4. 生成报告
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    report = cust_dir / "REPORT.md"
    report.write_text(TEMPLATE_REPORT.format(
        name=name, ts=ts, docs=docs, chunks=chunks, chars=chars,
        db_path=f"data/customers/{name}/{name}.duckdb",
    ), encoding="utf-8")

    return {
        "name": name, "docs": docs, "chunks": chunks, "chars": chars,
        "copied": copied, "parsed": parse_jsonl,
        "db": f"data/customers/{name}/{name}.duckdb",
        "report": str(report), "exit": r.returncode,
    }


def _parse_docs(raw_dir: Path, cust_dir: Path) -> int:
    """解析 pdf/docx → jsonl (doc_parser), 返回解析文件数"""
    parsed = 0
    jsonl_out = cust_dir / "parsed"
    jsonl_out.mkdir(exist_ok=True)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from doc_parser import parse_file
        for f in raw_dir.iterdir():
            if f.suffix.lower() in (".pdf", ".docx"):
                out_path = parse_file(f)  # 返回输出 jsonl 路径
                if out_path and Path(out_path).exists():
                    # 复制到客户 parsed/ 目录
                    shutil.copy2(out_path, jsonl_out / Path(out_path).name)
                parsed += 1
    except Exception:
        pass
    return parsed


def list_customers() -> list[str]:
    """列出已接入客户"""
    if not CUSTOMERS.exists():
        return []
    return sorted(d.name for d in CUSTOMERS.iterdir()
                  if d.is_dir() and (d / f"{d.name}.duckdb").exists())


def main():
    parser = argparse.ArgumentParser(description="客户文档接入")
    parser.add_argument("--name", help="客户标识")
    parser.add_argument("--source", default=None, help="文档目录/文件")
    parser.add_argument("--list", action="store_true", help="列出已接入客户")
    args = parser.parse_args()

    if args.list:
        customers = list_customers()
        if not customers:
            print("暂无已接入客户")
        for c in customers:
            print(f"  ✅ {c} (data/customers/{c}/{c}.duckdb)")
        return

    if not args.name:
        parser.print_help()
        sys.exit(1)

    result = onboard(args.name, args.source)
    print(f"=== 客户接入: {result['name']} ===")
    print(f"文档: {result['docs']} (复制 {result['copied']} + 解析 {result['parsed']})")
    print(f"分块: {result['chunks']} | 字符: {result['chars']:,}")
    print(f"独立库: {result['db']}")
    print(f"报告: {result['report']}")
    ok = result["exit"] == 0 and result["chunks"] > 0
    print(f"结果: {'✅ 接入成功' if ok else '❌ 失败'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
