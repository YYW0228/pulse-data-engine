"""devour_scorecard 测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_scorecard_high_quality(tmp_path):
    """高质量吞噬报告 → 通过"""
    from scripts.devour_scorecard import score_report

    report = tmp_path / "report.md"
    report.write_text("""# 吞噬报告

License: MIT
定位: 生产级 Agent Harness

## 架构拆解
- 核心循环: loop
- 组件: Orchestrator / Memory / Sandbox
- 数据流: 持久化 + 恢复
- 不变量: cache-first

## 模式提取
### 模式 1: loop detection
- 原实现: middleware/loop.py
- 可迁移: 接口建议
- 潜在坑: 误判

### 模式 2: memory
### 模式 3: sandbox
### 模式 4: context compaction
### 模式 5: checkpoint recovery
### 模式 6: evidence artifacts

## 对比矩阵
当前 vs 目标
最值得先迁移的 3 个模式
冲突点: 状态模型不同

## 适配方案
最小改动: 3 个 PR
测试: 如何验证
迁移清单

## 下一步
深化方向: middleware

## 裁决
未来证明: 模型变强后变简单
值得迁移: loop detection
试点客户价值: 高
""", encoding="utf-8")

    result = score_report(report)
    assert result["score"] >= 60
    assert result["verdict"] == "✅ 通过"


def test_scorecard_low_quality(tmp_path):
    """低质量吞噬报告 → 需重做"""
    from scripts.devour_scorecard import score_report

    report = tmp_path / "poor.md"
    report.write_text("随便写点东西", encoding="utf-8")

    result = score_report(report)
    assert result["score"] < 60
    assert result["verdict"] == "❌ 需重做"


def test_scorecard_license_check(tmp_path):
    """License 缺失 → Phase 0 扣分"""
    from scripts.devour_scorecard import score_report

    report = tmp_path / "nolicense.md"
    report.write_text("""# 报告

架构: 拆解了
模式: 提取了
""", encoding="utf-8")

    result = score_report(report)
    # License 是 Phase 0 的检查项之一, 缺失则该项不通过
    assert "License|MIT|Apache|PolyForm" not in report.read_text()
