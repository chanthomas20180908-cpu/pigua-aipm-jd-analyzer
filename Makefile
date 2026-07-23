# 目的：提供项目级一键运行与检查入口。
# 定义：面向本地开发和 CI 的 Make 命令集合。
# 范围包括：
# - dev、demo、health、test、ci 等常用命令。
# 范围不包括：
# - 不承载业务逻辑，不替代 Python 脚本和测试文件。
# 使用与修改规则：
# - 新增命令时保持无副作用优先，并同步 README 的快速开始说明。

PYTHON ?= python3
HOST ?= 127.0.0.1
PORT ?= 8000
PYTHONPYCACHEPREFIX ?= /tmp/aipm_resume_analyzer_pycache

.PHONY: dev demo health boundary test ci compile

dev:
	$(PYTHON) scripts/dev.py --host $(HOST) --port $(PORT)

demo:
	@printf "Health check:\n"
	@printf "  curl http://$(HOST):$(PORT)/health\n\n"
	@printf "Demo payload:\n"
	@printf "  curl http://$(HOST):$(PORT)/demo\n\n"
	@printf "Analyze v4:\n"
	@printf "  curl -X POST http://$(HOST):$(PORT)/analyze/v4 -H 'Content-Type: application/json' -d '{\"jd_text\":\"负责 AI Agent 产品规划与落地，围绕企业知识库、工作流自动化和智能助手场景，完成需求分析、Prompt 设计、效果评估和跨团队推进，对用户体验和业务指标负责。\"}'\n"

health:
	curl -fsS http://$(HOST):$(PORT)/health

compile:
	PYTHONPYCACHEPREFIX=$(PYTHONPYCACHEPREFIX) $(PYTHON) -m compileall app scripts tests

boundary:
	$(PYTHON) scripts/verify_public_boundary.py

test: compile
	$(PYTHON) -m unittest tests.unit.test_public_boundary -v
	$(PYTHON) -m unittest tests.unit.test_makefile_portability -v
	$(PYTHON) -m unittest tests.unit.test_iteration_components -v
	$(PYTHON) -m pytest tests/unit/test_llm_client.py tests/unit/test_narration_prompt.py
	$(PYTHON) -m unittest tests.unit.test_frontend_structure -v
	$(PYTHON) -m unittest tests.unit.test_frontend_sample_extractor -v
	$(PYTHON) -m unittest tests.unit.test_ai_pm_jd_skill -v
	$(PYTHON) -m unittest tests.unit.test_full_model_report_renderer -v
	$(PYTHON) -m unittest tests.unit.test_local_skill_loop_initializer -v

ci: boundary test
