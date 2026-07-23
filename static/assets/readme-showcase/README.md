# README 展示素材

这些素材用于仓库首页的简历入口展示，全部来自已审阅的
`static/fixtures/frontend-acceptance-v4.json` 冻结样例和生产前端渲染器。

- `hero-result.webp`：`/sample` 的结果页和关系图主视觉，≤ 400 KB。
- `graph-focus.svg`：一条真实分析路径的局部图谱，优先保证手机端可读性。
- `graph-full.svg`：同一冻结样例的完整岗位关系图。
- `../hero-screenshot.webp`：原版 README 的九宫格卡皮巴拉品牌视觉，900×900、WebP Q85、≤ 100 KB。

截图以 1440px 桌面视口采集；两张 SVG 直接用于 README，以保持文字清晰并控制扫码后的首次
加载体积。页面不嵌入 GIF，避免下载和解码拖慢首屏。

素材不得使用真实 JD、简历、trace、模型原始响应、密钥或本机路径。更新前须人工复核
冻结样例和 README 文案；在 `test_readme_showcase.py` 中保持文件存在性、大小预算和脱敏说明的校验。
