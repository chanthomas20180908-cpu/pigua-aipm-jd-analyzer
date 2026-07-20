<!--
目的：承载 FastAPI 直接服务的前端静态页面、样式、交互脚本和可视化资源。
定义：无构建步骤的静态前端目录，当前联调入口是 design-preview-02.html。
范围包括：
- HTML、CSS、浏览器 JS、D3 图谱渲染、本地 vendor 文件、错误页和展示素材。
范围不包括：
- 不放后端 Python 逻辑、不放测试集、不放服务端模板。
使用与修改规则：
- 当前功能优先修改 design-preview-02.*、graph-renderer.js、field-labels.js。
- 不要修改 static/d3.v7.min.js；需要升级时整体替换并记录来源。
-->

# static 目录说明

## 目的
承载 FastAPI 直接服务的前端静态页面、样式、交互脚本和可视化资源。

## 定义
无构建步骤的静态前端目录，当前联调入口是 design-preview-02.html。

## 范围包括
- HTML、CSS、浏览器 JS、D3 图谱渲染、本地 D3 vendor 文件、错误页和展示素材。

## 范围不包括
- 不放后端 Python 逻辑、不放测试集、不放服务端模板。

## 使用与修改规则
- 当前功能优先修改 `design-preview-02.*`、`about.*`、`meta-model.*`、`graph-renderer.js`、`field-labels.js`。
- `/sample` 与首页复用同一渲染器，fixture 位于 `fixtures/frontend-acceptance-v4.json`；更新时只能通过显式 trace 提取并先审阅 JSON diff。
- 首页本地历史使用浏览器 `localStorage` 键 `pigua-history-v1`，只保留最近 5 条，并须提供可见的清空入口。
- `theme.css` 与 `theme.js` 是三页共享主题基础，新页面优先复用。
- `/meta-model` 的图谱数据和渲染优先维护 `meta-model-data.js`、`meta-model-graph.js`。
- 品牌错误页维护 `error.html` / `error.css`，favicon 资源维护 `assets/favicon/`。
- `mammoth.browser.min.js` 是 `.docx` 文本读取的第三方浏览器 vendor；仅整体升级或替换，不在其中手工修改。
- 不要修改 static/d3.v7.min.js；需要升级时整体替换并记录来源。
