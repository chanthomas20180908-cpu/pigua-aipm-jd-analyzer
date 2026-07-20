/*
 * 目的：处理 about 展示页的轻交互。
 * 定义：负责 `/about` 的锚点平滑滚动增强。
 * 范围包括：
 * - 页面内锚点平滑滚动。
 * 范围不包括：
 * - 不请求后端接口，不生成页面结构，不重复实现主题切换。
 * 使用与修改规则：
 * - 主题切换已移交 `theme.js`，这里只保留页面行为。
 */

document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener("click", (event) => {
    const targetId = anchor.getAttribute("href");
    const target = document.querySelector(targetId);
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});
