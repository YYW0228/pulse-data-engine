"""
pulse/parsing.py — Output Parsing 层 (12组件第6项, 7层 Tools/Output 深化)

回答强制结构化: 模型输出 → 校验 → 结构化对象
失败处理: 重试 → 降级 (退回纯文本 + 标记)

设计:
  ComplianceAnswer (Pydantic 契约):
    answer: 正文
    citations: 引用列表 [{doc, section, snippet}]
    confidence: 置信度 (low/medium/high)
    disclaimer: 合规免责声明 (默认注入)

用法:
  parser = ComplianceParser()
  result = parser.parse(raw_text, retries=2)
  → ComplianceAnswer 或 (answer_text, fallback=True)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ── 结构化契约 ────────────────────────────────────────────────────────


class Citation(BaseModel):
    """引用来源"""

    doc: str = Field(..., description="文档名")
    section: str = Field("", description="章节")
    snippet: str = Field("", description="引用片段 (前 200 字)")


class ComplianceAnswer(BaseModel):
    """合规问答结构化输出契约"""

    answer: str = Field(..., min_length=10, description="回答正文")
    citations: list[Citation] = Field(default_factory=list, description="引用列表")
    confidence: str = Field("medium", description="置信度: low/medium/high")
    disclaimer: str = Field("", description="免责声明")

    @field_validator("confidence")
    @classmethod
    def _conf_valid(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            return "medium"
        return v


# ── Parser ────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    """解析结果 (成功或降级)"""

    answer: ComplianceAnswer | None
    raw: str
    fallback: bool = False  # True = 解析失败降级为纯文本
    error: str = ""


class ComplianceParser:
    """从模型输出解析结构化回答

    策略:
      1. 尝试 JSON 提取 (```json 块 或 纯 JSON)
      2. 尝试 markdown 引用解析 ([文档: xxx | 章节: yyy])
      3. 失败 → 降级: 纯文本 + 自动提取引用 + 默认免责声明
    """

    DISCLAIMER = "本回答基于内部合规知识库生成，仅供参考，不构成法律意见。重大决策请咨询专业法务。"
    CITATION_RE = re.compile(r"\[文档:\s*([^|\]]+?)\s*(?:\|\s*章节:\s*([^\]]+?))?\]")

    def parse(self, raw: str, retries: int = 2) -> ParseResult:
        """解析 (内部重试: 先 JSON, 再 markdown, 最后降级)"""
        # 尝试 1: JSON 结构化
        obj = self._extract_json(raw)
        if obj is not None:
            try:
                ans = ComplianceAnswer(**obj)
                return ParseResult(answer=ans, raw=raw, fallback=False)
            except Exception:
                pass

        # 尝试 2: markdown 引用解析
        citations = self._parse_citations(raw)
        body = self._strip_citations(raw)
        if len(body) >= 10:
            ans = ComplianceAnswer(
                answer=body,
                citations=citations,
                confidence=self._estimate_confidence(raw, citations),
                disclaimer=self.DISCLAIMER,
            )
            return ParseResult(answer=ans, raw=raw, fallback=False)

        # 降级: 纯文本
        return ParseResult(
            answer=None,
            raw=raw,
            fallback=True,
            error="structured parse failed, fell back to raw",
        )

    # ── 内部方法 ──────────────────────────────────────────────────────
    def _extract_json(self, raw: str) -> dict[str, Any] | None:
        """提取 JSON (```json 块 或 整个输出)"""
        # fenced block
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        candidates: list[str] = []
        if m:
            candidates.append(m.group(1))
        # 裸 JSON
        stripped = raw.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            candidates.append(stripped)

        for c in candidates:
            try:
                return json.loads(c)
            except json.JSONDecodeError:
                continue
        return None

    def _parse_citations(self, raw: str) -> list[Citation]:
        """从 [文档: xxx | 章节: yyy] 提取引用"""
        citations = []
        seen: set[tuple[str, str]] = set()
        for m in self.CITATION_RE.finditer(raw):
            doc = m.group(1).strip()
            section = (m.group(2) or "").strip()
            key = (doc, section)
            if key not in seen:
                seen.add(key)
                citations.append(Citation(doc=doc, section=section, snippet=""))
        return citations

    def _strip_citations(self, raw: str) -> str:
        """去掉引用标记, 保留正文"""
        body = self.CITATION_RE.sub("", raw)
        # 去掉引用来源尾部清单
        body = re.sub(r"\n*引用来源[：:].*$", "", body, flags=re.DOTALL)
        return body.strip()

    def _estimate_confidence(self, raw: str, citations: list[Citation]) -> str:
        """置信度启发式: 引用多 + 无'未找到' → high"""
        if "未找到" in raw or "资料中未找到" in raw:
            return "low"
        if len(citations) >= 3:
            return "high"
        if len(citations) >= 1:
            return "medium"
        return "low"


if __name__ == "__main__":
    parser = ComplianceParser()

    # 测试 1: JSON 结构化输出
    json_raw = '```json\n{"answer": "算法备案需在10个工作日内完成", "citations": [{"doc": "cac.md", "section": "一"}], "confidence": "high"}\n```'
    r1 = parser.parse(json_raw)
    print(f"[JSON] fallback={r1.fallback} | answer={r1.answer.answer[:20] if r1.answer else '?'} | conf={r1.answer.confidence if r1.answer else '?'}")

    # 测试 2: markdown 引用
    md_raw = "根据规定需要备案 [文档: cac.md | 章节: 一、制度概述]。另需评估 [文档: genai.md | 章节: 3.1]。\n\n引用来源：\n- cac.md"
    r2 = parser.parse(md_raw)
    print(f"[MD] fallback={r2.fallback} | citations={len(r2.answer.citations) if r2.answer else 0} | conf={r2.answer.confidence if r2.answer else '?'}")

    # 测试 3: 降级 (无引用纯文本)
    r3 = parser.parse("简单回答，没有引用")
    print(f"[FALLBACK] fallback={r3.fallback} | error={r3.error}")
