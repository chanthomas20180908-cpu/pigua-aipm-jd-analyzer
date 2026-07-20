/*
 * 目的：统一静态页的主题初始化与切换行为。
 * 定义：负责 `pigua-theme` 存储、白天默认主题和按钮文案同步。
 * 范围包括：
 * - 深浅主题解析、持久化和跨页面按钮绑定；首次访问默认白天。
 * 范围不包括：
 * - 不定义页面布局，不承载任何业务逻辑。
 * 使用与修改规则：
 * - 新增主题切换按钮时使用 `data-theme-toggle`。
 */

const THEME_KEY = "pigua-theme";
const LIGHT_THEME = "light";
const DARK_THEME = "dark";
const THEME_TOGGLE_SELECTOR = "[data-theme-toggle], #theme-toggle";
const themeMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
let listenersBound = false;

function safeStorageGet() {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === LIGHT_THEME || value === DARK_THEME ? value : null;
  } catch (error) {
    return null;
  }
}

function safeStorageSet(theme) {
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch (error) {
    // Ignore storage failures; the page can still follow system preference.
  }
}

function resolveTheme() {
  return safeStorageGet() || LIGHT_THEME;
}

function getCurrentTheme() {
  return document.documentElement.dataset.theme || resolveTheme();
}

function syncToggleLabels(theme) {
  const label = theme === DARK_THEME ? "切到白天" : "切到夜里";
  document.querySelectorAll(THEME_TOGGLE_SELECTOR).forEach((button) => {
    button.textContent = label;
    button.setAttribute("aria-pressed", theme === DARK_THEME ? "true" : "false");
  });
}

function applyTheme(theme) {
  const nextTheme = theme === DARK_THEME ? DARK_THEME : LIGHT_THEME;
  document.documentElement.dataset.theme = nextTheme;
  syncToggleLabels(nextTheme);
}

function setTheme(theme, { persist = true } = {}) {
  const nextTheme = theme === DARK_THEME ? DARK_THEME : LIGHT_THEME;
  applyTheme(nextTheme);
  if (persist) {
    safeStorageSet(nextTheme);
  }
}

function toggleTheme() {
  setTheme(getCurrentTheme() === DARK_THEME ? LIGHT_THEME : DARK_THEME);
}

function bindThemeControls() {
  if (listenersBound) return;
  listenersBound = true;

  document.querySelectorAll(THEME_TOGGLE_SELECTOR).forEach((button) => {
    button.addEventListener("click", toggleTheme);
  });

  if (typeof themeMediaQuery.addEventListener === "function") {
    themeMediaQuery.addEventListener("change", (event) => {
      if (safeStorageGet()) return;
      setTheme(event.matches ? DARK_THEME : LIGHT_THEME, { persist: false });
    });
  } else if (typeof themeMediaQuery.addListener === "function") {
    themeMediaQuery.addListener((event) => {
      if (safeStorageGet()) return;
      setTheme(event.matches ? DARK_THEME : LIGHT_THEME, { persist: false });
    });
  }
}

function initTheme() {
  applyTheme(resolveTheme());
  bindThemeControls();
}

document.documentElement.dataset.theme = resolveTheme();
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initTheme, { once: true });
} else {
  initTheme();
}

window.piguaTheme = {
  initTheme,
  toggleTheme,
  resolveTheme,
  setTheme,
  getCurrentTheme,
};
