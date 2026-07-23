# README 展示素材

这些素材用于仓库首页的简历入口展示，全部来自已审阅的
`static/fixtures/frontend-acceptance-v4.json` 冻结样例和生产前端渲染器。

- `hero-result.webp`：`/sample` 的结果页和关系图主视觉，≤ 400 KB。
- `flow-view.webp`：`/sample` 切换到流程图后的真实结果视图，≤ 350 KB。
- `product-flow.gif`：输入、加载和结果三段真实页面状态组成的 6 秒展示流程，≤ 2.5 MB。

截图以 1440px 桌面视口采集；GIF 是脱敏冻结展示流程，不会调用模型。首张静态主视觉优先
加载，动图作为产品体验证据紧随其后。

素材不得使用真实 JD、简历、trace、模型原始响应、密钥或本机路径。更新前须人工复核
冻结样例和 README 文案；在 `test_readme_showcase.py` 中保持文件存在性、大小预算和脱敏说明的校验。
