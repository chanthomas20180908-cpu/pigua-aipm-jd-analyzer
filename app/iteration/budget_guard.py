"""目的：限制离线迭代 Loop 的运行预算。

定义：借鉴 Inspect AI limit 词汇的轻量预算守卫。

范围包括：
- wall time、LLM 调用数、token、估算成本、无改进轮数和显式预算状态判断。

范围不包括：
- 不读取供应商账单，不中断已经发出的网络请求。

使用与修改规则：
- 新增预算维度时同步 RunBudget 和报告输出。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.iteration.models import RunBudget


@dataclass
class BudgetGuard:
    budget: RunBudget
    started_at: float = field(default_factory=time.monotonic)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    llm_elapsed_seconds: float = 0.0
    best_score: float = 0.0
    stale_iterations: int = 0

    def record_llm_calls(self, count: int) -> None:
        self.llm_calls += count

    def record_usage(self, records: list[object]) -> None:
        for record in records:
            self.llm_calls += 1
            input_tokens = int(getattr(record, "input_tokens", 0) or 0)
            output_tokens = int(getattr(record, "output_tokens", 0) or 0)
            model = str(getattr(record, "model", "") or "")
            duration_ms = int(getattr(record, "duration_ms", 0) or 0)
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.llm_elapsed_seconds += duration_ms / 1000
            self.estimated_cost += _estimate_cost(model, input_tokens, output_tokens)

    def record_score(self, score: float) -> None:
        if score > self.best_score:
            self.best_score = score
            self.stale_iterations = 0
        else:
            self.stale_iterations += 1

    def snapshot(self) -> dict[str, float | int]:
        return {
            "elapsed_seconds": round(time.monotonic() - self.started_at, 2),
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost": round(self.estimated_cost, 6),
            "llm_elapsed_seconds": round(self.llm_elapsed_seconds, 2),
            "best_score": round(self.best_score, 4),
            "stale_iterations": self.stale_iterations,
        }

    def should_stop(self, iteration: int) -> tuple[bool, str]:
        elapsed = time.monotonic() - self.started_at
        if iteration >= self.budget.max_iterations:
            return True, "max_iterations"
        if elapsed >= self.budget.max_wall_seconds:
            return True, "max_wall_seconds"
        if self.llm_calls >= self.budget.max_llm_calls:
            return True, "max_llm_calls"
        if self.budget.max_input_tokens and self.input_tokens >= self.budget.max_input_tokens:
            return True, "max_input_tokens"
        if self.budget.max_output_tokens and self.output_tokens >= self.budget.max_output_tokens:
            return True, "max_output_tokens"
        if self.budget.max_cost_usd and self.estimated_cost >= self.budget.max_cost_usd:
            return True, "max_cost_usd"
        if self.stale_iterations >= self.budget.stop_after_no_improvement:
            return True, "no_improvement"
        return False, ""


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = {
        "qwen-plus": (0.0008, 0.0020),
        "qwen-turbo": (0.0003, 0.0006),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4o": (0.0025, 0.0100),
    }
    normalized = model.lower()
    input_price, output_price = prices.get(normalized, prices["qwen-plus"])
    return (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
