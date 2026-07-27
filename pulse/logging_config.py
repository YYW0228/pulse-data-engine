"""
pulse/logging_config.py — 结构化日志配置

双输出:
  - 控制台: 彩色时间戳格式 (human-friendly)
  - 文件: JSON Lines (可被 ELK/Datadog 聚合)
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """JSON Lines 格式, 每行一个结构化事件"""

    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


def setup_logging(log_dir: str = "data/logs", level: int = logging.INFO):
    """配置双通道日志系统"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # 清除默认 handler
    root.handlers.clear()

    # Handler 1: 控制台 (人类可读)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(console)

    # Handler 2: JSON Lines 文件 (可聚合)
    log_file = log_path / "pulse.jsonl"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    return log_file
