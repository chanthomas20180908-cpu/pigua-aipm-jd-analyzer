/*
 * 目的：design-preview.js 旧版前端脚本。
 * 定义：static/design-preview.js 是历史预览页使用的浏览器端脚本。
 * 范围包括：
 * - 旧版页面交互和兼容展示逻辑。
 * 范围不包括：
 * - 不作为当前 design-preview-02 主联调入口。
 * 使用与修改规则：
 * - 新前端行为优先修改 design-preview-02.js。
 */

const MOCK_RESULT_TEXT = "可投，但先别急，先把这段经历讲得更像你真的做过。";
const LOADING_DURATION_MS = 1800;

const shell = document.getElementById("preview-shell");
const form = document.getElementById("preview-form");
const analyzeButton = document.getElementById("analyze-button");
const statusLine = document.getElementById("status-line");
const heroNote = document.getElementById("hero-note");
const bubbleText = document.getElementById("bubble-text");
const stateChip = document.getElementById("state-chip");
const jdText = document.getElementById("jd-text");
const resumeText = document.getElementById("resume-text");
const loadingPanel = document.getElementById("loading-panel");
const collapsedPanel = document.getElementById("collapsed-panel");
const collapsedBody = document.getElementById("collapsed-body");
const collapsedJd = document.getElementById("collapsed-jd");
const collapsedResume = document.getElementById("collapsed-resume");
const toggleInputPreview = document.getElementById("toggle-input-preview");
const backToInput = document.getElementById("back-to-input");
const resultBackButton = document.getElementById("result-back-button");
const resultStage = document.getElementById("result-stage");
const resultText = document.getElementById("result-text");
const loadingCopy = document.getElementById("loading-copy");

let loadingTimer = null;

function setState(nextState) {
  shell.dataset.state = nextState;
  shell.classList.remove("state-input", "state-loading", "state-result");
  shell.classList.add(`state-${nextState}`);

  const isLoading = nextState === "loading";
  const isResult = nextState === "result";

  loadingPanel.hidden = !isLoading;
  collapsedPanel.hidden = !isResult;
  resultStage.hidden = !isResult;
}

function validateInputs() {
  return jdText.value.trim().length > 0 && resumeText.value.trim().length > 0;
}

function setInputMode() {
  clearTimeout(loadingTimer);
  analyzeButton.disabled = false;
  collapsedBody.hidden = true;
  toggleInputPreview.textContent = "展开查看";
  stateChip.textContent = "输入中";
  statusLine.textContent = "把两段材料贴进来，然后开始判断。";
  heroNote.textContent = "输入 JD 和简历后，页面会切到审稿状态，再把结果放到中央。";
  bubbleText.textContent = "先把材料给我，我先看，不急着下结论。";
  setState("input");
}

function setLoadingMode() {
  analyzeButton.disabled = true;
  stateChip.textContent = "审稿中";
  statusLine.textContent = "正在对照 JD 和简历。";
  heroNote.textContent = "输入区暂时退后，卡皮巴拉正在整理重点，准备给出一句判断。";
  bubbleText.textContent = "我先划重点，你先别催。";
  loadingCopy.textContent = "正在对照 JD 和简历，把不该忽略的地方圈出来。";
  setState("loading");
}

function setResultMode() {
  analyzeButton.disabled = false;
  collapsedJd.textContent = jdText.value.trim();
  collapsedResume.textContent = resumeText.value.trim();
  resultText.textContent = MOCK_RESULT_TEXT;
  stateChip.textContent = "已完成";
  heroNote.textContent = "输入内容已经收起，页面现在只保留结论焦点。要修改材料，可以回到输入态重来一次。";
  bubbleText.textContent = "我看完了，结论放到中间给你。";
  setState("result");
}

function handleSubmit(event) {
  event.preventDefault();

  if (!validateInputs()) {
    statusLine.textContent = "两个输入都要先放内容。";
    bubbleText.textContent = "材料没放全，我还没法开始看。";
    return;
  }

  setLoadingMode();
  loadingTimer = window.setTimeout(() => {
    setResultMode();
  }, LOADING_DURATION_MS);
}

function handleTogglePreview() {
  const willExpand = collapsedBody.hidden;
  collapsedBody.hidden = !willExpand;
  toggleInputPreview.textContent = willExpand ? "收起查看" : "展开查看";
}

form.addEventListener("submit", handleSubmit);
backToInput.addEventListener("click", setInputMode);
resultBackButton.addEventListener("click", setInputMode);
toggleInputPreview.addEventListener("click", handleTogglePreview);

setInputMode();
