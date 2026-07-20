/*
 * 目的：design-preview-01.js 旧版前端脚本。
 * 定义：static/design-preview-01.js 是历史预览页使用的浏览器端脚本。
 * 范围包括：
 * - 旧版页面交互和兼容展示逻辑。
 * 范围不包括：
 * - 不作为当前 design-preview-02 主联调入口。
 * 使用与修改规则：
 * - 新前端行为优先修改 design-preview-02.js。
 */

const LOADING_DURATION_MS = 6200;
const MASCOT_FRAME_MS = 2000;
const MASCOT_FRAMES = [
  "/static/assets/pigua/frame-01.png",
  "/static/assets/pigua/frame-02.png",
  "/static/assets/pigua/frame-03.png",
  "/static/assets/pigua/frame-04.png",
  "/static/assets/pigua/frame-05.png",
];

const page = document.getElementById("preview-page");
const form = document.getElementById("preview-form");
const jdText = document.getElementById("jd-text");
const formError = document.getElementById("form-error");
const inputView = document.getElementById("input-view");
const loadingView = document.getElementById("loading-view");
const resultView = document.getElementById("result-view");
const materialSummary = document.getElementById("material-summary");
const materialDetail = document.getElementById("material-detail");
const jdPreview = document.getElementById("jd-preview");
const toggleMaterials = document.getElementById("toggle-materials");
const resetButton = document.getElementById("reset-button");
const resultResetButton = document.getElementById("result-reset-button");
const mascotFrame = document.getElementById("mascot-frame");
const mascotPlaceholder = document.getElementById("mascot-placeholder");
const steps = Array.from(document.querySelectorAll(".step"));

let loadingTimer = null;
let mascotFrameIndex = 0;

function hasInputs() {
  return jdText.value.trim().length > 0;
}

function setActiveStep(nextState) {
  if (steps.length === 0) {
    return;
  }

  steps.forEach((step) => {
    step.classList.toggle("is-active", step.dataset.step === nextState);
  });
}

function setState(nextState) {
  page.dataset.state = nextState;
  setActiveStep(nextState);

  inputView.hidden = nextState !== "input";
  loadingView.hidden = nextState !== "loading";
  resultView.hidden = nextState !== "result";
  materialSummary.hidden = nextState === "input";

  if (nextState !== "result") {
    materialDetail.hidden = true;
    toggleMaterials.textContent = "展开查看";
  }
}

function syncMaterialPreview() {
  jdPreview.textContent = jdText.value.trim();
}

function showInputError() {
  formError.hidden = false;
}

function clearInputError() {
  formError.hidden = true;
}

function enterLoading() {
  syncMaterialPreview();
  clearInputError();
  mascotFrameIndex = 0;
  mascotFrame.src = MASCOT_FRAMES[mascotFrameIndex];
  setState("loading");

  clearTimeout(loadingTimer);
  loadingTimer = window.setTimeout(() => {
    setState("result");
  }, LOADING_DURATION_MS);
}

function resetToInput() {
  clearTimeout(loadingTimer);
  clearInputError();
  setState("input");
}

function handleSubmit(event) {
  event.preventDefault();

  if (!hasInputs()) {
    showInputError();
    return;
  }

  enterLoading();
}

function handleToggleMaterials() {
  const shouldShow = materialDetail.hidden;
  materialDetail.hidden = !shouldShow;
  toggleMaterials.textContent = shouldShow ? "收起查看" : "展开查看";
}

function showMascotFallback() {
  mascotFrame.hidden = true;
  mascotPlaceholder.hidden = false;
}

function startMascotLoop() {
  if (!mascotFrame) {
    return;
  }

  window.setInterval(() => {
    mascotFrameIndex = (mascotFrameIndex + 1) % MASCOT_FRAMES.length;
    mascotFrame.src = MASCOT_FRAMES[mascotFrameIndex];
  }, MASCOT_FRAME_MS);
}

form.addEventListener("submit", handleSubmit);
toggleMaterials.addEventListener("click", handleToggleMaterials);
resetButton.addEventListener("click", resetToInput);
resultResetButton.addEventListener("click", resetToInput);
jdText.addEventListener("input", clearInputError);
mascotFrame.addEventListener("error", showMascotFallback);

startMascotLoop();
setState("input");
