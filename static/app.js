/*
 * 目的：app.js 旧版前端脚本。
 * 定义：static/app.js 是历史预览页使用的浏览器端脚本。
 * 范围包括：
 * - 旧版页面交互和兼容展示逻辑。
 * 范围不包括：
 * - 不作为当前 design-preview-02 主联调入口。
 * 使用与修改规则：
 * - 新前端行为优先修改 design-preview-02.js。
 */

const form = document.getElementById("analyze-form");
const loadDemoButton = document.getElementById("load-demo");
const submitButton = document.getElementById("submit-button");
const statusLine = document.getElementById("status-line");
const recommendationBadge = document.getElementById("recommendation-badge");
const workflowVersionBadge = document.getElementById("workflow-version");
const rawOutput = document.getElementById("raw-output");

function setStatus(message) {
  statusLine.textContent = message;
}

function setRecommendation(value) {
  recommendationBadge.textContent = value || "等待分析";
  recommendationBadge.className = "result-badge";

  if (value === "冲") {
    recommendationBadge.style.background = "rgba(109, 148, 100, 0.16)";
    recommendationBadge.style.color = "#456449";
  } else if (value === "可投") {
    recommendationBadge.style.background = "rgba(146, 171, 118, 0.18)";
    recommendationBadge.style.color = "#5a7047";
  } else if (value === "谨慎") {
    recommendationBadge.style.background = "rgba(201, 125, 82, 0.16)";
    recommendationBadge.style.color = "#9d603d";
  } else if (value === "避开") {
    recommendationBadge.style.background = "rgba(164, 94, 94, 0.14)";
    recommendationBadge.style.color = "#8d4747";
  } else {
    recommendationBadge.classList.add("idle");
  }
}

function setVersionBadge(version) {
  if (!workflowVersionBadge) return;
  workflowVersionBadge.textContent = version || "—";
  workflowVersionBadge.className = "version-badge";
  if (version === "v3" || version === "v4") {
    workflowVersionBadge.style.background = "rgba(100, 130, 180, 0.16)";
    workflowVersionBadge.style.color = "#3d5a80";
  } else if (version === "v2") {
    workflowVersionBadge.style.background = "rgba(150, 150, 150, 0.16)";
    workflowVersionBadge.style.color = "#666";
  } else {
    workflowVersionBadge.style.background = "rgba(106, 98, 87, 0.12)";
    workflowVersionBadge.style.color = "var(--muted)";
  }
}

async function loadDemo() {
  setStatus("正在加载示例…");
  const response = await fetch("/demo");
  const data = await response.json();
  document.getElementById("jd-text").value = data.jd_text;
  document.getElementById("resume-text").value = data.resume_text;
  setStatus("示例已填充，可以直接开始分析。");
}

async function analyzeWith(endpoint, payload) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorText = await response.text().catch(() => "分析失败");
    const err = new Error(errorText);
    err.status = response.status;
    throw err;
  }
  return response.json();
}

async function handleSubmit(event) {
  event.preventDefault();

  const payload = {
    jd_text: document.getElementById("jd-text").value.trim(),
    resume_text: document.getElementById("resume-text").value.trim(),
  };

  submitButton.disabled = true;
  setStatus("正在分析岗位和你的匹配情况…");
  setRecommendation("分析中");
  setVersionBadge("—");
  rawOutput.textContent = "分析中…";

  try {
    let result;
    let version = "v4";
    try {
      result = await analyzeWith("/analyze/v4", payload);
    } catch (err) {
      if (err.status === 503) {
        setStatus("v4 需要 LLM key，正在回退到 v2…");
        result = await analyzeWith("/analyze", payload);
        version = "v2";
      } else {
        throw err;
      }
    }

    version = result.meta?.version || version;
    setVersionBadge(version);
    setRecommendation(result.recommendation);
    rawOutput.textContent = JSON.stringify(result, null, 2);
    setStatus("分析完成。可以继续修改内容再分析一次。");
  } catch (error) {
    setRecommendation("等待分析");
    setVersionBadge("—");
    rawOutput.textContent = error.message;
    setStatus("这次没跑通，先检查文本长度和格式。");
  } finally {
    submitButton.disabled = false;
  }
}

loadDemoButton.addEventListener("click", loadDemo);
form.addEventListener("submit", handleSubmit);
