/*
 * 目的：当前联调页面交互。
 * 定义：驱动 design-preview-02.html 的浏览器端状态、请求和结果渲染。
 * 范围包括：
 * - 表单提交、loading 动画、/analyze/v4 调用、结构化结果渲染入口。
 * 范围不包括：
 * - 不定义后端 schema，不修改 LLM 结果。
 * 使用与修改规则：
 * - 后端字段变化时同步 renderStructured、renderGraph 和 field-labels。
 */

const MASCOT_FRAME_MS = 2000;
const MASCOT_FRAMES = [
  "/static/assets/pigua/frame-01.png",
  "/static/assets/pigua/frame-02.png",
  "/static/assets/pigua/frame-03.png",
  "/static/assets/pigua/frame-04.png",
  "/static/assets/pigua/frame-05.png",
];

const API_URL = "/analyze/v4";
const API_TIMEOUT_MS = 120000;
const HISTORY_STORAGE_KEY = "pigua-history-v1";
const HISTORY_LIMIT = 5;
const SAMPLE_FIXTURE_URL = "/static/fixtures/frontend-acceptance-v4.json";
const isSampleMode = window.location.pathname === "/sample";

const page = document.getElementById("preview-page");
const form = document.getElementById("preview-form");
const jdText = document.getElementById("jd-text");
const formError = document.getElementById("form-error");
const inputView = document.getElementById("input-view");
const loadingView = document.getElementById("loading-view");
const resultView = document.getElementById("result-view");
const resultContent = document.getElementById("result-content");
const resultSummary = document.getElementById("result-summary");
const resultExportToolbar = document.getElementById("result-export-toolbar");
const downloadJsonButton = document.getElementById("download-json-button");
const downloadMarkdownButton = document.getElementById("download-markdown-button");
const copyTraceButton = document.getElementById("copy-trace-button");
const exportStatus = document.getElementById("export-status");
const resultResetButton = document.getElementById("result-reset-button");
const graphCard = document.getElementById("graphCard");
const graphFullscreenToggle = document.getElementById("graph-fullscreen-toggle");
const sampleBanner = document.getElementById("sample-banner");
const sampleBannerDetail = document.getElementById("sample-banner-detail");
const mascotFrame = document.getElementById("mascot-frame");
const mascotPlaceholder = document.getElementById("mascot-placeholder");
const loadingStatus = document.getElementById("loading-status");
const historyPanel = document.getElementById("history-panel");
const historyList = document.getElementById("history-list");
const historyClearButton = document.getElementById("history-clear-button");
let mascotFrameIndex = 0;
let abortController = null;
let currentResult = null;
let loadingStatusTimer = null;
let graphFullscreenPlaceholder = null;
let graphFullscreenParent = null;

const LOADING_STATUS_MESSAGES = [
  "分析通常需要 60-90 秒，卡皮巴拉正在卖力劈瓜...",
  "正在把 JD 拆成业务元素，先看看这瓜从哪儿长出来。",
  "正在核对岗位重点和风险，别急，瓜瓤马上就露出来。",
  "正在整理结论和图谱，最后一刀要劈得准。",
];

const HistoryManager = {
  read: function() {
    try {
      const history = JSON.parse(window.localStorage.getItem(HISTORY_STORAGE_KEY) || "[]");
      return Array.isArray(history) ? history : [];
    } catch (error) {
      return [];
    }
  },

  save: function(jd, result) {
    if (!jd || !result) return;
    const entry = {
      jd: jd,
      preview: jd.replace(/\s+/g, " ").slice(0, 50),
      conclusionLabel: (result.narration && result.narration.conclusion_label) || "已分析",
      traceId: (result._meta && result._meta.trace_id) || "",
      createdAt: new Date().toISOString(),
    };
    const history = this.read().filter(function(item) { return item.jd !== jd; });
    try {
      window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify([entry].concat(history).slice(0, HISTORY_LIMIT)));
    } catch (error) {
      // 本地存储不可用时不影响本次分析结果展示。
    }
  },

  clear: function() {
    try {
      window.localStorage.removeItem(HISTORY_STORAGE_KEY);
    } catch (error) {
      // 本地存储不可用时，页面仍可继续使用。
    }
  },
};

/* ------------------------------------------------------------------ */
/*  state helpers                                                      */
/* ------------------------------------------------------------------ */

function hasInputs() {
  return jdText.value.trim().length > 0;
}

function setState(nextState) {
  page.dataset.state = nextState;

  inputView.hidden = nextState !== "input";
  loadingView.hidden = nextState !== "loading";
  resultView.hidden = nextState !== "result";
}

function showInputError() {
  formError.textContent = "先放岗位描述，才能劈瓜。";
  formError.classList.add("is-error");
  formError.classList.remove("is-success");
  formError.hidden = false;
}

function clearInputError() {
  formError.hidden = true;
  formError.classList.remove("is-error", "is-success");
}

function formatHistoryTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function renderHistory() {
  const history = HistoryManager.read();
  historyPanel.hidden = history.length === 0;
  historyList.innerHTML = history.map(function(item, index) {
    return (
      `<li class="history-item">` +
      `<button class="history-item-button" type="button" data-history-index="${index}">` +
      `<span class="history-item-title">${escapeHtml(item.preview || "未命名 JD")}</span>` +
      `<span class="history-item-meta">${escapeHtml(item.conclusionLabel || "已分析")} · ${escapeHtml(formatHistoryTime(item.createdAt))}</span>` +
      `</button>` +
      `</li>`
    );
  }).join("");
}

function refillHistory(event) {
  const button = event.target.closest("[data-history-index]");
  if (!button) return;
  const item = HistoryManager.read()[Number(button.dataset.historyIndex)];
  if (!item || !item.jd) return;
  jdText.value = item.jd;
  clearInputError();
  showFileInputMessage("已回填历史 JD，可直接分析或继续修改。");
  jdText.focus();
}

function clearHistory() {
  HistoryManager.clear();
  renderHistory();
  showFileInputMessage("已清空这台设备上的历史 JD。", false);
}

/* ------------------------------------------------------------------ */
/*  loading / reset                                                    */
/* ------------------------------------------------------------------ */

function enterLoading() {
  clearInputError();
  mascotFrameIndex = 0;
  mascotFrame.src = MASCOT_FRAMES[mascotFrameIndex];
  startLoadingStatusLoop();
  setState("loading");
}

function resetToInput() {
  exitGraphFullscreen(false);
  if (isSampleMode) {
    window.location.assign("/");
    return;
  }
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  stopLoadingStatusLoop();
  clearInputError();
  graphCard.hidden = true;
  resultSummary.innerHTML = "";
  resultContent.innerHTML = "";
  resultExportToolbar.hidden = true;
  exportStatus.textContent = "";
  currentResult = null;
  setState("input");
}

function setGraphFullscreen(nextState) {
  if (!graphCard || graphCard.hidden || !graphFullscreenToggle) return;
  if (nextState) {
    graphCard.open = true;
    if (!graphFullscreenPlaceholder) {
      graphFullscreenParent = graphCard.parentNode;
      graphFullscreenPlaceholder = document.createComment("graph-card-fullscreen-placeholder");
      graphFullscreenParent.insertBefore(graphFullscreenPlaceholder, graphCard);
      document.body.appendChild(graphCard);
    }
  } else if (graphFullscreenPlaceholder && graphFullscreenParent) {
    graphFullscreenParent.insertBefore(graphCard, graphFullscreenPlaceholder);
    graphFullscreenPlaceholder.remove();
    graphFullscreenPlaceholder = null;
    graphFullscreenParent = null;
  }
  graphCard.classList.toggle("is-fullscreen", nextState);
  document.body.classList.toggle("graph-fullscreen-open", nextState);
  graphFullscreenToggle.setAttribute("aria-pressed", String(nextState));
  graphFullscreenToggle.textContent = nextState ? "返回结果" : "全屏查看";
  const refresh = function() {
    if (typeof window.refreshGraphLayout === "function") window.refreshGraphLayout();
  };
  window.requestAnimationFrame(function() {
    window.requestAnimationFrame(refresh);
  });
  window.setTimeout(refresh, 90);
  window.setTimeout(refresh, 260);
}

function exitGraphFullscreen(returnFocus) {
  if (!graphCard || !graphCard.classList.contains("is-fullscreen")) return;
  setGraphFullscreen(false);
  if (returnFocus && graphFullscreenToggle) graphFullscreenToggle.focus();
}

function toggleGraphFullscreen() {
  setGraphFullscreen(!graphCard.classList.contains("is-fullscreen"));
}

function startLoadingStatusLoop() {
  stopLoadingStatusLoop();
  let messageIndex = 0;
  loadingStatus.textContent = LOADING_STATUS_MESSAGES[messageIndex];
  loadingStatusTimer = window.setInterval(function() {
    messageIndex = (messageIndex + 1) % LOADING_STATUS_MESSAGES.length;
    loadingStatus.textContent = LOADING_STATUS_MESSAGES[messageIndex];
  }, 4200);
}

function stopLoadingStatusLoop() {
  if (loadingStatusTimer === null) return;
  window.clearInterval(loadingStatusTimer);
  loadingStatusTimer = null;
}

/* ------------------------------------------------------------------ */
/*  API call                                                           */
/* ------------------------------------------------------------------ */

async function callAnalyzeV4(jdTextValue) {
  abortController = new AbortController();
  const timer = setTimeout(() => abortController.abort(), API_TIMEOUT_MS);

  try {
    const resp = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jd_text: jdTextValue }),
      signal: abortController.signal,
    });

    clearTimeout(timer);

    if (!resp.ok) {
      if (resp.status === 503) {
        throw new Error("分析服务暂时不可用，请配置 API Key 后重试。");
      }
      throw new Error(`分析请求失败（${resp.status}），请稍后重试。`);
    }

    return await resp.json();
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new Error("请求超时，请稍后重试");
    }
    throw err;
  }
}

/* ------------------------------------------------------------------ */
/*  render helpers                                                     */
/* ------------------------------------------------------------------ */

function escapeHtml(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function fieldLabel(key) {
  return FIELD_LABELS[key] || key;
}

function listStyle(key) {
  for (const rule of LIST_STYLE_RULES) {
    if (rule.match.test(key)) return rule;
  }
  return DEFAULT_LIST_STYLE;
}

function severityBadge(sev) {
  const s = SEVERITY_MAP[sev] || { label: sev, cls: "badge-muted" };
  return `<span class="styled-badge ${s.cls}">${escapeHtml(s.label)}</span>`;
}

function certaintyBadge(cert) {
  const label = CERTAINTY_MAP[cert] || cert;
  const cls = cert === "explicit" ? "badge-green" : "badge-amber";
  return `<span class="styled-badge ${cls}">${escapeHtml(label)}</span>`;
}

/* ------------------------------------------------------------------ */
/*  generic structured renderer                                        */
/* ------------------------------------------------------------------ */

function renderStructured(value, key, depth, opts) {
  depth = depth || 0;
  opts = opts || {};

  /* ---- string ---- */
  if (typeof value === "string") {
    if (value.length > LONG_TEXT_THRESHOLD) return renderProse(value, key);
    return `<span class="styled-text">${escapeHtml(value)}</span>`;
  }

  /* ---- number / boolean ---- */
  if (typeof value === "number" || typeof value === "boolean") {
    return `<span class="styled-primitive">${escapeHtml(String(value))}</span>`;
  }

  /* ---- null / undefined ---- */
  if (value === null || value === undefined) {
    return `<span class="styled-empty">（暂无）</span>`;
  }

  /* ---- array ---- */
  if (Array.isArray(value)) {
    if (value.length === 0) return `<span class="styled-empty">（暂无）</span>`;
    const first = value[0];
    if (first !== null && typeof first === "object") {
      return renderCardList(value, key, depth, opts);
    }
    return renderList(value, key, opts);
  }

  /* ---- object ---- */
  if (typeof value === "object") {
    return renderObjectFields(value, key, depth, opts);
  }

  return escapeHtml(String(value));
}

/* ------------------------------------------------------------------ */
/*  prose — 长文本                                                      */
/* ------------------------------------------------------------------ */

function renderProse(text, key) {
  return (
    `<div class="styled-prose">` +
    `<p class="styled-prose-text">${escapeHtml(text)}</p>` +
    `</div>`
  );
}

/* ------------------------------------------------------------------ */
/*  list — 字符串数组                                                    */
/* ------------------------------------------------------------------ */

function renderList(items, key, opts) {
  const style = listStyle(key);
  const isNumbered = style.cls === "list-numbered";
  const light = opts.light;

  let html = `<ul class="styled-list ${style.cls}${light ? " list-light" : ""}">`;
  for (let i = 0; i < items.length; i++) {
    const icon = isNumbered ? String(i + 1) : style.icon;
    html +=
      `<li class="styled-list-item">` +
      `<span class="styled-list-icon">${icon}</span>` +
      `<span class="styled-list-text">${escapeHtml(String(items[i]))}</span>` +
      `</li>`;
  }
  html += `</ul>`;
  return html;
}

/* ------------------------------------------------------------------ */
/*  card list — 对象数组                                                 */
/* ------------------------------------------------------------------ */

function renderCardList(items, key, depth, opts) {
  let html = `<div class="styled-card-list">`;
  for (let i = 0; i < items.length; i++) {
    html += renderCard(items[i], key, depth, opts);
  }
  html += `</div>`;
  return html;
}

function renderCard(obj, parentKey, depth, opts) {
  const shape = detectCardShape(obj);

  if (shape === "risk") {
    return renderRiskCard(obj);
  }
  if (shape === "finding") {
    return renderFindingCard(obj);
  }
  if (shape === "supplement") {
    return renderSupplementCard(obj);
  }

  /* generic card — 打散为字段列表 */
  let html = `<div class="styled-card styled-card-generic">`;
  html += renderObjectFields(obj, parentKey, depth + 1, opts);
  html += `</div>`;
  return html;
}

function detectCardShape(obj) {
  if (!obj || typeof obj !== "object") return "generic";
  if ("severity" in obj && "target" in obj) return "risk";
  if ("type" in obj && "finding" in obj && "target" in obj) return "finding";
  if ("type" in obj && "suggested_action" in obj) return "supplement";
  return "generic";
}

/* --- risk card --- */

function renderRiskCard(obj) {
  const sev = obj.severity || "low";
  const sevCls = { high: "risk-high", medium: "risk-medium", low: "risk-low" }[sev] || "risk-low";
  return (
    `<div class="styled-card styled-risk-card ${sevCls}">` +
    `<div class="risk-bar"></div>` +
    `<div class="risk-body">` +
    `<div class="risk-head">` +
    severityBadge(sev) +
    `<strong class="risk-target">${escapeHtml(obj.target || "")}</strong>` +
    `</div>` +
    (obj.description ? `<p class="risk-desc">${escapeHtml(obj.description)}</p>` : "") +
    `</div>` +
    `</div>`
  );
}

/* --- finding card --- */

function renderFindingCard(obj) {
  return (
    `<div class="styled-card styled-finding-card">` +
    `<div class="finding-head">` +
    `<span class="styled-badge badge-type">${escapeHtml(fieldLabel(obj.type || ""))}</span>` +
    `<strong class="finding-target">${escapeHtml(obj.target || "")}</strong>` +
    certaintyBadge(obj.certainty || "") +
    `</div>` +
    (obj.finding ? `<p class="finding-body">${escapeHtml(obj.finding)}</p>` : "") +
    (obj.evidence && obj.evidence.length
      ? `<div class="finding-evidence">` +
        obj.evidence.map(function(e) {
          return `<span class="evidence-chip">${escapeHtml(e)}</span>`;
        }).join("") +
        `</div>`
      : "") +
    `</div>`
  );
}

/* --- supplement card --- */

function renderSupplementCard(obj) {
  return (
    `<div class="styled-card styled-supplement-card">` +
    `<div class="supplement-head">` +
    `<span class="styled-badge badge-type">${escapeHtml(fieldLabel(obj.type || ""))}</span>` +
    `<strong class="supplement-target">${escapeHtml(obj.target || "")}</strong>` +
    `</div>` +
    (obj.description ? `<p class="supplement-desc">${escapeHtml(obj.description)}</p>` : "") +
    (obj.suggested_action
      ? `<p class="supplement-action">→ ${escapeHtml(obj.suggested_action)}</p>`
      : "") +
    `</div>`
  );
}

/* ------------------------------------------------------------------ */
/*  object fields — 遍历对象键值                                          */
/* ------------------------------------------------------------------ */

function renderObjectFields(obj, parentKey, depth, opts) {
  if (depth >= 3) return renderKVTable(obj);

  const keys = Object.keys(obj);
  if (keys.length === 0) return `<span class="styled-empty">（暂无）</span>`;

  /* 小对象（≤4 个短字段）→ 属性表 */
  const allShort = keys.every(function(k) {
    const v = obj[k];
    return typeof v === "string" && v.length < 80;
  });
  if (keys.length <= 4 && allShort && depth > 0) {
    return renderKVTable(obj);
  }

  /* 一般对象 → 逐字段渲染 */
  let html = `<div class="styled-fields">`;
  for (let i = 0; i < keys.length; i++) {
    const k = keys[i];
    const v = obj[k];
    const label = fieldLabel(k);
    const body = renderStructured(v, k, depth + 1, opts);
    html +=
      `<div class="styled-field">` +
      `<span class="styled-field-label">${escapeHtml(label)}</span>` +
      `<div class="styled-field-value">${body}</div>` +
      `</div>`;
  }
  html += `</div>`;
  return html;
}

/* ------------------------------------------------------------------ */
/*  KV table — 折叠属性表（深度 ≥3 降级用）                                */
/* ------------------------------------------------------------------ */

function renderKVTable(obj) {
  const keys = Object.keys(obj);
  if (keys.length === 0) return `<span class="styled-empty">（暂无）</span>`;

  let html = `<table class="styled-kv-table">`;
  for (let i = 0; i < keys.length; i++) {
    const k = keys[i];
    const v = obj[k];
    let valStr;
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      valStr = escapeHtml(String(v));
    } else if (Array.isArray(v)) {
      valStr = v.map(function(x) { return escapeHtml(String(x)); }).join("、");
    } else if (v === null || v === undefined) {
      valStr = `<span class="styled-empty">—</span>`;
    } else {
      valStr = `<details class="kv-nested"><summary>展开</summary>${renderKVTable(v)}</details>`;
    }
    html +=
      `<tr>` +
      `<td class="kv-key">${escapeHtml(fieldLabel(k))}</td>` +
      `<td class="kv-val">${valStr}</td>` +
      `</tr>`;
  }
  html += `</table>`;
  return html;
}

/* ------------------------------------------------------------------ */
/*  section wrapper                                                     */
/* ------------------------------------------------------------------ */

const JUDGMENT_CARD_FIELDS = [
  ["core_judgment", "核心判断"],
  ["job_focus", "工作重点"],
  ["strengths", "亮点"],
  ["risks", "风险"],
  ["key_findings", "关键发现"],
  ["interview_questions", "面试要问的"],
];

function renderJudgmentCard(key, label, body) {
  const modifier = /^[a-z_]+$/.test(key) ? ` judgment-card-${key}` : "";
  return (
    `<section class="judgment-card${modifier}">` +
    `<h3 class="judgment-card-title">${escapeHtml(label)}</h3>` +
    `<div class="judgment-card-body">${body}</div>` +
    `</section>`
  );
}

function renderJudgmentFindingRows(items) {
  if (!Array.isArray(items) || items.length === 0) return `<span class="styled-empty">（暂无）</span>`;
  return (
    `<div class="judgment-finding-list">` +
    items.map(function(item) {
      const finding = item || {};
      const evidence = Array.isArray(finding.evidence) ? finding.evidence : [];
      return (
        `<article class="judgment-finding-row">` +
        `<div class="judgment-finding-head">` +
        `<span class="styled-badge badge-type">${escapeHtml(fieldLabel(finding.type || "其他"))}</span>` +
        `<strong>${escapeHtml(finding.target || "未命名对象")}</strong>` +
        certaintyBadge(finding.certainty || "") +
        `</div>` +
        (finding.finding ? `<p>${escapeHtml(finding.finding)}</p>` : `<span class="styled-empty">（暂无）</span>`) +
        (evidence.length
          ? `<div class="finding-evidence">${evidence.map(function(itemEvidence) {
            return `<span class="evidence-chip">${escapeHtml(String(itemEvidence))}</span>`;
          }).join("")}</div>`
          : "") +
        `</article>`
      );
    }).join("") +
    `</div>`
  );
}

function renderJudgmentSection(value) {
  const judgment = value && typeof value === "object" ? value : {};
  let cards = "";
  for (let index = 0; index < JUDGMENT_CARD_FIELDS.length; index++) {
    const key = JUDGMENT_CARD_FIELDS[index][0];
    const label = JUDGMENT_CARD_FIELDS[index][1];
    let body;
    if (key === "key_findings") {
      body = renderJudgmentFindingRows(judgment[key]);
    } else if (key === "core_judgment") {
      body = judgment[key] ? renderProse(String(judgment[key]), key) : `<span class="styled-empty">（暂无）</span>`;
    } else {
      body = renderStructured(judgment[key], key, 1, {});
    }
    cards += renderJudgmentCard(key, label, body);
  }

  const knownKeys = new Set(JUDGMENT_CARD_FIELDS.map(function(field) { return field[0]; }));
  Object.keys(judgment).filter(function(key) { return !knownKeys.has(key); }).forEach(function(key) {
    cards += renderJudgmentCard(key, fieldLabel(key), renderStructured(judgment[key], key, 1, {}));
  });

  return (
    `<details class="styled-section judgment-section result-disclosure" open>` +
    `<summary class="styled-section-title result-disclosure-summary">岗位判断</summary>` +
    `<div class="result-disclosure-body"><div class="judgment-card-list">${cards}</div></div>` +
    `</details>`
  );
}

function renderSectionStyled(key, value) {
  if (key === "jd_core_judgment") return renderJudgmentSection(value);
  const label = SECTION_LABELS[key] || key;
  const body = renderStructured(value, key, 0, {});
  return (
    `<details class="styled-section section-${escapeHtml(key)} result-disclosure" open>` +
    `<summary class="styled-section-title result-disclosure-summary">${escapeHtml(label)}</summary>` +
    `<div class="result-disclosure-body">${body}</div>` +
    `</details>`
  );
}

/* ------------------------------------------------------------------ */
/*  summary / narration                                                */
/* ------------------------------------------------------------------ */

function renderSummary(data) {
  const n = data.narration;
  if (!n) return "";

  const label = n.conclusion_label || "";
  const summary = n.summary || "";
  const labelClass = conclusionLabelClass(label);
  const metrics = summaryMetrics(data);

  return (
    `<div class="result-summary ${labelClass}">` +
    (label ? `<span class="result-label"><span aria-hidden="true">🍉</span>${escapeHtml(label)}</span>` : "") +
    renderSummaryParagraphs(summary) +
    `<div class="summary-metrics" aria-label="分析关键指标">` +
    metrics.map(function(metric) {
      return `<span class="summary-metric"><strong>${metric.value}</strong>${metric.label}</span>`;
    }).join("") +
    `</div>` +
    `</div>`
  );
}

function renderSummaryParagraphs(summary) {
  if (!summary) return "";
  const paragraphs = summary
    .split(/\n\s*\n/)
    .map(function(paragraph) { return paragraph.trim(); })
    .filter(Boolean);
  return (
    `<div class="result-summary-text">` +
    paragraphs.map(function(paragraph) {
      return `<p class="result-summary-paragraph">${escapeHtml(paragraph)}</p>`;
    }).join("") +
    `</div>`
  );
}

function conclusionLabelClass(label) {
  if (label.includes("保熟")) return "conclusion-ripe";
  if (label.includes("生瓜")) return "conclusion-unripe";
  if (label.includes("秤")) return "conclusion-suspicious";
  if (label.includes("萨日朗")) return "conclusion-sarilang";
  return "conclusion-default";
}

function collectionLength(value) {
  return Array.isArray(value) ? value.length : 0;
}

function summaryMetrics(data) {
  const modeling = data.element_modeling || {};
  const quality = data.quality_check || {};
  const judgment = data.jd_core_judgment || {};
  return [
    { label: "价值流", value: collectionLength(modeling.value_streams) },
    { label: "风险点", value: collectionLength(quality.risk_points) },
    { label: "核心发现", value: collectionLength(judgment.key_findings) },
  ];
}

function errorPresentation(message) {
  if (/超时|timeout/i.test(message)) {
    return { emoji: "⏳", title: "这瓜有点难劈", detail: "分析花的时间比预期更久，换个网络或稍后再试。" };
  }
  if (/服务暂时不可用|503|API Key/i.test(message)) {
    return { emoji: "🛠️", title: "劈瓜摊暂时收工", detail: "分析服务现在不可用，稍后恢复后可直接重试。" };
  }
  if (/网络|请求失败|fetch/i.test(message)) {
    return { emoji: "📡", title: "劈瓜信号断了", detail: "检查网络连接后，再把这只瓜递过来。" };
  }
  return { emoji: "🍉", title: "这瓜没劈开", detail: "出了点意外，重新试一次通常就好。" };
}

function renderError(message) {
  const presentation = errorPresentation(message);
  return (
    `<div class="result-error" role="alert">` +
    `<div class="error-illustration" aria-hidden="true">${presentation.emoji}</div>` +
    `<h3>${escapeHtml(presentation.title)}</h3>` +
    `<p class="error-detail">${escapeHtml(presentation.detail)}</p>` +
    `<p class="error-message">${escapeHtml(message)}</p>` +
    `<button class="quiet-button retry-button" type="button" id="retry-analysis-button">重新分析</button>` +
    `</div>`
  );
}

/* ------------------------------------------------------------------ */
/*  export helpers                                                     */
/* ------------------------------------------------------------------ */

function exportFileName(result, extension) {
  const traceId = result && result._meta && result._meta.trace_id
    ? result._meta.trace_id
    : "analysis";
  return `pigua-${traceId}.${extension}`;
}

function downloadBlob(content, type, filename) {
  const blob = new Blob([content], { type: type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadJson(result) {
  downloadBlob(
    JSON.stringify(result, null, 2),
    "application/json;charset=utf-8",
    exportFileName(result, "json")
  );
}

function markdownBlock(title, value) {
  if (value === undefined) return "";
  if (typeof value === "string") {
    return `## ${title}\n\n${value}\n\n`;
  }
  return `## ${title}\n\n\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\`\n\n`;
}

function resultToMarkdown(result) {
  const traceId = result && result._meta ? result._meta.trace_id : "";
  let markdown = "# 劈瓜 JD 分析结果\n\n";
  if (traceId) markdown += `- Trace ID: \`${traceId}\`\n`;
  if (result && result._meta && result._meta.timing) {
    markdown += `- Workflow total: \`${result._meta.timing.workflow_total_ms || 0}ms\`\n`;
  }
  markdown += "\n";

  if (result && result.narration) {
    markdown += markdownBlock("口语化总结", result.narration.summary || result.narration);
  }
  for (let i = 0; i < SECTION_ORDER.length; i++) {
    const key = SECTION_ORDER[i];
    if (key === "narration") continue;
    if (result[key] !== undefined) {
      markdown += markdownBlock(SECTION_LABELS[key] || key, result[key]);
    }
  }
  return markdown;
}

function downloadMarkdown(result) {
  downloadBlob(
    resultToMarkdown(result),
    "text/markdown;charset=utf-8",
    exportFileName(result, "md")
  );
}

async function copyTraceLink(result) {
  const traceId = result && result._meta && result._meta.trace_id;
  if (!traceId) {
    exportStatus.textContent = "没有 trace_id";
    return;
  }
  await navigator.clipboard.writeText(traceId);
  exportStatus.textContent = "已复制 trace_id";
}

/* ------------------------------------------------------------------ */
/*  main render                                                        */
/* ------------------------------------------------------------------ */

function renderResult(data, options) {
  const renderOptions = options || {};
  stopLoadingStatusLoop();
  exitGraphFullscreen(false);
  currentResult = data;
  if (renderOptions.saveHistory !== false) {
    HistoryManager.save(jdText.value.trim(), data);
    renderHistory();
  }
  resultExportToolbar.hidden = false;
  exportStatus.textContent = "";
  resultSummary.innerHTML = renderSummary(data);

  let html = "";
  for (let i = 0; i < SECTION_ORDER.length; i++) {
    const key = SECTION_ORDER[i];
    if (key === "narration") continue;
    if (key === "element_modeling") continue;
    if (data[key] !== undefined) {
      html += renderSectionStyled(key, data[key]);
    }
  }

  resultContent.innerHTML = html;

  /* 图谱渲染 */
  if (data.element_modeling) {
    graphCard.hidden = false;
    renderGraph(data.element_modeling);
  } else {
    graphCard.hidden = true;
  }

  setState("result");
}

function renderErrorMessage(message) {
  stopLoadingStatusLoop();
  exitGraphFullscreen(false);
  currentResult = null;
  resultExportToolbar.hidden = true;
  exportStatus.textContent = "";
  resultSummary.innerHTML = "";
  graphCard.hidden = true;
  resultContent.innerHTML = renderError(message);
  setState("result");
  document.getElementById("retry-analysis-button").addEventListener("click", handleRetry);
}

/* ------------------------------------------------------------------ */
/*  form submit                                                        */
/* ------------------------------------------------------------------ */

async function handleSubmit(event) {
  event.preventDefault();
  if (isSampleMode) return;

  if (!hasInputs()) {
    showInputError();
    return;
  }

  enterLoading();

  try {
    const data = await callAnalyzeV4(jdText.value.trim());
    renderResult(data);
  } catch (err) {
    renderErrorMessage(err.message || "未知错误，请稍后重试");
  }
}

function handleRetry() {
  if (isSampleMode) {
    loadFrontendSample();
    return;
  }
  form.requestSubmit();
}

async function loadFrontendSample() {
  document.title = "劈瓜 · 前端验收样例";
  sampleBanner.hidden = false;
  sampleBannerDetail.textContent = "正在加载冻结结果，不调用 LLM。";
  try {
    const response = await fetch(SAMPLE_FIXTURE_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`样例 fixture 加载失败（${response.status}）`);
    const data = await response.json();
    const traceId = data && data._meta ? data._meta.trace_id : "未标注 trace";
    sampleBannerDetail.textContent = `来源 trace：${traceId} · 使用生产渲染器 · 不调用 LLM。`;
    resultResetButton.textContent = "返回分析首页";
    renderResult(data, { saveHistory: false });
  } catch (error) {
    sampleBannerDetail.textContent = "冻结样例加载失败，请检查 fixture 是否完整。";
    renderErrorMessage(error.message || "冻结样例加载失败");
  }
}

function showFileInputMessage(message, isError) {
  formError.textContent = message;
  formError.classList.toggle("is-error", Boolean(isError));
  formError.classList.toggle("is-success", !isError);
  formError.hidden = false;
}

function validateTextFile(file) {
  const extension = file.name.split(".").pop().toLowerCase();
  if (!['txt', 'md', 'docx'].includes(extension)) {
    throw new Error("仅支持 .txt / .md / .docx 文件");
  }
  if (file.size > 500 * 1024) {
    throw new Error("文件不能超过 500KB");
  }
  return extension;
}

async function fillFromTextFile(file) {
  try {
    const extension = validateTextFile(file);
    let content;
    if (extension === "docx") {
      if (!window.mammoth) throw new Error("DOCX 读取组件未加载，请刷新后重试");
      const result = await window.mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() });
      content = result.value;
    } else {
      content = await file.text();
    }
    if (!content.trim()) throw new Error("文件中没有可读取的文本");
    jdText.value = content.trim();
    clearInputError();
    showFileInputMessage(`已填入：${file.name}`);
    jdText.focus();
  } catch (err) {
    showFileInputMessage(err.message || "文件读取失败", true);
  }
}

function handleDrop(event) {
  event.preventDefault();
  jdText.classList.remove("is-dragging");
  const file = event.dataTransfer.files && event.dataTransfer.files[0];
  if (file) fillFromTextFile(file);
}

function handlePaste(event) {
  const items = event.clipboardData && event.clipboardData.items;
  if (!items) return;
  for (let i = 0; i < items.length; i++) {
    if (items[i].kind === "file") {
      event.preventDefault();
      fillFromTextFile(items[i].getAsFile());
      return;
    }
  }
}

function handleSampleJd(event) {
  const sample = SAMPLE_JDS[event.currentTarget.dataset.sampleJd];
  if (!sample) return;
  jdText.value = sample;
  clearInputError();
  showFileInputMessage("已填入示例，可直接分析或继续修改。");
  jdText.classList.remove("is-sample-filled");
  window.requestAnimationFrame(function() { jdText.classList.add("is-sample-filled"); });
  jdText.focus();
}

function showMascotFallback() {
  mascotFrame.hidden = true;
  mascotPlaceholder.hidden = false;
}

function startMascotLoop() {
  if (!mascotFrame || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  window.setInterval(() => {
    mascotFrameIndex = (mascotFrameIndex + 1) % MASCOT_FRAMES.length;
    mascotFrame.src = MASCOT_FRAMES[mascotFrameIndex];
  }, MASCOT_FRAME_MS);
}

function handleDownloadJson() {
  if (!currentResult) return;
  downloadJson(currentResult);
  exportStatus.textContent = "JSON 已下载";
}

function handleDownloadMarkdown() {
  if (!currentResult) return;
  downloadMarkdown(currentResult);
  exportStatus.textContent = "Markdown 已下载";
}

function handleCopyTrace() {
  if (!currentResult) return;
  copyTraceLink(currentResult).catch(function() {
    exportStatus.textContent = "复制失败";
  });
}

/* ------------------------------------------------------------------ */
/*  init                                                               */
/* ------------------------------------------------------------------ */

form.addEventListener("submit", handleSubmit);
resultResetButton.addEventListener("click", resetToInput);
downloadJsonButton.addEventListener("click", handleDownloadJson);
downloadMarkdownButton.addEventListener("click", handleDownloadMarkdown);
copyTraceButton.addEventListener("click", handleCopyTrace);
graphFullscreenToggle.addEventListener("click", function(event) {
  event.preventDefault();
  event.stopPropagation();
  toggleGraphFullscreen();
});
document.addEventListener("keydown", function(event) {
  if (event.key === "Escape") exitGraphFullscreen(true);
});
jdText.addEventListener("input", clearInputError);
jdText.addEventListener("animationend", function(event) {
  if (event.animationName === "sampleFilled") jdText.classList.remove("is-sample-filled");
});
jdText.addEventListener("dragover", function(event) {
  event.preventDefault();
  jdText.classList.add("is-dragging");
});
jdText.addEventListener("dragleave", function() { jdText.classList.remove("is-dragging"); });
jdText.addEventListener("drop", handleDrop);
jdText.addEventListener("paste", handlePaste);
document.querySelectorAll("[data-sample-jd]").forEach(function(chip) {
  chip.addEventListener("click", handleSampleJd);
});
historyList.addEventListener("click", refillHistory);
historyClearButton.addEventListener("click", clearHistory);
mascotFrame.addEventListener("error", showMascotFallback);

if (isSampleMode) {
  loadFrontendSample();
} else {
  startMascotLoop();
  renderHistory();
  setState("input");
}
