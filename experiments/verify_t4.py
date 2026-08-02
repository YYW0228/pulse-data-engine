"""T4 reactive_compaction 验证脚本"""

import os
import sys

sys.path.insert(0, "scripts")
from compliance_qa import _dump_large_chunk, _reactive_compact

# 1. 大块存盘
path = _dump_large_chunk("测试文档", "大块章节", "内容" * 5000)
print("存盘:", path, "| 文件大小:", os.path.getsize(path))
assert os.path.getsize(path) > 5000, "存盘内容不完整"

# 2. 反应式压缩
msgs = [{"role": "system", "content": "sys"}]
history_flat: list[dict] = []
for i in range(10):
    history_flat.append({"role": "user", "content": f"q{i}"})
    history_flat.append({"role": "assistant", "content": f"a{i}"})
msgs_full = msgs + history_flat + [{"role": "user", "content": "当前问题"}]

compacted = _reactive_compact(msgs_full, history_flat)
assert compacted is not None, "应能压缩"
print("压缩后消息数:", len(compacted))
print("压缩后角色:", [m["role"] for m in compacted])
assert len(compacted) == 8, f"预期 8 (system+6+当前), 实际 {len(compacted)}"

# 3. 历史太短不压缩
short = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
assert _reactive_compact(msgs + short, short) is None, "短历史不应压缩"

print("\n✅ T4 验证通过 (大块存盘 + 反应式压缩)")
