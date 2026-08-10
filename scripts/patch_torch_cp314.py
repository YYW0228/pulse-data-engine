"""patch_torch_cp314.py — 修复 torch 2.13.0 cp314 wheel 缺失 _is_kineto_stopped 符号

背景: torch 2.13.0 的 macOS cp314 wheel 构建缺陷 (torch/_C/_autograd 未导出
_is_kineto_stopped), 而 3.14 是唯一符号完整的本地 CPython。此脚本幂等注入
该符号 (False = kineto profiler 未运行, 与 CPU-only 默认语义一致)。

用法: uv run python scripts/patch_torch_cp314.py
"""
from __future__ import annotations

from pathlib import Path

AUTOGAD_INIT = (
    Path(__file__).resolve().parent.parent
    / ".venv/lib/python3.14/site-packages/torch/autograd/__init__.py"
)
MARKER = "# [patch_torch_cp314]"
INJECT = (
    "from torch._C import _autograd as _torch_c_autograd_patch  # noqa: E402\n"
    "if not hasattr(_torch_c_autograd_patch, '_is_kineto_stopped'):\n"
    "    # 补丁: torch 2.13.0 cp314 wheel 缺失该符号 (kineto 停止标志)\n"
    "    _torch_c_autograd_patch._is_kineto_stopped = lambda: False\n"
)


def main() -> int:
    if not AUTOGAD_INIT.exists():
        print(f"❌ 未找到 {AUTOGAD_INIT} (预期 python3.14 venv + torch 2.13)")
        return 1
    text = AUTOGAD_INIT.read_text()
    if MARKER in text:
        print("✅ 补丁已存在 (幂等跳过)")
        return 0
    anchor = "if not torch._C._autograd_init():\n    raise RuntimeError(\"autograd initialization failed\")\n"
    if anchor not in text:
        print("❌ 锚点未找到, 版本可能已变化, 请人工检查")
        return 1
    patched = text.replace(anchor, MARKER + "\n" + INJECT + "\n" + anchor, 1)
    AUTOGAD_INIT.write_text(patched)
    print(f"✅ 补丁已注入 {AUTOGAD_INIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
