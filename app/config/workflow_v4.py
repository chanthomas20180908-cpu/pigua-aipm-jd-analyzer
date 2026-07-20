"""目的：v4 工作流配置。

定义：定义 v4 三大模块和子模块执行顺序的配置文件。

范围包括：
- 模块分组、子模块名称和版本选择。

范围不包括：
- 不写 prompt 正文和 LLM 调用逻辑。

使用与修改规则：
- 变更模块名或版本前确认 SUB_MODULE_LIBRARY 已注册。
"""

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# v4 工作流配置
#
# 三大模块顺序执行，每个模块内的子模块顺序执行。
# 切换子模块版本：改 sub_modules 里的 version 字段。
# 增减子模块：在 sub_modules 列表中增删即可。
# ---------------------------------------------------------------------------

WORKFLOW_V4_CONFIG: Dict[str, Any] = {
    "version": "v4",
    "modules": [
        {
            "name": "modeling",
            "label": "模块一：建模分析",
            "sub_modules": [
                {"name": "element_modeling", "version": "v1"},
                {"name": "jd_core_judgment", "version": "v1"},
            ],
        },
        {
            "name": "quality_review",
            "label": "模块二：质检",
            "sub_modules": [
                {"name": "quality_check", "version": "v1"},
            ],
        },
        {
            "name": "summary",
            "label": "模块三：口语化总结",
            "sub_modules": [
                {"name": "narration", "version": "v1"},
            ],
        },
    ],
}
