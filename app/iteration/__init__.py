"""目的：v4 迭代 Loop 包入口。

定义：暴露离线 Evaluator-Optimizer 组件的命名空间。

范围包括：
- 包版本和核心模型的便捷导入。

范围不包括：
- 不执行 loop，不触发 LLM 调用。

使用与修改规则：
- 新增公共 API 时保持脚本入口和文档同步。
"""

from __future__ import annotations

from app.iteration.models import EvalConfig, LoopReport, RunBudget, TrialResult, VariantSpec

__all__ = [
    "EvalConfig",
    "LoopReport",
    "RunBudget",
    "TrialResult",
    "VariantSpec",
]
