# README 展示素材

这些素材用于仓库首页的简历入口展示，全部来自已审阅的
`static/fixtures/frontend-acceptance-v4.json` 冻结样例。

- `graph-focus.svg` 是一条真实分析路径的局部图谱，优先保证手机端可读性。
- `graph-full.svg` 汇总同一冻结样例的完整关系图。

SVG 直接用于 README，以保持文字清晰并把首次加载体积控制在很小范围；V1 不嵌入
GIF，避免动图下载和解码拖慢扫码后的首屏。

素材不得使用真实 JD、简历、trace、模型原始响应、密钥或本机路径。更新前须人工复核
冻结样例和 README 文案；在 `test_readme_showcase.py` 中保持文件存在性、大小预算和脱敏说明的校验。
