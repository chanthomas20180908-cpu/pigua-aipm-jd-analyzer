"""目的：FastAPI 服务入口。

定义：后端 HTTP API 的应用初始化、静态资源挂载和路由定义文件。

范围包括：
- 静态页面路由、前端验收样例、favicon、404/503 品牌错误页、健康检查、demo、v2/v3 兼容接口和 v4 主接口。

范围不包括：
- 不写具体分析逻辑、prompt 或前端渲染逻辑。

使用与修改规则：
- 新增接口时保持请求/响应模型清晰，并优先调用 workflows 层。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.llm_client import LLMEnhancementError, llm_is_configured
from app.workflows.analyze_job_fit import run as analyze_job_fit_v2
from app.workflows.analyze_job_fit_v3 import run as analyze_job_fit_v3
from app.workflows.analyze_jd_v4 import run as analyze_jd_v4


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
ERROR_PAGE = STATIC_DIR / "error.html"
FAVICON_FILE = STATIC_DIR / "assets" / "favicon" / "favicon.png"

app = FastAPI(title="AI PM Job Tool MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def error_page(status_code: int, message: str) -> HTMLResponse:
    html = ERROR_PAGE.read_text(encoding="utf-8")
    html = html.replace("__ERROR_STATUS__", str(status_code))
    html = html.replace("__ERROR_MESSAGE__", message)
    return HTMLResponse(html, status_code=status_code)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
    return error_page(404, "这个页面不存在，先回到分析入口重新开始。")


@app.exception_handler(503)
async def service_unavailable_handler(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
    message = str(exc.detail) if getattr(exc, "detail", None) else "分析服务暂时不可用。"
    return error_page(503, message)


class AnalyzeRequest(BaseModel):
    jd_text: str = Field(min_length=30)
    resume_text: str = Field(min_length=30)
    user_level: Literal["新人", "转岗PM", "有经验PM", "有AI项目经验"] | None = None
    goal: Literal["求稳", "冲高薪", "转AI", "找长期主线"] | None = None


class AnalyzeRequestV3(BaseModel):
    jd_text: str = Field(min_length=30)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "design-preview-02.html")


@app.get("/sample")
def frontend_sample() -> FileResponse:
    """Serve the production renderer in deterministic, no-index sample mode."""
    return FileResponse(
        STATIC_DIR / "design-preview-02.html",
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(FAVICON_FILE, media_type="image/png")


@app.head("/favicon.ico")
def favicon_head() -> FileResponse:
    return FileResponse(FAVICON_FILE, media_type="image/png")


@app.get("/about")
def about() -> FileResponse:
    return FileResponse(STATIC_DIR / "about.html")


@app.get("/meta-model")
def meta_model() -> FileResponse:
    return FileResponse(STATIC_DIR / "meta-model.html")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "llm_configured": llm_is_configured()}


@app.get("/demo")
def demo() -> dict:
    return {
        "jd_text": (
            "负责 AI Agent 产品规划与落地，围绕企业知识库、工作流自动化和智能助手场景，"
            "完成需求分析、Prompt 设计、效果评估和跨团队推进，对用户体验和业务指标负责。"
        ),
        "resume_text": (
            "3 年产品经理经验，负责 B 端协作工具产品规划与需求分析，推动研发、设计、运营协作上线。"
            "做过知识库问答和自动化工作流原型，能使用 API 和 SQL 进行基础分析，曾将流程效率提升 18%。"
        ),
    }


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    result = analyze_job_fit_v2(
        jd_text=payload.jd_text,
        resume_text=payload.resume_text,
    )
    if "llm" not in result.get("meta", {}):
        result["meta"]["llm"] = {
            "used": False,
            "provider": "rule-fallback",
            "model": None,
        }
    if not llm_is_configured():
        result["meta"]["llm"]["used"] = False
    return result


@app.post("/analyze/v3")
def analyze_v3(payload: AnalyzeRequestV3) -> dict:
    if not llm_is_configured():
        raise HTTPException(
            status_code=503,
            detail="v3 workflow requires DASHSCOPE_API_KEY or OPENAI_API_KEY.",
        )
    try:
        return analyze_job_fit_v3(
            jd_text=payload.jd_text,
        )
    except LLMEnhancementError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/analyze/v4")
def analyze_v4(payload: AnalyzeRequestV3) -> dict:
    if not llm_is_configured():
        raise HTTPException(
            status_code=503,
            detail="v4 workflow requires DASHSCOPE_API_KEY or OPENAI_API_KEY.",
        )
    try:
        return analyze_jd_v4(
            jd_text=payload.jd_text,
        )
    except LLMEnhancementError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
