"""
pulse/component.py — 最小热替换原语 (Cordis 原则的轻量 Python 版)

从 Cordis 论文 (Spatiotemporal Composability) 提取三条原则, 不移植框架:
1. 可撤回 (revertible): 组件有 build/stop 生命周期; 替换 = 新实例先 build → 原子换引用
   → 旧实例 drain (排空在途请求后 gc)。swap 失败自动回滚, 调用方无感。
2. 依赖按身份 (uid): 组件经 name 注册, 消费者用 get() 拿当前实例, 不持有全局变量
   (全局名绑定 = "换人了"无法感知; 身份绑定 = 每次 get 都拿最新)。
3. 失败隔离: build 抛异常 → 旧实例保持, 错误不冒泡到调用方业务路径。

适用: 进程内长驻、有共享状态、需要热更新的组件 (embedding 模型 / 连接池 / 工具注册表)。
不适用: 纯提示词 skill (过度设计) / 进程外工具 (MCP/子进程天然隔离)。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ManagedComponent:
    """按身份注册的进程内组件, 支持 build→swap→drain 热替换。

    name: 组件身份 (uid), 消费方经 get() 解析, 不持有实例引用。
    factory: 首次构建工厂 (懒加载)。
    """

    name: str
    factory: Callable[[], Any]
    _current: Any = field(default=None, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def get(self) -> Any:
        """拿当前实例 (懒构建); 换人后自动拿到新实例。"""
        with self._lock:
            if self._current is None:
                self._current = self.factory()
            return self._current

    def swap(self, new_factory: Callable[[], Any]) -> tuple[Any, Any]:
        """build → 原子换引用 → 返回 (old, new); 失败回滚, 旧实例不动。

        调用方拿到 old 后负责 drain (排空在途请求), 随后可安全释放。
        """
        with self._lock:
            old = self._current
            candidate = new_factory()      # build 失败 → 抛异常, 旧实例保持
            self._current = candidate      # 原子换引用: 之后的 get() 拿新实例
            return old, candidate

    def reset(self) -> Any | None:
        """卸载 (stop): 清空当前实例, 返回旧实例供 drain; 下次 get() 重新 build。"""
        with self._lock:
            old = self._current
            self._current = None
            return old

    @property
    def active(self) -> bool:
        return self._current is not None
