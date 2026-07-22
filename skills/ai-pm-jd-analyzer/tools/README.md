<!--
目的：说明完整元模型可视化报告渲染器的边界与调用方式。
定义：随 ai-pm-jd-analyzer skill 分发的本地辅助工具目录。
范围包括：从完整 Markdown 报告生成离线 HTML 的确定性脚本。
范围不包括：不调用模型、网络、项目 API，不保存原始 JD 或调试日志。
使用与修改规则：由 Skill 在每次默认分析完成后生成 HTML；变更 JSON 契约时同步更新脚本和单元测试。
-->

# tools 目录说明

## 目的

把完整元模型报告的 JSON 附录转换为可离线打开的图形化报告。

## 定义

这是 skill 源包的一部分；复制 skill 安装副本时会一并复制。

## 范围包括

- `render_full_model_report.py`：解析报告 JSON 附录、校验引用并生成自包含 HTML；当前关系图支持元素筛选、鼠标拖拽、左下角按钮缩放和详情抽屉。

## 范围不包括

- 不启动服务、不访问网络、不调用 LLM、不读取 prompt、trace 或原始 JD 文件。

## 使用与修改规则

从 skill 根目录或任意目录运行均可：

```bash
python3 /path/to/ai-pm-jd-analyzer/tools/render_full_model_report.py \
  report.md --output report.html
```

- Skill 默认将 `report.md` 与 `report.html` 保存到调用目录的 `.agents/ai-pm-jd-reports/<unique-run-id>/`；已有文件不得覆盖。
- 输入 Markdown 必须含有“结构化模型 JSON”章节下唯一的 `json` fenced block。
- HTML 默认链接回输入 Markdown 的相对路径；移动其中一个文件时应一并移动另一个。
