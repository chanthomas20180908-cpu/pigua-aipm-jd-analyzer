"""目的：生成 prompt 变体候选。

定义：DSPy optimizer 的轻量适配层；无 DSPy 依赖时使用规则化候选生成。

范围包括：
- 根据失败归因生成 system prompt 追加约束和温度变体。

范围不包括：
- 不直接修改源码文件，不运行评估，不承诺全局最优搜索。

使用与修改规则：
- 引入真实 DSPy 优化器时保持 VariantSpec 输出契约不变。
"""

from __future__ import annotations

from typing import Callable

from app.iteration.models import VariantSpec

try:
    import dspy
except Exception:  # pragma: no cover - optional runtime dependency until installed.
    dspy = None


if dspy is not None:
    class PromptVariantSignature(dspy.Signature):
        """Generate a constrained prompt variant."""

        target = dspy.InputField()
        current_system_prompt = dspy.InputField()
        failure_reasons = dspy.InputField()
        constraints = dspy.InputField()
        improved_suffix = dspy.OutputField()
        temperature = dspy.OutputField()
else:
    PromptVariantSignature = None


class VariantGenerator:
    def __init__(self, *, target: str):
        self.target = target
        self._history: list[tuple[VariantSpec, float, list[str]]] = []

    def baseline(self) -> VariantSpec:
        return VariantSpec(
            id="baseline",
            target=self.target,
            description="Current production prompt and workflow config.",
        )

    def next_variant(
        self,
        *,
        iteration: int,
        constraints: list[str],
        current_system_prompt: str = "",
        scorer: Callable[[VariantSpec], float] | None = None,
    ) -> VariantSpec:
        candidates = self.generate_candidates(
            iteration=iteration,
            constraints=constraints,
            current_system_prompt=current_system_prompt,
        )
        if not scorer:
            return candidates[0]

        scored = [(candidate, scorer(candidate)) for candidate in candidates]
        best, best_score = max(scored, key=lambda item: item[1])
        baseline_score = scorer(self.baseline())
        if best_score < baseline_score:
            fallback_candidates = [
                self._rule_variant(iteration=iteration, constraints=constraints, suffix_id="evidence"),
                self._rule_variant(iteration=iteration, constraints=constraints, suffix_id="integrity"),
                self._rule_variant(iteration=iteration, constraints=constraints, suffix_id="coverage"),
            ]
            scored_fallbacks = [
                (candidate, scorer(candidate)) for candidate in fallback_candidates
            ]
            best_fallback, best_fallback_score = max(scored_fallbacks, key=lambda item: item[1])
            self._history.append((best_fallback, best_fallback_score, constraints))
            return best_fallback
        self._history.append((best, best_score, constraints))
        return best

    def generate_candidates(
        self,
        *,
        iteration: int,
        constraints: list[str],
        current_system_prompt: str = "",
    ) -> list[VariantSpec]:
        dspy_candidate = self._dspy_candidate(
            iteration=iteration,
            constraints=constraints,
            current_system_prompt=current_system_prompt,
        )
        candidates = [
            dspy_candidate,
            self._rule_variant(iteration=iteration, constraints=constraints, suffix_id="evidence"),
            self._rule_variant(iteration=iteration, constraints=constraints, suffix_id="integrity"),
            self._rule_variant(iteration=iteration, constraints=constraints, suffix_id="coverage"),
        ]
        return [candidate for candidate in candidates if candidate is not None]

    def _dspy_candidate(
        self,
        *,
        iteration: int,
        constraints: list[str],
        current_system_prompt: str,
    ) -> VariantSpec | None:
        if dspy is None or PromptVariantSignature is None:
            return None
        predictor = dspy.Predict(PromptVariantSignature)
        if len(self._history) >= 3:
            demos = [
                dspy.Example(
                    target=self.target,
                    current_system_prompt=current_system_prompt,
                    failure_reasons=", ".join(reasons),
                    constraints=", ".join(reasons),
                    improved_suffix=variant.system_prompt_suffix,
                    temperature=str(variant.temperature or 0.2),
                ).with_inputs("target", "current_system_prompt", "failure_reasons", "constraints")
                for variant, _, reasons in self._history[-6:]
            ]
            optimizer = dspy.BootstrapFewShot()
            predictor = optimizer.compile(predictor, trainset=demos)
        try:
            result = predictor(
                target=self.target,
                current_system_prompt=current_system_prompt,
                failure_reasons="\n".join(constraints),
                constraints="\n".join(constraints),
            )
        except Exception:
            return None
        suffix = str(getattr(result, "improved_suffix", "") or "").strip()
        if not suffix:
            return None
        try:
            temperature = float(getattr(result, "temperature", 0.2))
        except (TypeError, ValueError):
            temperature = 0.2
        return VariantSpec(
            id=f"variant-{iteration:02d}-dspy",
            target=self.target,
            description="Prompt variant generated by DSPy Signature.",
            system_prompt_suffix="\n\n" + suffix,
            temperature=max(0.0, min(1.0, temperature)),
            metadata={"constraints": constraints[:10], "generator": "dspy"},
        )

    def _rule_variant(self, *, iteration: int, constraints: list[str], suffix_id: str) -> VariantSpec:
        suffix_lines = [
            "",
            "## 迭代约束",
            "以下约束来自上一轮失败归因，必须优先满足：",
        ]
        suffix_lines.extend(f"- {constraint}" for constraint in constraints[:10])
        if not constraints:
            suffix_lines.append("- 保持当前 schema 不变，优先提高证据忠实度和 ID 引用自洽。")
        if suffix_id == "integrity":
            suffix_lines.append("- 输出前自检所有 ID 引用；任何引用必须能在同一 JSON 数组中找到对应 id。")
        if suffix_id == "evidence":
            suffix_lines.append("- source_evidence 必须优先截取 JD 原文短句，不能用总结性改写替代证据。")
        if suffix_id == "coverage":
            suffix_lines.append("- 不要只抽象总结职责；至少覆盖主业务流程、核心工作项、关键实体和能力边界。")
        return VariantSpec(
            id=f"variant-{iteration:02d}-{suffix_id}",
            target=self.target,
            description="Prompt variant generated from deterministic failure reasons.",
            system_prompt_suffix="\n".join(suffix_lines),
            temperature=0.2,
            metadata={"constraints": constraints[:10], "generator": "rule"},
        )
