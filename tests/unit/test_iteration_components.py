"""目的：覆盖 iteration 核心组件的回归风险点。

定义：Reflector、VariantGenerator 和 BudgetGuard 的窄范围单元测试。

范围包括：
- 抽象实体反思约束、10 条约束上限和 plateau 早停行为。

范围不包括：
- 不调用真实 LLM，不运行完整 loop，不验证 Git/worktree 副作用。

使用与修改规则：
- 保持纯本地、确定性；新增预算或约束策略时同步补充断言。
"""

from __future__ import annotations

import unittest

from app.iteration.budget_guard import BudgetGuard
from app.iteration.generator import VariantGenerator
from app.iteration.models import CaseEvalResult, RunBudget, TrialResult, VariantSpec
from app.iteration.reflector import Reflector


class ReflectorTests(unittest.TestCase):
    def test_abstract_entity_reason_returns_explicit_forbidden_list(self) -> None:
        reflector = Reflector()
        trial = TrialResult(
            iteration=1,
            variant=VariantSpec(id="v1", target="element_modeling", description="test"),
            score=0.4,
            passed=False,
            failure_reasons=["abstract_entity"],
            case_results=[
                CaseEvalResult(
                    case_id="case_003",
                    score=0.4,
                    passed=False,
                    metrics={"failure_tags": ["abstract_entity"]},
                )
            ],
        )

        constraints = reflector.reflect(trial)

        self.assertEqual(len(constraints), 1)
        self.assertIn("禁止输出抽象总称实体/工作事项", constraints[0])
        self.assertIn("平台能力定义", constraints[0])
        self.assertIn("后台配置能力", constraints[0])
        self.assertIn("抽象可复用平台能力", constraints[0])
        self.assertIn("AI能力边界", constraints[0])
        self.assertIn("知识库", constraints[0])
        self.assertIn("智能问答", constraints[0])
        self.assertIn("Agent编排", constraints[0])
        self.assertIn("工作流", constraints[0])
        self.assertIn("模型服务", constraints[0])
        self.assertIn("平台API", constraints[0])


class VariantGeneratorTests(unittest.TestCase):
    def test_rule_variant_keeps_first_ten_constraints(self) -> None:
        generator = VariantGenerator(target="element_modeling")
        constraints = [f"constraint-{index}" for index in range(12)]

        variant = generator.generate_candidates(
            iteration=2,
            constraints=constraints,
            current_system_prompt="",
        )[0]

        self.assertEqual(variant.metadata["constraints"], constraints[:10])
        self.assertIn("- constraint-9", variant.system_prompt_suffix)
        self.assertNotIn("- constraint-10", variant.system_prompt_suffix)
        self.assertNotIn("- constraint-11", variant.system_prompt_suffix)


class BudgetGuardTests(unittest.TestCase):
    def test_stop_after_single_stale_iteration(self) -> None:
        guard = BudgetGuard(
            budget=RunBudget(
                max_iterations=5,
                max_wall_seconds=600,
                max_llm_calls=80,
                stop_after_no_improvement=1,
            )
        )

        guard.record_score(0.9)
        guard.record_score(0.9)

        should_stop, reason = guard.should_stop(iteration=2)

        self.assertTrue(should_stop)
        self.assertEqual(reason, "no_improvement")


if __name__ == "__main__":
    unittest.main()
