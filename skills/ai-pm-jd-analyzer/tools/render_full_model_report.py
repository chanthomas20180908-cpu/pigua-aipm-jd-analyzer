#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""目的：把完整 AI PM JD 元模型报告生成离线、可追溯的可视化 HTML。

定义：skill 随附的纯本地渲染器，消费 Markdown 报告中唯一的 JSON 附录。

范围包括：提取摘要和模型、校验引用、生成无外部依赖的交互式报告页面。

范围不包括：不调用网络、模型、服务或读取原始 JD、prompt、trace 和日志。

使用与修改规则：输出路径必须显式指定；默认不覆盖文件；模型契约变更时同步更新校验、页面和测试。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "ai_pm_jd_full_model/v1"
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "source",
    "company_context",
    "job_profile",
    "value_streams",
    "work_items",
    "roles",
    "responsibility_assignments",
    "business_entities",
    "entity_relationships",
    "business_capabilities",
    "capability_relationships",
    "qualification_requirements",
    "work_environment",
    "compensation_benefits",
    "risks",
    "uncertainties",
    "judgment",
}
MODEL_HEADING = "结构化模型 JSON"


class ReportRenderError(ValueError):
    """Raised when a report cannot safely become a visual report."""


@dataclass(frozen=True)
class ReportPayload:
    """The small, source-traceable payload embedded into the standalone report."""

    title: str
    summary_paragraphs: tuple[str, ...]
    model: dict[str, Any]


def _require_list(model: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = model.get(key)
    if not isinstance(value, list):
        raise ReportRenderError(f"{key} 必须是数组")
    if not all(isinstance(item, dict) for item in value):
        raise ReportRenderError(f"{key} 只能包含对象")
    return value


def _index(items: Iterable[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ReportRenderError(f"{label} 含有缺少 id 的项目")
        if item_id in index:
            raise ReportRenderError(f"{label} 含有重复 id：{item_id}")
        index[item_id] = item
    return index


def _check_reference(value: Any, index: dict[str, Any], label: str) -> None:
    if not isinstance(value, str) or value not in index:
        raise ReportRenderError(f"{label} 引用了不存在的 id：{value!r}")


def validate_model(model: dict[str, Any]) -> None:
    """Validate the renderer-critical subset of the full-model schema fail-closed."""
    if not isinstance(model, dict):
        raise ReportRenderError("JSON 附录必须是对象")
    if model.get("schema_version") != SCHEMA_VERSION:
        raise ReportRenderError(
            f"不支持的 schema_version：{model.get('schema_version')!r}；需要 {SCHEMA_VERSION}"
        )
    missing = REQUIRED_TOP_LEVEL - set(model)
    if missing:
        raise ReportRenderError(f"JSON 附录缺少顶层字段：{', '.join(sorted(missing))}")

    streams = _index(_require_list(model, "value_streams"), "value_streams")
    work_items = _index(_require_list(model, "work_items"), "work_items")
    roles = _index(_require_list(model, "roles"), "roles")
    entities = _index(_require_list(model, "business_entities"), "business_entities")
    capabilities = _index(_require_list(model, "business_capabilities"), "business_capabilities")
    requirements = _index(_require_list(model, "qualification_requirements"), "qualification_requirements")
    _index(_require_list(model, "risks"), "risks")
    _index(_require_list(model, "uncertainties"), "uncertainties")

    for item in work_items.values():
        _check_reference(item.get("value_stream_id"), streams, "工作事项 value_stream_id")
        operations = item.get("entity_operations")
        capability_ids = item.get("capability_ids")
        if not isinstance(operations, list) or not isinstance(capability_ids, list):
            raise ReportRenderError(f"工作事项 {item['id']} 缺少实体操作或能力列表")
        for operation in operations:
            if not isinstance(operation, dict):
                raise ReportRenderError(f"工作事项 {item['id']} 的实体操作不是对象")
            _check_reference(operation.get("entity_id"), entities, "实体操作 entity_id")
        for capability_id in capability_ids:
            _check_reference(capability_id, capabilities, "工作事项 capability_ids")

    for entity in entities.values():
        _check_reference(entity.get("primary_capability_id"), capabilities, "实体 primary_capability_id")

    for assignment in _require_list(model, "responsibility_assignments"):
        _check_reference(assignment.get("role_id"), roles, "责任分配 role_id")
        _check_reference(assignment.get("work_item_id"), work_items, "责任分配 work_item_id")

    for relation in _require_list(model, "entity_relationships"):
        _check_reference(relation.get("source_id"), entities, "实体关系 source_id")
        _check_reference(relation.get("target_id"), entities, "实体关系 target_id")

    for capability in capabilities.values():
        supported = capability.get("supported_work_item_ids", [])
        if not isinstance(supported, list):
            raise ReportRenderError(f"能力 {capability['id']} 的 supported_work_item_ids 必须是数组")
        for work_item_id in supported:
            _check_reference(work_item_id, work_items, "能力 supported_work_item_ids")

    for relation in _require_list(model, "capability_relationships"):
        _check_reference(relation.get("source_id"), capabilities, "能力关系 source_id")
        _check_reference(relation.get("target_id"), capabilities, "能力关系 target_id")

    known_targets = set(streams) | set(work_items) | set(roles) | set(entities) | set(capabilities)
    for requirement in requirements.values():
        targets = requirement.get("mapping_target_ids", [])
        if not isinstance(targets, list):
            raise ReportRenderError(f"要求 {requirement['id']} 的 mapping_target_ids 必须是数组")
        for target_id in targets:
            _check_reference(target_id, known_targets, "要求 mapping_target_ids")


def _extract_title_and_summary(markdown: str) -> tuple[str, tuple[str, ...]]:
    title_match = re.search(r"^#\s+(.+?)\s*$", markdown, re.MULTILINE)
    if not title_match:
        raise ReportRenderError("报告缺少一级标题")
    title = title_match.group(1).strip()
    after_title = markdown[title_match.end() :]
    first_section = re.search(r"^##\s+", after_title, re.MULTILINE)
    intro = after_title[: first_section.start()] if first_section else after_title
    paragraphs = tuple(
        re.sub(r"\s+", " ", paragraph).strip()
        for paragraph in re.split(r"\n\s*\n", intro)
        if paragraph.strip() and not paragraph.lstrip().startswith("<!--")
    )
    if not paragraphs:
        raise ReportRenderError("报告标题后缺少结论摘要")
    return title, paragraphs


def extract_report_payload(markdown: str) -> ReportPayload:
    """Extract one full-model JSON appendix and the report's short introduction."""
    title, summary_paragraphs = _extract_title_and_summary(markdown)
    heading = re.search(rf"^##\s+{re.escape(MODEL_HEADING)}\s*$", markdown, re.MULTILINE)
    if not heading:
        raise ReportRenderError(f"缺少“{MODEL_HEADING}”章节")
    tail = markdown[heading.end() :]
    fences = re.findall(r"^```json\s*\n(.*?)^```\s*$", tail, re.MULTILINE | re.DOTALL)
    if len(fences) != 1:
        raise ReportRenderError(f"“{MODEL_HEADING}”章节必须含有且仅含有一个 JSON fenced block")
    try:
        model = json.loads(fences[0].strip())
    except json.JSONDecodeError as exc:
        raise ReportRenderError(f"JSON 附录不是合法 JSON：{exc.msg}") from exc
    validate_model(model)
    return ReportPayload(title=title, summary_paragraphs=summary_paragraphs, model=model)


def _embedded_json(value: Any) -> str:
    """Keep arbitrary source text from terminating the JSON script element."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _build_legacy_html(payload: ReportPayload, source_href: str) -> str:
    """Retain the prior card-report template only as a migration reference."""
    escaped_title = html.escape(payload.title)
    escaped_href = html.escape(source_href, quote=True)
    embedded = _embedded_json(
        {
            "title": payload.title,
            "summaryParagraphs": payload.summary_paragraphs,
            "model": payload.model,
            "sourceHref": source_href,
        }
    )
    return f"""<!--
目的：展示 case 或用户指定报告的完整元模型可视化结果。
定义：由 ai-pm-jd-analyzer 本地渲染器生成的独立离线 HTML 报告。
范围包括：岗位摘要、模型关系、要求、风险和可追溯证据。
范围不包括：不调用服务、不编辑模型、不包含原始 JD、prompt 或调试日志。
使用与修改规则：请通过 tools/render_full_model_report.py 从对应 Markdown 重新生成，不手工维护页面数据。
-->
<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{escaped_title}｜可视化报告</title>
  <style>
    :root {{
      --paper:#f5f0e6; --surface:#fffaf1; --surface-strong:#fffdf7; --ink:#1e2923;
      --muted:#657168; --line:rgba(30,41,35,.16); --green:#235b47; --leaf:#2f8d5b;
      --leaf-soft:#dceadf; --red:#ba5145; --red-soft:#f6ded9; --amber:#b66a22;
      --amber-soft:#f8e5c5; --blue:#3f6685; --blue-soft:#dce8f0; --shadow:0 28px 70px rgba(37,48,40,.12);
      --display:"LXGW WenKai Lite","Songti SC",serif; --body:"Avenir Next","PingFang SC","Hiragino Sans GB",sans-serif;
    }}
    html[data-theme="dark"] {{
      --paper:#101814; --surface:#18231d; --surface-strong:#1e2c24; --ink:#edf5ed; --muted:#afc0b3;
      --line:rgba(237,245,237,.14); --green:#91d3ae; --leaf:#71c58e; --leaf-soft:rgba(79,130,97,.32);
      --red:#f08e80; --red-soft:rgba(157,72,60,.26); --amber:#f0b45e; --amber-soft:rgba(184,108,34,.25);
      --blue:#91bdd9; --blue-soft:rgba(64,103,134,.32); --shadow:0 28px 75px rgba(0,0,0,.34);
    }}
    * {{ box-sizing:border-box }} html {{ background:var(--paper); scroll-behavior:smooth }}
    body {{ margin:0; min-width:320px; color:var(--ink); background:radial-gradient(circle at 95% 0%,rgba(83,151,104,.14),transparent 30rem),var(--paper); font-family:var(--body); line-height:1.55 }}
    button,a {{ font:inherit }} button {{ color:inherit }} button:focus-visible,a:focus-visible {{ outline:3px solid var(--amber); outline-offset:3px }}
    .shell {{ width:min(1400px,calc(100% - 40px)); margin:auto; padding:24px 0 70px }}
    .topbar {{ display:flex; align-items:center; justify-content:space-between; gap:18px; padding:10px 0 30px }}
    .brand {{ display:flex; align-items:center; gap:10px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; font-size:12px }}
    .brand-mark {{ width:30px; height:30px; display:grid; place-items:center; border-radius:50% 50% 46% 46%; background:var(--leaf); color:white; box-shadow:inset 0 -5px rgba(0,0,0,.12) }}
    .tools {{ display:flex; flex-wrap:wrap; gap:8px }} .quiet {{ border:1px solid var(--line); border-radius:999px; background:var(--surface); padding:8px 12px; text-decoration:none; cursor:pointer; font-size:13px }} .quiet:hover {{ border-color:var(--green); color:var(--green) }}
    .hero {{ position:relative; overflow:hidden; border:1px solid var(--line); border-radius:32px; padding:clamp(28px,5vw,64px); background:linear-gradient(130deg,var(--surface-strong),var(--leaf-soft)); box-shadow:var(--shadow) }}
    .hero:after {{ content:""; position:absolute; right:-80px; bottom:-150px; width:330px; height:330px; border:34px solid rgba(47,141,91,.18); border-radius:50%; transform:rotate(-15deg) }}
    .eyebrow {{ margin:0 0 13px; font-size:12px; color:var(--green); font-weight:800; letter-spacing:.13em; text-transform:uppercase }}
    h1,h2,h3,p {{ margin-top:0 }} h1 {{ max-width:900px; margin-bottom:18px; font:clamp(34px,5vw,68px)/1.08 var(--display); letter-spacing:-.06em }}
    .summary {{ position:relative; z-index:1; max-width:900px; font-size:17px; color:var(--muted) }} .summary p:last-child {{ margin-bottom:0 }}
    .hero-meta {{ position:relative; z-index:1; display:flex; flex-wrap:wrap; gap:9px; margin-top:26px }} .pill {{ padding:6px 10px; border:1px solid var(--line); border-radius:999px; background:rgba(255,255,255,.52); font-size:13px; font-weight:700 }} html[data-theme="dark"] .pill {{ background:rgba(0,0,0,.14) }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:18px 0 42px }} .metric {{ padding:18px; border:1px solid var(--line); border-radius:18px; background:var(--surface); min-width:0 }} .metric b {{ display:block; font:32px/1 var(--display); color:var(--green) }} .metric span {{ color:var(--muted); font-size:13px }}
    .section {{ margin-top:54px }} .section-head {{ display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:18px }} h2 {{ margin:0; font:clamp(25px,3vw,38px)/1.1 var(--display); letter-spacing:-.04em }} .section-note {{ color:var(--muted); max-width:580px; font-size:14px }}
    .legend {{ display:flex; gap:9px; flex-wrap:wrap }} .status {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:800; border-radius:999px; padding:5px 9px }} .status:before {{ content:""; width:7px; height:7px; border-radius:50%; background:currentColor }} .explicit {{ color:var(--leaf); background:var(--leaf-soft) }} .inferred {{ color:var(--amber); background:var(--amber-soft) }} .not_disclosed {{ color:var(--blue); background:var(--blue-soft) }}
    .flow-board {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(260px,.36fr); gap:16px }} .flow-scroll {{ overflow-x:auto; padding-bottom:8px }} .flow {{ display:flex; align-items:stretch; min-width:max-content; gap:10px }} .stream {{ width:245px; padding:18px; border-radius:20px; border:1px solid var(--line); background:var(--surface); position:relative }} .stream:not(:last-child):after {{ content:"→"; position:absolute; right:-18px; top:48%; z-index:1; color:var(--green); font-weight:900 }} .stream-index {{ color:var(--green); font-size:12px; font-weight:900 }} .stream h3 {{ margin:7px 0 5px; font-size:17px; line-height:1.25 }} .stream p {{ color:var(--muted); font-size:13px }}
    .node-list {{ display:grid; gap:7px; margin-top:15px }} .node {{ width:100%; display:flex; align-items:center; justify-content:space-between; gap:10px; text-align:left; border:1px solid var(--line); border-radius:11px; padding:9px 10px; background:var(--surface-strong); cursor:pointer; font-size:13px }} .node:hover,.node[aria-pressed="true"] {{ border-color:var(--green); box-shadow:0 5px 20px rgba(35,91,71,.12) }} .node small {{ color:var(--muted); white-space:nowrap }}
    .evidence {{ border:1px solid var(--line); border-radius:20px; padding:20px; background:var(--surface); min-height:300px }} .evidence h3 {{ font-size:20px; margin-bottom:9px }} .evidence p {{ color:var(--muted); font-size:14px }} .evidence .quote {{ margin-top:15px; padding:12px; border-left:3px solid var(--green); background:var(--leaf-soft); color:var(--ink); font-size:14px }}
    .switches {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px }} .switch {{ cursor:pointer; border:1px solid var(--line); border-radius:999px; padding:8px 12px; background:var(--surface); font-size:13px; font-weight:700 }} .switch[aria-selected="true"] {{ background:var(--green); color:white; border-color:var(--green) }} .relation-board {{ border:1px solid var(--line); border-radius:24px; background:var(--surface); overflow:hidden }} .relation-canvas {{ min-height:410px; padding:20px; overflow:auto; background:linear-gradient(90deg,rgba(35,91,71,.035) 1px,transparent 1px),linear-gradient(rgba(35,91,71,.035) 1px,transparent 1px); background-size:22px 22px }} .relation-grid {{ display:grid; grid-template-columns:repeat(3,minmax(200px,1fr)); gap:22px; min-width:760px; align-items:start }} .relation-column {{ display:grid; gap:10px }} .relation-column h3 {{ margin:0 0 3px; font-size:13px; color:var(--muted) }} .relation-node {{ border:1px solid var(--line); border-radius:13px; background:var(--surface-strong); padding:12px; cursor:pointer; text-align:left }} .relation-node:hover,.relation-node.active {{ border-color:var(--green); background:var(--leaf-soft) }} .relation-node small {{ display:block; color:var(--muted); margin-top:4px }} .relation-links {{ margin:6px 0 0; padding-left:18px; color:var(--green); font-size:12px }}
    .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:16px }} .panel {{ border:1px solid var(--line); border-radius:22px; background:var(--surface); padding:22px }} .panel h3 {{ margin-bottom:14px; font-size:19px }} .card-list {{ display:grid; gap:10px }} .card {{ border-left:3px solid var(--line); padding:12px 0 12px 13px }} .card.mandatory {{ border-left-color:var(--red) }} .card.preferred {{ border-left-color:var(--leaf) }} .card.risk {{ border-left-color:var(--amber) }} .card.unknown {{ border-left-color:var(--blue) }} .card strong {{ display:block }} .card span {{ color:var(--muted); font-size:13px }}
    .foot {{ display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-top:50px; padding-top:20px; border-top:1px solid var(--line); color:var(--muted); font-size:12px }}
    @media (max-width:850px) {{ .shell {{ width:min(100% - 24px,720px) }} .metric-grid,.two-col,.flow-board {{ grid-template-columns:1fr }} .evidence {{ min-height:auto }} .section-head {{ align-items:start; flex-direction:column }} .topbar {{ align-items:flex-start; flex-direction:column }} }}
    @media print {{ .tools,.switches {{ display:none!important }} body {{ background:white }} .shell {{ width:100%; padding:0 }} .hero,.panel,.relation-board,.stream,.metric {{ box-shadow:none }} .relation-canvas {{ min-height:0; overflow:visible }} }}
    @media (prefers-reduced-motion:reduce) {{ * {{ scroll-behavior:auto!important; transition:none!important }} }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar"><div class="brand"><span class="brand-mark">瓜</span>完整元模型可视化报告</div><div class="tools"><a class="quiet" id="source-link" href="{escaped_href}">查看 Markdown</a><button class="quiet" id="theme-toggle" type="button">切到夜里</button><button class="quiet" id="print-button" type="button">打印 / 存为 PDF</button></div></header>
    <section class="hero"><p class="eyebrow">Evidence-first job intelligence / {html.escape(SCHEMA_VERSION)}</p><h1 id="report-title">{escaped_title}</h1><div class="summary" id="summary"></div><div class="hero-meta" id="hero-meta"></div></section>
    <section class="metric-grid" id="metrics" aria-label="模型规模"></section>
    <section class="section"><div class="section-head"><div><p class="eyebrow">01 / 工作链路</p><h2>从场景到运营，岗位在负责什么？</h2></div><div class="legend" id="legend"></div></div><div class="flow-board"><div class="flow-scroll"><div class="flow" id="flow"></div></div><aside class="evidence" id="evidence" aria-live="polite"></aside></div></section>
    <section class="section"><div class="section-head"><div><p class="eyebrow">02 / 结构关系</p><h2>对象、能力与依赖如何相连？</h2></div><p class="section-note">先从价值流和事项看全貌；关系视图按需展开，避免大模型退化为难读的全量连线。</p></div><div class="switches" role="tablist"><button class="switch" type="button" data-relation="entities" aria-selected="true">实体与主归属能力</button><button class="switch" type="button" data-relation="capabilities" aria-selected="false">能力依赖</button><button class="switch" type="button" data-relation="operations" aria-selected="false">事项 CRUD 与能力</button></div><div class="relation-board"><div class="relation-canvas" id="relation-canvas"></div></div></section>
    <section class="section two-col"><article class="panel"><p class="eyebrow">03 / 入场门槛</p><h2>哪些要求是硬条件？</h2><div class="card-list" id="requirements"></div></article><article class="panel"><p class="eyebrow">04 / 风险收口</p><h2>哪些事必须问清？</h2><div class="card-list" id="risks"></div></article></section>
    <footer class="foot"><span>页面由本地完整元模型渲染器生成；图形仅展示报告 JSON 已有事实与关系。</span><span>证据状态：explicit / inferred / not_disclosed</span></footer>
  </main>
  <script id="report-data" type="application/json">{embedded}</script>
  <script>
  (() => {{
    const report = JSON.parse(document.getElementById('report-data').textContent);
    const model = report.model;
    const $ = (selector) => document.querySelector(selector);
    const byId = (items) => Object.fromEntries(items.map((item) => [item.id, item]));
    const streams = byId(model.value_streams), workItems = byId(model.work_items), entities = byId(model.business_entities), capabilities = byId(model.business_capabilities);
    const labels = {{ create:'创建', read:'读取', update:'更新', delete:'删除', responsible:'执行负责', accountable:'最终负责', consulted:'被征询', informed:'被知会', input_to:'输入到', related_to:'相关', depends_on:'依赖' }};
    const statusLabels = {{ explicit:'JD 明确表达', inferred:'谨慎推断', not_disclosed:'JD 未披露' }};
    const make = (tag, className, text) => {{ const element = document.createElement(tag); if (className) element.className = className; if (text !== undefined) element.textContent = text; return element; }};
    const evidenceFor = (item) => item && item.evidence ? item.evidence : {{ status:'not_disclosed' }};
    const renderEvidence = (item, typeLabel, extra = []) => {{
      const evidence = evidenceFor(item); const panel = $('#evidence'); panel.replaceChildren();
      panel.append(make('span', `status ${{evidence.status || 'not_disclosed'}}`, statusLabels[evidence.status] || evidence.status));
      panel.append(make('h3', '', item.name || typeLabel));
      if (typeLabel) panel.append(make('p', '', typeLabel));
      if (item.description) panel.append(make('p', '', item.description));
      extra.filter(Boolean).forEach((line) => panel.append(make('p', '', line)));
      const quote = evidence.snippets && evidence.snippets.length ? evidence.snippets.join('；') : evidence.inference_basis || 'JD 未披露该项的可核验证据。';
      panel.append(make('div', 'quote', quote));
    }};
    const allEvidence = [];
    ['value_streams','work_items','roles','business_entities','business_capabilities','qualification_requirements','risks','uncertainties'].forEach((key) => (model[key] || []).forEach((item) => allEvidence.push(evidenceFor(item))));
    const counts = allEvidence.reduce((result, evidence) => {{ result[evidence.status] = (result[evidence.status] || 0) + 1; return result; }}, {{}});
    report.summaryParagraphs.forEach((paragraph) => $('#summary').append(make('p', '', paragraph)));
    const profile = model.job_profile.fields || {{}}; const judgment = model.judgment.fields || {{}};
    [profile.job_title, profile.location, profile.level, judgment.ai_authenticity].filter(Boolean).forEach((field) => {{ if (field.value) $('#hero-meta').append(make('span', 'pill', field.value)); }});
    const metrics = [ [model.value_streams.length,'价值流'], [model.work_items.length,'工作事项'], [model.business_entities.length,'业务实体'], [model.business_capabilities.length,'业务能力'] ];
    metrics.forEach(([value,label]) => {{ const card = make('div','metric'); card.append(make('b','',String(value))); card.append(make('span','',label)); $('#metrics').append(card); }});
    ['explicit','inferred','not_disclosed'].forEach((status) => $('#legend').append(make('span', `status ${{status}}`, `${{statusLabels[status]}} · ${{counts[status] || 0}}`)));
    model.value_streams.forEach((stream, streamIndex) => {{
      const card = make('article','stream'); card.append(make('span','stream-index',`价值流 ${{String(streamIndex + 1).padStart(2,'0')}}`)); card.append(make('h3','',stream.name)); card.append(make('p','',stream.description || '')); const list = make('div','node-list');
      model.work_items.filter((item) => item.value_stream_id === stream.id).forEach((item) => {{ const node = make('button','node'); node.type='button'; node.append(make('span','',item.name)); node.append(make('small','',`${{(item.entity_operations || []).length}} 实体`)); node.addEventListener('click', () => {{ document.querySelectorAll('.node').forEach((button) => button.setAttribute('aria-pressed','false')); node.setAttribute('aria-pressed','true'); renderEvidence(item,'工作事项', [`所属价值流：${{stream.name}}`, `关联能力：${{(item.capability_ids || []).map((id) => capabilities[id]?.name).filter(Boolean).join('、') || '未披露'}}`]); }}); list.append(node); }}); card.append(list); $('#flow').append(card);
    }});
    renderEvidence(model.value_streams[0], '价值流', ['点击左侧工作事项，查看其实体、能力与证据。']);
    const relationCanvas = $('#relation-canvas');
    const relationData = {{
      entities: () => {{ const columns = [{{title:'业务实体', items:model.business_entities}}, {{title:'主归属能力', items:model.business_capabilities}}, {{title:'实体关系', items:model.entity_relationships.map((relation) => ({{ name:`${{entities[relation.source_id].name}} → ${{entities[relation.target_id].name}}`, description:labels[relation.relation_type], evidence:relation.evidence, relation }}))}}]; return columns; }},
      capabilities: () => [{{title:'能力', items:model.business_capabilities}}, {{title:'依赖关系', items:model.capability_relationships.map((relation) => ({{ name:`${{capabilities[relation.source_id].name}} → ${{capabilities[relation.target_id].name}}`, description:labels[relation.relation_type], evidence:relation.evidence, relation }}))}}, {{title:'被支持工作事项', items:model.work_items}}],
      operations: () => [{{title:'工作事项', items:model.work_items}}, {{title:'实体 CRUD', items:model.work_items.flatMap((item) => item.entity_operations.map((operation) => ({{ name:`${{item.name}} · ${{entities[operation.entity_id].name}}`, description:labels[operation.operation], evidence:operation.evidence, operation }})))}}, {{title:'所需能力', items:model.business_capabilities}}]
    }};
    const extraFor = (item, mode) => {{
      if (mode === 'entities' && item.primary_capability_id) return [`主归属能力：${{capabilities[item.primary_capability_id]?.name || '未披露'}}`];
      if (mode === 'capabilities' && item.supported_work_item_ids) return [`支撑事项：${{item.supported_work_item_ids.map((id) => workItems[id]?.name).filter(Boolean).join('、') || '未披露'}}`];
      if (mode === 'operations' && item.capability_ids) return [`关联能力：${{item.capability_ids.map((id) => capabilities[id]?.name).filter(Boolean).join('、') || '未披露'}}`];
      return item.description ? [item.description] : [];
    }};
    const renderRelations = (mode) => {{ relationCanvas.replaceChildren(); const grid = make('div','relation-grid'); relationData[mode]().forEach((column) => {{ const col = make('section','relation-column'); col.append(make('h3','',column.title)); column.items.forEach((item) => {{ const button = make('button','relation-node'); button.type='button'; button.append(make('strong','',item.name || '未命名关系')); if (item.description) button.append(make('small','',item.description)); const extras = extraFor(item, mode); if (extras.length) {{ const links = make('ul','relation-links'); extras.forEach((line) => links.append(make('li','',line))); button.append(links); }} button.addEventListener('click', () => {{ document.querySelectorAll('.relation-node').forEach((node) => node.classList.remove('active')); button.classList.add('active'); renderEvidence(item, column.title, extras); }}); col.append(button); }}); grid.append(col); }}); relationCanvas.append(grid); }};
    document.querySelectorAll('[data-relation]').forEach((button) => button.addEventListener('click', () => {{ document.querySelectorAll('[data-relation]').forEach((tab) => tab.setAttribute('aria-selected','false')); button.setAttribute('aria-selected','true'); renderRelations(button.dataset.relation); }})); renderRelations('entities');
    const humanTargets = (targets) => (targets || []).map((id) => workItems[id]?.name || capabilities[id]?.name || streams[id]?.name || id).join('、');
    model.qualification_requirements.forEach((requirement) => {{ const card = make('article', `card ${{requirement.necessity === 'mandatory' ? 'mandatory' : 'preferred'}}`); card.append(make('strong','',requirement.name)); card.append(make('span','',`${{requirement.necessity === 'mandatory' ? '硬性要求' : '加分项'}} · ${{humanTargets(requirement.mapping_target_ids) || '岗位准入'}}`)); card.addEventListener('click', () => renderEvidence(requirement,'任职要求')); $('#requirements').append(card); }});
    [...model.risks.map((item) => [item,'risk','风险']), ...model.uncertainties.map((item) => [item,'unknown','待确认'])].forEach(([item,kind,label]) => {{ const card = make('article',`card ${{kind}}`); card.tabIndex=0; card.append(make('strong','',`${{label}} · ${{item.name}}`)); card.append(make('span','',item.description || '')); const open = () => renderEvidence(item,label); card.addEventListener('click',open); card.addEventListener('keydown',(event) => {{ if (event.key === 'Enter' || event.key === ' ') {{ event.preventDefault(); open(); }} }}); $('#risks').append(card); }});
    const root = document.documentElement; const toggle = $('#theme-toggle'); const setTheme = (theme) => {{ root.dataset.theme=theme; toggle.textContent=theme === 'dark' ? '切到白天' : '切到夜里'; }}; setTheme('light'); toggle.addEventListener('click', () => setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark')); $('#print-button').addEventListener('click', () => window.print());
  }})();
  </script>
</body>
</html>"""


def build_html(payload: ReportPayload, source_href: str) -> str:
    """Build the standalone relationship-graph workbench for a validated report."""
    template = r'''<!--
目的：展示 case 或用户指定报告的完整元模型关系图谱。
定义：由 ai-pm-jd-analyzer 本地渲染器生成的独立离线图谱工作台。
范围包括：模型统计、关系图、节点筛选、缩放拖拽与可追溯详情抽屉。
范围不包括：不调用服务、不编辑模型、不包含原始 JD、prompt 或调试日志。
使用与修改规则：请通过 tools/render_full_model_report.py 从对应 Markdown 重新生成，不手工维护页面数据。
-->
<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>__TITLE__｜关系图谱</title>
  <style>
    :root { --paper:#f4f0e7;--surface:#fffdf7;--ink:#17342b;--muted:#66786e;--line:#d7ddd3;--grid:rgba(29,83,63,.075);--forest:#195c48;--leaf:#31905d;--role:#5d7881;--capability:#28736f;--amber:#dd9226;--brick:#a8482f;--soft:#e8f0e5;--shadow:0 22px 55px rgba(35,57,45,.12);--body:"Avenir Next","PingFang SC","Hiragino Sans GB",sans-serif;--display:"LXGW WenKai Lite","Songti SC",serif;--report-font-size:13px; }
    html[data-theme="dark"] { --paper:#101914;--surface:#17241d;--ink:#eef5ee;--muted:#aac0b2;--line:#385043;--grid:rgba(176,220,188,.08);--forest:#8bd3ad;--leaf:#6cc98d;--role:#9ab8c1;--capability:#7ec9c3;--amber:#f0b661;--brick:#ee947f;--soft:#223b2d;--shadow:0 24px 65px rgba(0,0,0,.3); }
    * { box-sizing:border-box } body { margin:0; min-width:320px; color:var(--ink); background:radial-gradient(circle at 88% -15%,rgba(102,174,116,.18),transparent 30rem),var(--paper); font:14px/1.55 var(--body); } button,a { font:inherit; } button { color:inherit; } button:focus-visible,a:focus-visible,[tabindex="0"]:focus-visible { outline:3px solid var(--amber); outline-offset:3px; }
    .shell { width:min(1540px,calc(100% - 36px)); margin:auto; padding:24px 0 54px; } .topbar { display:flex; justify-content:space-between; align-items:center; gap:18px; padding:0 2px 22px; } .brand { display:flex; align-items:center; gap:10px; color:var(--forest); font-size:12px; font-weight:900; letter-spacing:.1em; text-transform:uppercase; } .brand-mark { display:grid; place-items:center; width:32px; height:32px; border-radius:12px 12px 16px 16px; background:var(--forest); color:#fff; box-shadow:inset 0 -5px rgba(0,0,0,.13); } .tools { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; } .quiet { border:1px solid var(--line); border-radius:999px; padding:8px 12px; background:var(--surface); color:var(--ink); cursor:pointer; text-decoration:none; font-size:12px; font-weight:800; } .quiet:hover { border-color:var(--forest); color:var(--forest); }
    .intro { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:22px; align-items:end; margin-bottom:16px; padding:28px 30px; border:1px solid var(--line); border-radius:26px; background:linear-gradient(120deg,var(--surface),var(--soft)); box-shadow:var(--shadow); } .eyebrow { margin:0 0 9px; color:var(--forest); font-size:11px; font-weight:900; letter-spacing:.12em; text-transform:uppercase; } h1 { max-width:900px; margin:0; font:clamp(30px,4vw,56px)/1.08 var(--display); letter-spacing:-.045em; } .summary { max-width:870px; margin:15px 0 0; color:var(--muted); font-size:15px; } .metrics { display:grid; grid-template-columns:repeat(4,minmax(70px,1fr)); gap:8px; } .metric { min-width:84px; padding:11px; border:1px solid var(--line); border-radius:14px; background:color-mix(in srgb,var(--surface) 84%,transparent); text-align:center; } .metric b { display:block; color:var(--forest); font:26px/1 var(--display); } .metric span { display:block; margin-top:3px; color:var(--muted); font-size:11px; white-space:nowrap; }
    .model-workbench { position:relative; overflow:hidden; border:1px solid var(--line); border-radius:26px; background:var(--surface); box-shadow:var(--shadow); } .workbench-head { display:flex; justify-content:space-between; align-items:center; gap:18px; padding:17px 22px; border-bottom:1px solid var(--line); background:linear-gradient(90deg,color-mix(in srgb,var(--soft) 92%,transparent),var(--surface)); } .workbench-title { display:flex; align-items:center; gap:12px; min-width:0; } .workbench-title h2 { margin:0; font:700 20px/1.1 var(--display); } .workbench-title span { color:var(--muted); font-size:12px; } .view-chip { flex:0 0 auto; padding:6px 9px; border-radius:999px; background:var(--forest); color:#fff; font-size:11px; font-weight:900; }
    .graph-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:8px; padding:12px 18px; border-bottom:1px solid var(--line); } .toolbar-label { margin-right:2px; color:var(--muted); font-size:12px; font-weight:800; } .graph-filter,.fit-graph { border:1px solid var(--line); border-radius:999px; padding:6px 10px; background:var(--surface); cursor:pointer; font-size:12px; font-weight:800; } .graph-filter[aria-pressed="true"] { color:#fff; border-color:var(--filter); background:var(--filter); } .graph-filter[data-type="stream"] { --filter:var(--forest); } .graph-filter[data-type="work"] { --filter:var(--leaf); } .graph-filter[data-type="entity"] { --filter:var(--amber); } .graph-filter[data-type="capability"] { --filter:var(--brick); } .fit-graph { margin-left:auto; border-color:var(--forest); color:var(--forest); }
    .graph-stage { position:relative; min-height:660px; overflow:hidden; background-color:var(--surface); background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px); background-size:28px 28px; touch-action:none; } #graph-svg { display:block; width:100%; height:660px; cursor:grab; } #graph-svg.panning { cursor:grabbing; } .graph-edge { fill:none; stroke-linecap:round; pointer-events:none; transition:opacity .16s; } .graph-edge.contains { stroke:var(--forest); stroke-width:2.4; } .graph-edge.crud { stroke:var(--amber); stroke-width:1.8; stroke-dasharray:6 5; } .graph-edge.requires { stroke:var(--brick); stroke-width:1.7; stroke-dasharray:2 5; } .graph-edge.context { stroke:var(--muted); stroke-width:1.1; stroke-dasharray:2 7; opacity:.38; } .graph-node { cursor:pointer; } .graph-node .shape { transition:opacity .16s,filter .16s,stroke-width .16s; } .graph-node:hover .shape,.graph-node:focus .shape,.graph-node.selected .shape { filter:drop-shadow(0 5px 7px rgba(15,46,34,.2)); stroke:var(--ink); stroke-width:2.5; } .graph-label { pointer-events:none; fill:var(--ink); font-size:12px; font-weight:800; text-anchor:middle; paint-order:stroke; stroke:var(--surface); stroke-linejoin:round; stroke-width:4px; } .graph-node.hidden,.graph-edge.hidden { display:none; } .graph-node.dimmed,.graph-edge.dimmed { opacity:.13; } .graph-node.dimmed .shape { filter:none; } .graph-zoom-controls { position:absolute; z-index:3; bottom:16px; left:16px; display:grid; gap:6px; padding:6px; border:1px solid var(--line); border-radius:12px; background:color-mix(in srgb,var(--surface) 94%,transparent); box-shadow:0 8px 20px rgba(27,52,39,.14); } .graph-zoom-button { display:grid; place-items:center; width:36px; height:36px; border:1px solid var(--line); border-radius:8px; background:var(--surface); color:var(--ink); cursor:pointer; font-size:21px; font-weight:800; line-height:1; } .graph-zoom-button:hover:not(:disabled) { border-color:var(--forest); color:var(--forest); } .graph-zoom-button:disabled { cursor:not-allowed; opacity:.45; }
    .tooltip { position:absolute; z-index:4; max-width:260px; padding:9px 11px; border:1px solid var(--line); border-radius:10px; background:color-mix(in srgb,var(--surface) 96%,transparent); box-shadow:0 10px 25px rgba(27,52,39,.16); color:var(--ink); font-size:12px; pointer-events:none; opacity:0; transform:translateY(4px); transition:opacity .12s,transform .12s; } .tooltip.open { opacity:1; transform:translateY(0); } .tooltip b { display:block; margin-bottom:2px; } .tooltip span { color:var(--muted); }
    .legend { display:flex; flex-wrap:wrap; align-items:center; gap:11px 16px; padding:12px 18px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; } .legend strong { color:var(--ink); } .legend-item { display:inline-flex; align-items:center; gap:6px; } .swatch { width:13px; height:13px; background:var(--swatch); } .swatch.stream { --swatch:var(--forest); border-radius:4px; } .swatch.work { --swatch:var(--leaf); border-radius:50%; } .swatch.entity { --swatch:var(--amber); transform:rotate(45deg); border-radius:2px; } .swatch.capability { --swatch:var(--brick); clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%); } .line { width:25px; border-top:2px solid var(--line); } .line.contains { border-color:var(--forest); } .line.crud { border-color:var(--amber); border-top-style:dashed; } .line.requires { border-color:var(--brick); border-top-style:dotted; }
    .drawer-scrim { position:fixed; inset:0; z-index:9; display:none; background:rgba(9,22,16,.28); } .drawer-scrim.open { display:block; } .detail-drawer { position:absolute; z-index:10; top:0; right:0; display:flex; flex-direction:column; width:min(390px,94vw); height:100%; padding:20px; border-left:1px solid var(--line); background:var(--surface); box-shadow:-18px 0 42px rgba(21,45,33,.16); transform:translateX(104%); transition:transform .2s ease; overflow:auto; } .detail-drawer.open { transform:translateX(0); } .drawer-close { position:absolute; top:14px; right:14px; width:32px; height:32px; border:1px solid var(--line); border-radius:50%; background:var(--surface); cursor:pointer; font-size:21px; line-height:1; } .drawer-type { margin:4px 42px 12px 0; color:var(--forest); font-size:11px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; } .detail-drawer h3 { margin:0 34px 6px 0; font:24px/1.2 var(--display); } .drawer-copy { margin:6px 0 18px; color:var(--muted); } .drawer-section { margin-top:18px; } .drawer-section h4 { margin:0 0 8px; color:var(--muted); font-size:11px; letter-spacing:.08em; text-transform:uppercase; } .detail-list { display:grid; gap:7px; } .detail-link { width:100%; border:1px solid var(--line); border-radius:10px; padding:8px 10px; background:var(--surface); color:var(--ink); cursor:pointer; text-align:left; font-size:12px; } .detail-link:hover { border-color:var(--forest); color:var(--forest); } .evidence { padding:10px; border-radius:10px; background:var(--soft); } .evidence-status { display:inline-block; margin-bottom:6px; color:var(--forest); font-size:11px; font-weight:900; } .evidence-status.inferred { color:var(--amber); } .evidence-status.not_disclosed { color:var(--muted); } .evidence-quote { margin:6px 0 0; color:var(--ink); font-size:12px; }
    .view-tabs { display:flex; align-items:end; gap:7px; margin:24px 0 -1px; padding:0 18px; } .view-tab { position:relative; z-index:2; border:1px solid var(--line); border-bottom:0; border-radius:14px 14px 0 0; padding:10px 13px; background:color-mix(in srgb,var(--surface) 76%,var(--paper)); color:var(--muted); cursor:pointer; font-size:12px; font-weight:900; } .view-tab[aria-selected="true"] { background:var(--surface); color:var(--forest); } .view-panel[hidden] { display:none!important; }
    .model-new-view { overflow:hidden; border:1px solid var(--line); border-radius:0 26px 26px 26px; background:var(--surface); box-shadow:var(--shadow); } .new-view-head { display:flex; align-items:end; justify-content:space-between; gap:18px; padding:20px 22px; border-bottom:1px solid var(--line); background:linear-gradient(90deg,color-mix(in srgb,var(--soft) 92%,transparent),var(--surface)); } .new-view-head h2 { margin:0; font:700 22px/1.1 var(--display); } .new-view-head p { max-width:580px; margin:7px 0 0; color:var(--muted); font-size:12px; } .view-kicker { margin:0 0 6px; color:var(--forest); font-size:10px; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }
    .flow-view-shell,.capability-view-shell,.requirement-view-shell { padding:22px; overflow-x:auto; background-color:var(--surface); background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px); background-size:28px 28px; } .flow-view-grid,.capability-layout { min-width:960px; } .flow-view-grid { display:grid; grid-template-columns:210px minmax(0,1fr); gap:18px; align-items:start; } .rail { padding:15px; border:1px solid var(--line); border-radius:18px; background:color-mix(in srgb,var(--surface) 93%,var(--soft)); } .rail h3,.relation-zone h3 { margin:0 0 10px; color:var(--forest); font-size:12px; letter-spacing:.06em; } .rail-note,.empty-state { margin:0; color:var(--muted); font-size:12px; } .role-card,.requirement-card,.entity-card,.work-mini,.relation-card { margin-top:9px; border:1px solid var(--line); border-radius:12px; background:var(--surface); } .role-card { padding:11px; border-left:3px solid var(--role); background:color-mix(in srgb,var(--role) 5%,var(--surface)); } .role-card strong,.requirement-card strong,.entity-card strong,.work-mini strong { display:block; font-size:13px; line-height:1.35; } .role-link,.model-link { width:100%; border:0; background:none; color:var(--ink); cursor:pointer; font:inherit; text-align:left; } .role-link { padding:7px 0 0; color:var(--forest); font-size:12px; } .raci-badge,.relation-pill,.field-status { display:inline-flex; align-items:center; border-radius:999px; padding:2px 6px; font-size:10px; font-weight:900; } .raci-badge { margin-right:5px; color:var(--role); background:color-mix(in srgb,var(--role) 13%,var(--surface)); } .relation-pill.crud { color:#925700; background:color-mix(in srgb,var(--amber) 22%,var(--surface)); } .relation-pill.capability { color:var(--capability); background:color-mix(in srgb,var(--capability) 13%,var(--surface)); }
    .stream-stack { display:grid; grid-template-columns:repeat(auto-fit,minmax(245px,1fr)); gap:15px; } .stream-container,.capability-container { position:relative; border:1px solid color-mix(in srgb,var(--forest) 52%,var(--line)); border-radius:20px; padding:15px; background:color-mix(in srgb,var(--surface) 92%,var(--soft)); } .stream-container { border-left:3px solid var(--forest); } .capability-container { border-color:color-mix(in srgb,var(--capability) 48%,var(--line)); border-left:3px solid var(--capability); background:color-mix(in srgb,var(--capability) 5%,var(--surface)); } .stream-container:before,.capability-container:before { position:absolute; top:-10px; left:14px; padding:2px 7px; border-radius:999px; background:var(--forest); color:#fff; font-size:10px; font-weight:900; letter-spacing:.04em; } .stream-container:before { content:'价值流'; } .capability-container:before { content:'业务能力'; background:var(--capability); } .stream-container h3,.capability-container h3 { margin:2px 0 12px; font:700 18px/1.22 var(--display); } .work-card { margin-top:10px; padding:11px; border:1px solid color-mix(in srgb,var(--leaf) 38%,var(--line)); border-left:3px solid var(--leaf); border-radius:13px; background:color-mix(in srgb,var(--leaf) 5%,var(--surface)); } .work-card h4 { margin:0; font-size:13px; line-height:1.35; } .association-row { display:grid; gap:5px; margin-top:9px; padding-top:8px; border-top:1px dashed var(--line); } .association-label { color:var(--muted); font-size:10px; font-weight:900; letter-spacing:.04em; } .association-links { display:flex; flex-wrap:wrap; gap:5px; } .association-link { border:1px solid var(--line); border-radius:999px; padding:4px 7px; background:var(--surface-strong,var(--surface)); color:var(--ink); cursor:pointer; font-size:11px; line-height:1.25; text-align:left; } .association-link.crud { border-color:color-mix(in srgb,var(--amber) 46%,var(--line)); color:#925700; background:color-mix(in srgb,var(--amber) 8%,var(--surface)); } .association-link.capability { border-color:color-mix(in srgb,var(--capability) 46%,var(--line)); color:var(--capability); background:color-mix(in srgb,var(--capability) 7%,var(--surface)); }
    .capability-stack { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:15px; } .entity-card,.work-mini { padding:10px; } .entity-card { border-left:3px solid var(--amber); background:color-mix(in srgb,var(--amber) 6%,var(--surface)); } .work-mini { border-left:3px solid var(--leaf); } .requirement-card { padding:11px; border-left:3px solid var(--brick); } .requirement-card.is-independent { border-left-color:var(--amber); } .requirement-card .association-links { margin-top:8px; } .relation-zone { margin-top:18px; padding:15px; border-top:1px solid var(--line); background:color-mix(in srgb,var(--surface) 90%,var(--soft)); } .relation-list { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:9px; } .relation-card { display:flex; align-items:center; gap:7px; padding:10px; } .relation-card .model-link { padding:0; font-size:12px; } .relation-arrow { flex:0 0 auto; color:var(--forest); font-weight:900; } .relation-card.is-neutral .relation-arrow { color:var(--muted); }
    .requirement-board { display:grid; min-width:820px; gap:12px; } .requirement-map { display:grid; grid-template-columns:minmax(260px,.85fr) minmax(170px,.45fr) minmax(300px,1fr); gap:12px; align-items:center; padding:14px; border:1px solid color-mix(in srgb,var(--brick) 34%,var(--line)); border-left:3px solid var(--brick); border-radius:18px; background:color-mix(in srgb,var(--brick) 5%,var(--surface)); } .requirement-map.is-independent { grid-template-columns:minmax(260px,.85fr) minmax(170px,.45fr) minmax(220px,.7fr); } .requirement-trigger { width:100%; border:0; background:none; color:var(--ink); cursor:pointer; text-align:left; padding:0; } .requirement-trigger strong { display:block; font-size:14px; line-height:1.35; } .requirement-meta { display:flex; flex-wrap:wrap; gap:5px; margin-top:7px; } .requirement-meta span { border-radius:999px; padding:2px 6px; background:color-mix(in srgb,var(--brick) 10%,var(--surface)); color:var(--brick); font-size:10px; font-weight:900; } .requirement-bridge { color:var(--muted); font-size:11px; font-weight:900; text-align:center; } .requirement-bridge:before { content:'→'; margin-right:6px; color:var(--brick); font-size:16px; vertical-align:-1px; } .requirement-targets { display:flex; flex-wrap:wrap; gap:6px; } .requirement-targets .association-link { border-color:color-mix(in srgb,var(--brick) 42%,var(--line)); }
    .report-details { margin-top:24px; overflow:hidden; border:1px solid var(--line); border-radius:24px; background:var(--surface); box-shadow:var(--shadow); } .report-details-head { padding:20px 22px 12px; } .report-details-head h2 { margin:0; font:700 21px/1.15 var(--display); } .report-details-head p { margin:7px 0 0; color:var(--muted); font-size:12px; } .detail-groups { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0; border-top:1px solid var(--line); } .detail-group { padding:16px 18px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); } .detail-group:nth-child(even) { border-right:0; } .detail-group h3 { margin:0; font-size:14px; } .fact-row { display:flex; align-items:start; justify-content:space-between; gap:10px; margin-top:9px; padding-top:9px; border-top:1px dashed var(--line); } .fact-row:first-of-type { border-top:0; } .fact-row b { display:block; font-size:12px; } .fact-row span:last-child { color:var(--muted); font-size:12px; text-align:right; } .field-status { color:var(--muted); background:var(--soft); } .field-status.explicit { color:var(--forest); } .field-status.inferred { color:#925700; } .analysis-card { margin-top:9px; padding:10px; border-left:3px solid var(--amber); background:color-mix(in srgb,var(--amber) 7%,var(--surface)); } .analysis-card.uncertainty { border-left-color:var(--brick); background:color-mix(in srgb,var(--brick) 6%,var(--surface)); } .analysis-card strong { display:block; font-size:12px; } .analysis-card p { margin:4px 0 0; color:var(--muted); font-size:12px; }
    .model-detail-trigger { cursor:pointer; transition:border-color .16s ease,background .16s ease,box-shadow .16s ease; } .model-detail-trigger:hover,.model-detail-trigger:focus-visible { box-shadow:0 5px 16px rgba(27,52,39,.11); } .model-detail-trigger.model-detail-selected { outline:2px solid var(--ink); outline-offset:2px; box-shadow:0 8px 20px rgba(27,52,39,.17); } .model-detail-drawer { position:fixed; z-index:20; top:0; right:0; width:min(400px,94vw); height:100dvh; padding:22px; border-left:1px solid var(--line); background:var(--surface); box-shadow:-18px 0 42px rgba(21,45,33,.22); transform:translateX(104%); transition:transform .2s ease; overflow:auto; } .model-detail-drawer.open { transform:translateX(0); } .model-detail-close { position:absolute; top:14px; right:14px; width:32px; height:32px; border:1px solid var(--line); border-radius:50%; background:var(--surface); cursor:pointer; font-size:20px; } .model-detail-type { margin:5px 42px 10px 0; color:var(--forest); font-size:11px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; } .model-detail-drawer h3 { margin:0 35px 12px 0; font:24px/1.2 var(--display); } .model-detail-drawer p { color:var(--muted); }
    @media (max-width:820px) { .shell { width:min(100% - 20px,760px); padding-top:12px; } .topbar,.intro { align-items:flex-start; flex-direction:column; } .tools { justify-content:flex-start; } .intro { padding:22px; } .metrics { width:100%; } .graph-stage,#graph-svg { min-height:560px; height:560px; } .workbench-head { align-items:flex-start; flex-direction:column; } .fit-graph { margin-left:0; } .detail-drawer { position:fixed; top:auto; bottom:0; width:100%; height:min(78dvh,620px); border-top:1px solid var(--line); border-left:0; border-radius:22px 22px 0 0; transform:translateY(105%); } .detail-drawer.open { transform:translateY(0); } .view-tabs { overflow:auto; padding:0 10px; } .view-tab { flex:0 0 auto; } .new-view-head { align-items:flex-start; flex-direction:column; } .detail-groups { grid-template-columns:1fr; } .detail-group { border-right:0; } .model-detail-drawer { top:auto; bottom:0; width:100%; height:min(78dvh,620px); border-top:1px solid var(--line); border-left:0; border-radius:22px 22px 0 0; transform:translateY(104%); } }
    @media print { .tools,.graph-toolbar,.drawer-scrim,.detail-drawer { display:none!important; } .model-detail-drawer { display:none!important; } .shell { width:100%; padding:0; } .intro,.model-workbench { box-shadow:none; } #graph-svg { height:580px; } }
    @media (prefers-reduced-motion:reduce) { *,*::before,*::after { scroll-behavior:auto!important; transition:none!important; } }
    :root { --type-stream:#2f6b57;--type-stream-surface:#e8f1ec;--type-work:#556ead;--type-work-surface:#edf0fb;--type-entity:#b7791f;--type-entity-surface:#fbf3e4;--type-capability:#2c7a7b;--type-capability-surface:#e8f4f3;--type-role:#7c5a91;--type-role-surface:#f4edf7;--type-requirement:#a14d67;--type-requirement-surface:#f9edf1; }
    html[data-theme="dark"] { --type-stream:#8ac4a8;--type-stream-surface:#1f352c;--type-work:#aab9ed;--type-work-surface:#252b43;--type-entity:#f0bd69;--type-entity-surface:#3a2e1a;--type-capability:#83cfca;--type-capability-surface:#1b3435;--type-role:#d1b6e1;--type-role-surface:#34263d;--type-requirement:#e6a1b6;--type-requirement-surface:#3a202c; }
    .metric.type-stream { border-color:color-mix(in srgb,var(--type-stream) 42%,var(--line)); background:var(--type-stream-surface); } .metric.type-stream b { color:var(--type-stream); } .metric.type-work { border-color:color-mix(in srgb,var(--type-work) 42%,var(--line)); background:var(--type-work-surface); } .metric.type-work b { color:var(--type-work); } .metric.type-entity { border-color:color-mix(in srgb,var(--type-entity) 42%,var(--line)); background:var(--type-entity-surface); } .metric.type-entity b { color:var(--type-entity); } .metric.type-capability { border-color:color-mix(in srgb,var(--type-capability) 42%,var(--line)); background:var(--type-capability-surface); } .metric.type-capability b { color:var(--type-capability); }
    .flow-view-grid { display:block; } .graph-filter[data-type="stream"] { --filter:var(--type-stream); } .graph-filter[data-type="work"] { --filter:var(--type-work); } .graph-filter[data-type="entity"] { --filter:var(--type-entity); } .graph-filter[data-type="capability"] { --filter:var(--type-capability); } .graph-node[data-node-type="stream"] .shape { fill:var(--type-stream)!important; } .graph-node[data-node-type="work"] .shape { fill:var(--type-work)!important; } .graph-node[data-node-type="entity"] .shape { fill:var(--type-entity)!important; } .graph-node[data-node-type="capability"] .shape { fill:var(--type-capability)!important; } .graph-edge.contains { stroke:var(--type-stream); } .graph-edge.crud { stroke:var(--type-entity); } .graph-edge.requires { stroke:var(--type-capability); } #arrow-contains path { fill:var(--type-stream); } #arrow-crud path { fill:var(--type-entity); } #arrow-requires path { fill:var(--type-capability); } .swatch.stream { --swatch:var(--type-stream); } .swatch.work { --swatch:var(--type-work); } .swatch.entity { --swatch:var(--type-entity); } .swatch.capability { --swatch:var(--type-capability); } .line.contains { border-color:var(--type-stream); } .line.crud { border-color:var(--type-entity); } .line.requires { border-color:var(--type-capability); }
    .stream-container { border-color:color-mix(in srgb,var(--type-stream) 48%,var(--line)); border-left-color:var(--type-stream); background:var(--type-stream-surface); } .stream-container:before { background:var(--type-stream); } .work-card { border-color:color-mix(in srgb,var(--type-work) 42%,var(--line)); border-left-color:var(--type-work); background:var(--type-work-surface); } .capability-container { border-color:color-mix(in srgb,var(--type-capability) 48%,var(--line)); border-left-color:var(--type-capability); background:var(--type-capability-surface); } .capability-container:before { background:var(--type-capability); } .entity-card { border-left-color:var(--type-entity); background:var(--type-entity-surface); } .requirement-map { border-color:color-mix(in srgb,var(--type-requirement) 42%,var(--line)); border-left-color:var(--type-requirement); background:var(--type-requirement-surface); } .requirement-meta span { background:color-mix(in srgb,var(--type-requirement) 12%,var(--surface)); color:var(--type-requirement); } .requirement-bridge:before { color:var(--type-requirement); }
    .association-link.type-stream,.detail-link.type-stream { border-color:color-mix(in srgb,var(--type-stream) 46%,var(--line)); background:var(--type-stream-surface); color:var(--type-stream); } .association-link.type-work,.detail-link.type-work { border-color:color-mix(in srgb,var(--type-work) 46%,var(--line)); background:var(--type-work-surface); color:var(--type-work); } .association-link.type-entity,.detail-link.type-entity { border-color:color-mix(in srgb,var(--type-entity) 46%,var(--line)); background:var(--type-entity-surface); color:var(--type-entity); } .association-link.type-capability,.detail-link.type-capability { border-color:color-mix(in srgb,var(--type-capability) 46%,var(--line)); background:var(--type-capability-surface); color:var(--type-capability); } .association-link.type-role,.detail-link.type-role { border-color:color-mix(in srgb,var(--type-role) 46%,var(--line)); background:var(--type-role-surface); color:var(--type-role); } .association-link.type-requirement,.detail-link.type-requirement { border-color:color-mix(in srgb,var(--type-requirement) 46%,var(--line)); background:var(--type-requirement-surface); color:var(--type-requirement); } .drawer-type.type-stream,.model-detail-type.type-stream { color:var(--type-stream); } .drawer-type.type-work,.model-detail-type.type-work { color:var(--type-work); } .drawer-type.type-entity,.model-detail-type.type-entity { color:var(--type-entity); } .drawer-type.type-capability,.model-detail-type.type-capability { color:var(--type-capability); } .drawer-type.type-role,.model-detail-type.type-role { color:var(--type-role); } .drawer-type.type-requirement,.model-detail-type.type-requirement { color:var(--type-requirement); }
    body,body *,body *::before,body *::after { font-size:var(--report-font-size)!important; } .graph-zoom-button,.drawer-close,.model-detail-close { font-size:20px!important; }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar"><div class="brand"><span class="brand-mark">瓜</span>完整元模型图谱</div><div class="tools"><a class="quiet" href="__SOURCE_HREF__">查看 Markdown</a><button class="quiet" id="theme-toggle" type="button">切到夜里</button><button class="quiet" id="print-button" type="button">打印 / 存为 PDF</button></div></header>
    <section class="intro"><div><p class="eyebrow">Evidence-first job intelligence / __SCHEMA__</p><h1>__TITLE__</h1><p class="summary" id="summary"></p></div><div class="metrics" id="metrics" aria-label="模型规模"></div></section>
    <nav class="view-tabs" role="tablist" aria-label="完整元模型视图"><button class="view-tab" id="relationship-tab" type="button" role="tab" aria-selected="true" aria-controls="relationship-view" data-view-target="relationship">关系图</button><button class="view-tab" id="value-stream-tab" type="button" role="tab" aria-selected="false" aria-controls="value-stream-view" data-view-target="value-stream">价值流视图</button><button class="view-tab" id="capability-tab" type="button" role="tab" aria-selected="false" aria-controls="capability-view" data-view-target="capability">能力视图</button><button class="view-tab" id="requirement-tab" type="button" role="tab" aria-selected="false" aria-controls="requirement-view" data-view-target="requirement">任职要求视图</button></nav>
    <section class="model-workbench" aria-labelledby="workbench-title"><header class="workbench-head"><div class="workbench-title"><div><h2 id="workbench-title">建模图谱</h2><span>拖拽画布；使用左下角按钮缩放；点击元素查看可追溯详情</span></div></div><span class="view-chip">关系图 · 首轮</span></header><div class="graph-toolbar" aria-label="图谱控制"><span class="toolbar-label">筛选：</span><button class="graph-filter" type="button" data-type="stream" aria-pressed="true">价值流</button><button class="graph-filter" type="button" data-type="work" aria-pressed="true">工作事项</button><button class="graph-filter" type="button" data-type="entity" aria-pressed="true">业务实体</button><button class="graph-filter" type="button" data-type="capability" aria-pressed="true">能力</button><button class="fit-graph" id="fit-graph" type="button">一屏看清</button></div><div class="graph-stage" id="graph-stage"><svg id="graph-svg" role="application" aria-label="岗位元模型关系图"></svg><div class="graph-zoom-controls" aria-label="图谱缩放"><button class="graph-zoom-button" id="graph-zoom-in" type="button" aria-controls="graph-svg" aria-label="放大图谱">+</button><button class="graph-zoom-button" id="graph-zoom-out" type="button" aria-controls="graph-svg" aria-label="缩小图谱">−</button></div><div class="tooltip" id="graph-tooltip" role="status"></div></div><div class="legend"><strong>图例</strong><span class="legend-item"><i class="swatch stream"></i>价值流</span><span class="legend-item"><i class="swatch work"></i>工作事项</span><span class="legend-item"><i class="swatch entity"></i>业务实体</span><span class="legend-item"><i class="swatch capability"></i>能力</span><span class="legend-item"><i class="line contains"></i>包含</span><span class="legend-item"><i class="line crud"></i>CRUD 操作</span><span class="legend-item"><i class="line requires"></i>需要能力</span></div><aside class="detail-drawer" id="detail-drawer" aria-label="元素详情" aria-hidden="true" tabindex="-1"><button class="drawer-close" id="drawer-close" type="button" aria-label="关闭详情">×</button><div id="drawer-content"></div></aside></section>
    <section class="model-new-view view-panel" id="value-stream-view" role="tabpanel" aria-labelledby="value-stream-tab" hidden><header class="new-view-head"><div><p class="view-kicker">ownership view / no inferred flow</p><h2>价值流视图</h2><p>价值流是工作事项的归属容器；容器之间不表示先后流向。角色责任、事项操作对象与所需能力均以局部关联呈现。</p></div></header><div class="flow-view-shell"><div class="flow-view-grid"><div class="stream-stack" id="value-stream-board"></div></div></div></section>
    <section class="model-new-view view-panel" id="capability-view" role="tabpanel" aria-labelledby="capability-tab" hidden><header class="new-view-head"><div><p class="view-kicker">ownership view / evidence-linked</p><h2>能力视图</h2><p>业务能力是实体的主归属容器；展示能力依赖、实体关联和支撑工作事项。</p></div></header><div class="capability-view-shell"><div class="capability-layout"><div class="capability-stack" id="capability-board"></div></div><div class="relation-zone"><h3>能力依赖</h3><div class="relation-list" id="capability-relations"></div></div><div class="relation-zone"><h3>实体关联</h3><div class="relation-list" id="entity-relations"></div></div></div></section>
    <section class="model-new-view view-panel" id="requirement-view" role="tabpanel" aria-labelledby="requirement-tab" hidden><header class="new-view-head"><div><p class="view-kicker">qualification map / evidence-linked</p><h2>任职要求视图</h2><p>以任职要求为起点，展示其与价值流、工作事项、角色和业务能力的已知关联；未映射项目保留为独立岗位准入条件。</p></div></header><div class="requirement-view-shell"><div class="requirement-board" id="requirement-board"></div></div></section>
    <section class="report-details" aria-labelledby="report-details-title"><header class="report-details-head"><h2 id="report-details-title">岗位信息与审阅结论</h2><p>所有字段均来自完整模型；“JD 未披露”是需要在后续沟通中确认的信息，不是负面事实。</p></header><div class="detail-groups" id="detail-groups"></div></section>
  </main>
  <aside class="model-detail-drawer" id="model-detail-drawer" aria-label="模型详情" aria-hidden="true" tabindex="-1"><button class="model-detail-close" id="model-detail-close" type="button" aria-label="关闭详情">×</button><div id="model-detail-content"></div></aside>
  <div class="drawer-scrim" id="drawer-scrim"></div>
  <script id="report-data" type="application/json">__DATA__</script>
  <script>
  (() => {
    const report = JSON.parse(document.getElementById('report-data').textContent);
    const model = report.model;
    const SVG_NS = 'http:' + '//www.w3.org/2000/svg';
    const labels = {stream:'价值流',work:'工作事项',entity:'业务实体',capability:'业务能力',contains:'包含',crud:'CRUD 操作',requires:'需要能力',context:'补充关系',create:'创建',read:'读取',update:'更新',delete:'删除',depends_on:'依赖',parent_of:'从属',lifecycle_precedes:'生命周期前序',input_to:'输入到',related_to:'相关',responsible:'执行负责',accountable:'最终负责',consulted:'被征询',informed:'被知会'};
    const evidenceLabels = {explicit:'JD 明确表达',inferred:'谨慎推断',not_disclosed:'JD 未披露'};
    const $ = (selector) => document.querySelector(selector);
    const svg = $('#graph-svg'), stage = $('#graph-stage'), tooltip = $('#graph-tooltip'), drawer = $('#detail-drawer'), scrim = $('#drawer-scrim'), drawerContent = $('#drawer-content');
    const make = (tag, className, text) => { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; };
    const svgEl = (tag, attrs = {}) => { const el = document.createElementNS(SVG_NS, tag); Object.entries(attrs).forEach(([key,value]) => el.setAttribute(key, String(value))); return el; };
    const index = (items) => Object.fromEntries((items || []).map((item) => [item.id,item]));
    const streams = index(model.value_streams), workItems = index(model.work_items), entities = index(model.business_entities), capabilities = index(model.business_capabilities), roles = index(model.roles);
    const nodes = [], nodeById = new Map(), edges = [];
    const addNode = (raw,type) => { const node = {id:raw.id,type,raw,name:raw.name || raw.id}; nodes.push(node); nodeById.set(node.id,node); return node; };
    (model.value_streams || []).forEach((item) => addNode(item,'stream')); (model.work_items || []).forEach((item) => addNode(item,'work')); (model.business_entities || []).forEach((item) => addNode(item,'entity')); (model.business_capabilities || []).forEach((item) => addNode(item,'capability'));
    const addEdge = (source,target,type,raw = {}) => { if (nodeById.has(source) && nodeById.has(target)) edges.push({source,target,type,raw}); };
    (model.work_items || []).forEach((item) => { addEdge(item.value_stream_id,item.id,'contains'); (item.entity_operations || []).forEach((operation) => addEdge(item.id,operation.entity_id,'crud',operation)); (item.capability_ids || []).forEach((id) => addEdge(item.id,id,'requires')); });
    (model.business_entities || []).forEach((item) => { if (item.primary_capability_id) addEdge(item.id,item.primary_capability_id,'context',{relation_type:'primary_capability'}); });
    (model.entity_relationships || []).forEach((relation) => addEdge(relation.source_id,relation.target_id,'context',relation)); (model.capability_relationships || []).forEach((relation) => addEdge(relation.source_id,relation.target_id,'context',relation));
    const counts = [['价值流',model.value_streams.length,'stream'],['工作事项',model.work_items.length,'work'],['业务实体',model.business_entities.length,'entity'],['业务能力',model.business_capabilities.length,'capability']];
    counts.forEach(([label,value,type]) => { const card=make('div',`metric type-${type}`); card.append(make('b','',String(value)),make('span','',label)); $('#metrics').append(card); });
    $('#summary').textContent = (report.summaryParagraphs || [])[0] || '图谱仅展示 JSON 模型中已定义的元素与关系。';
    const MIN_SCALE = .55, MAX_SCALE = 2.4, ZOOM_FACTOR = 1.15;
    const state = {filters:{stream:true,work:true,entity:true,capability:true},scale:1,tx:0,ty:0,lastTrigger:null};
    const positions = new Map(); let nodeElements = new Map(), edgeElements = [], graphLayer;
    function layout() { const width = Math.max(stage.clientWidth,720), baseHeight = Math.max(stage.clientHeight,660), cols = {stream:.11,work:.36,entity:.64,capability:.89}, rowPitch = {stream:82,work:92,entity:98,capability:98}, edgePadding = 58; const groups = Object.fromEntries(Object.keys(cols).map((type) => [type,nodes.filter((node) => node.type===type)])); const requiredHeight = Math.max(...Object.keys(cols).map((type) => { const count=groups[type].length; return count ? edgePadding * 2 + (count - 1) * rowPitch[type] : 0; }),0); const height = Math.max(baseHeight,requiredHeight); stage.style.minHeight=`${height}px`; svg.style.height=`${height}px`; svg.setAttribute('viewBox', `0 0 ${width} ${height}`); Object.keys(cols).forEach((type) => { const group=groups[type], span=Math.max(group.length - 1,0) * rowPitch[type], start=(height - span) / 2; group.forEach((node,idx) => positions.set(node.id,{x:width*cols[type],y:start + idx * rowPitch[type]})); }); return {width,height}; }
    function applyTransform() { graphLayer.setAttribute('transform',`translate(${state.tx} ${state.ty}) scale(${state.scale})`); }
    function updateZoomControls() { $('#graph-zoom-in').disabled=state.scale >= MAX_SCALE; $('#graph-zoom-out').disabled=state.scale <= MIN_SCALE; }
    function setScale(nextScale) { const scale=Math.max(MIN_SCALE,Math.min(MAX_SCALE,nextScale)); if(scale===state.scale) { updateZoomControls(); return; } const width=svg.viewBox.baseVal.width || stage.clientWidth, height=svg.viewBox.baseVal.height || stage.clientHeight, factor=scale/state.scale, cx=width/2, cy=height/2; state.tx=cx-(cx-state.tx)*factor; state.ty=cy-(cy-state.ty)*factor; state.scale=scale; applyTransform(); updateZoomControls(); }
    function shapeFor(node) { const color={stream:'var(--type-stream)',work:'var(--type-work)',entity:'var(--type-entity)',capability:'var(--type-capability)'}[node.type]; if(node.type==='stream') return svgEl('rect',{x:-52,y:-20,width:104,height:40,rx:10,fill:color}); if(node.type==='work') return svgEl('circle',{r:24,fill:color}); if(node.type==='entity') return svgEl('polygon',{points:'0,-29 29,0 0,29 -29,0',fill:color}); return svgEl('polygon',{points:'-25,-15 0,-29 25,-15 25,15 0,29 -25,15',fill:color}); }
    function truncate(value,max=10) { return value.length > max ? `${value.slice(0,max)}…` : value; }
    function draw() { const {width,height} = layout(); svg.replaceChildren(); const defs=svgEl('defs'); [['contains','var(--type-stream)'],['crud','var(--type-entity)'],['requires','var(--type-capability)'],['context','var(--muted)']].forEach(([type,color]) => { const marker=svgEl('marker',{id:`arrow-${type}`,viewBox:'0 -5 10 10',refX:10,refY:0,markerWidth:6,markerHeight:6,orient:'auto'}); marker.append(svgEl('path',{d:'M0,-4L8,0L0,4',fill:color})); defs.append(marker); }); svg.append(defs); graphLayer=svgEl('g',{id:'graph-layer'}); const edgesLayer=svgEl('g'), nodesLayer=svgEl('g'); graphLayer.append(edgesLayer,nodesLayer); svg.append(graphLayer); edgeElements=[]; nodeElements=new Map(); edges.forEach((edge) => { const source=positions.get(edge.source),target=positions.get(edge.target); const bend=(target.x-source.x)*.48; const path=svgEl('path',{d:`M ${source.x} ${source.y} C ${source.x+bend} ${source.y}, ${target.x-bend} ${target.y}, ${target.x} ${target.y}`,class:`graph-edge ${edge.type}`, 'data-edge-type':edge.type,'marker-end':`url(#arrow-${edge.type})`}); edge.element=path; edgeElements.push({edge,element:path}); edgesLayer.append(path); }); nodes.forEach((node) => { const point=positions.get(node.id), group=svgEl('g',{class:'graph-node','data-node-id':node.id,'data-node-type':node.type,tabindex:0,role:'button','aria-label':`查看${node.name}详情`,transform:`translate(${point.x} ${point.y})`}); const shape=shapeFor(node); shape.classList.add('shape'); group.append(shape); const label=svgEl('text',{class:'graph-label',y:node.type==='stream'?36:45}); label.textContent=truncate(node.name); group.append(label); group.addEventListener('pointerenter',(event) => { highlight(node.id); tooltip.replaceChildren(make('b','',node.name),make('span','',labels[node.type])); tooltip.classList.add('open'); moveTooltip(event); }); group.addEventListener('pointermove',moveTooltip); group.addEventListener('pointerleave',() => { clearHighlight(); tooltip.classList.remove('open'); }); group.addEventListener('click',(event) => { event.stopPropagation(); openDetail(node,group); }); group.addEventListener('keydown',(event) => { if(event.key==='Enter'||event.key===' '){event.preventDefault();openDetail(node,group);} }); nodeElements.set(node.id,group); nodesLayer.append(group); }); updateFilters(); applyTransform(); }
    function moveTooltip(event) { const rect=stage.getBoundingClientRect(); tooltip.style.left=`${Math.min(event.clientX-rect.left+14,rect.width-270)}px`; tooltip.style.top=`${Math.max(event.clientY-rect.top-12,8)}px`; }
    function connected(id) { const ids=new Set([id]); edges.forEach((edge) => { if(edge.source===id) ids.add(edge.target); if(edge.target===id) ids.add(edge.source); }); return ids; }
    function highlight(id) { const ids=connected(id); nodeElements.forEach((element,nodeId) => element.classList.toggle('dimmed',!ids.has(nodeId))); edgeElements.forEach(({edge,element}) => element.classList.toggle('dimmed',edge.source!==id&&edge.target!==id)); }
    function clearHighlight() { nodeElements.forEach((element) => element.classList.remove('dimmed')); edgeElements.forEach(({element}) => element.classList.remove('dimmed')); }
    function updateFilters() { nodeElements.forEach((element,id) => element.classList.toggle('hidden',!state.filters[nodeById.get(id).type])); edgeElements.forEach(({edge,element}) => element.classList.toggle('hidden',!state.filters[nodeById.get(edge.source).type]||!state.filters[nodeById.get(edge.target).type])); }
    function section(title) { const el=make('section','drawer-section'); el.append(make('h4','',title)); return el; }
    function evidenceBlock(evidence) { const box=make('div','evidence'), status=evidence && evidence.status || 'not_disclosed'; box.append(make('span',`evidence-status ${status}`,evidenceLabels[status] || status)); const quote=(evidence && evidence.snippets && evidence.snippets.length ? evidence.snippets.join('；') : evidence && evidence.inference_basis) || 'JD 未披露可核验证据。'; box.append(make('p','evidence-quote',quote)); return box; }
    function linkedNodeButton(id,prefix='') { const linked=nodeById.get(id); if(!linked) return null; const button=make('button',`detail-link type-${linked.type}`,`${prefix}${linked.name}`); button.type='button'; button.addEventListener('click',() => { const target=nodeElements.get(id); openDetail(linked,target); target && target.focus(); }); return button; }
    function nodeDescription(node) { const raw=node.raw; return raw.description || raw.definition || raw.category || raw.entity_type || raw.name || ''; }
    function relationshipRows(node) { const list=make('div','detail-list'); const direct=edges.filter((edge) => edge.source===node.id||edge.target===node.id); direct.forEach((edge) => { const otherId=edge.source===node.id?edge.target:edge.source; const relation=edge.type==='crud' ? `${labels[edge.raw.operation] || edge.raw.operation} · ` : edge.type==='context' ? `${labels[edge.raw.relation_type] || '关联'} · ` : `${labels[edge.type]} · `; const button=linkedNodeButton(otherId,relation); if(button) list.append(button); }); if(!list.children.length) list.append(make('p','drawer-copy','没有可展示的直接关联。')); return list; }
    function addSpecificDetails(node,container) { const raw=node.raw; if(node.type==='work') { const stream=linkedNodeButton(raw.value_stream_id,'所属价值流 · '); if(stream) container.append(stream); (raw.capability_ids||[]).forEach((id) => { const button=linkedNodeButton(id,'所需能力 · '); if(button) container.append(button); }); } if(node.type==='entity'&&raw.primary_capability_id) { const button=linkedNodeButton(raw.primary_capability_id,'主归属能力 · '); if(button) container.append(button); } if(node.type==='capability') (raw.supported_work_item_ids||[]).forEach((id) => { const button=linkedNodeButton(id,'支撑工作事项 · '); if(button) container.append(button); }); if(node.type==='work') { (model.responsibility_assignments||[]).filter((item) => item.work_item_id===node.id).forEach((item) => { const role=roles[item.role_id]; if(role) container.append(make('p','drawer-copy',`${labels[item.raci] || item.raci}：${role.name}`)); }); } }
    function openDetail(node,trigger) { state.lastTrigger=trigger||document.activeElement; drawerContent.replaceChildren(); drawerContent.append(make('p',`drawer-type type-${node.type}`,labels[node.type])); drawerContent.append(make('h3','',node.name)); const description=nodeDescription(node); if(description) drawerContent.append(make('p','drawer-copy',description)); const specifics=section('模型映射'); addSpecificDetails(node,specifics); if(specifics.children.length>1) drawerContent.append(specifics); const relations=section('关联元素'); relations.append(relationshipRows(node)); drawerContent.append(relations); const evidence=section('来源证据'); evidence.append(evidenceBlock(node.raw.evidence)); drawerContent.append(evidence); nodeElements.forEach((element) => element.classList.toggle('selected',element===trigger)); drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false'); }
    function closeDetail(restoreFocus=true) { drawer.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); scrim.classList.remove('open'); nodeElements.forEach((element) => element.classList.remove('selected')); if(restoreFocus&&state.lastTrigger&&state.lastTrigger.focus) state.lastTrigger.focus(); }
    document.querySelectorAll('.graph-filter').forEach((button) => button.addEventListener('click',() => { const type=button.dataset.type; state.filters[type]=!state.filters[type]; button.setAttribute('aria-pressed',String(state.filters[type])); updateFilters(); }));
    $('#fit-graph').addEventListener('click',() => { state.scale=1;state.tx=0;state.ty=0;applyTransform();updateZoomControls(); }); $('#graph-zoom-in').addEventListener('click',() => setScale(state.scale * ZOOM_FACTOR)); $('#graph-zoom-out').addEventListener('click',() => setScale(state.scale / ZOOM_FACTOR)); $('#drawer-close').addEventListener('click',() => closeDetail(true)); document.addEventListener('keydown',(event) => { if(event.key==='Escape'&&drawer.classList.contains('open')) closeDetail(true); }); document.addEventListener('click',(event) => { if(drawer.classList.contains('open')&&!drawer.contains(event.target)&&!event.target.closest('[data-node-id]')) closeDetail(false); }); document.addEventListener('model-view-change',() => closeDetail(false)); $('#theme-toggle').addEventListener('click',() => { const root=document.documentElement,next=root.dataset.theme==='dark'?'light':'dark'; root.dataset.theme=next; $('#theme-toggle').textContent=next==='dark'?'切到白天':'切到夜里'; }); $('#print-button').addEventListener('click',() => window.print());
    let pan=null; svg.addEventListener('pointerdown',(event) => { if(event.target.closest('[data-node-id]')) return; pan={x:event.clientX,y:event.clientY,tx:state.tx,ty:state.ty}; svg.classList.add('panning'); svg.setPointerCapture(event.pointerId); }); svg.addEventListener('pointermove',(event) => { if(!pan) return; state.tx=pan.tx+event.clientX-pan.x;state.ty=pan.ty+event.clientY-pan.y;applyTransform(); }); svg.addEventListener('pointerup',() => { pan=null;svg.classList.remove('panning'); }); svg.addEventListener('wheel',(event) => { if(event.ctrlKey) event.preventDefault(); },{passive:false}); ['gesturestart','gesturechange','gestureend'].forEach((type) => svg.addEventListener(type,(event) => event.preventDefault(),{passive:false}));
    draw(); window.addEventListener('resize',() => { draw(); });
  })();
  </script>
  <script>
  (() => {
    const report = JSON.parse(document.getElementById('report-data').textContent);
    const model = report.model;
    const $ = (selector) => document.querySelector(selector);
    const make = (tag, className, text) => { const el=document.createElement(tag); if(className) el.className=className; if(text !== undefined) el.textContent=text; return el; };
    const index = (items) => Object.fromEntries((items || []).map((item) => [item.id,item]));
    const streams=index(model.value_streams), works=index(model.work_items), entities=index(model.business_entities), capabilities=index(model.business_capabilities), roles=index(model.roles), requirements=index(model.qualification_requirements);
    const all={...streams,...works,...entities,...capabilities,...roles,...requirements}, types={};
    [[streams,'价值流'],[works,'工作事项'],[entities,'业务实体'],[capabilities,'业务能力'],[roles,'责任角色'],[requirements,'任职要求']].forEach(([items,label]) => Object.keys(items).forEach((id) => { types[id]=label; }));
    const elementKinds={价值流:'stream',工作事项:'work',业务实体:'entity',业务能力:'capability',责任角色:'role',任职要求:'requirement'};
    const labels={create:'创建',read:'读取',update:'更新',delete:'删除',depends_on:'依赖',parent_of:'从属',lifecycle_precedes:'生命周期前序',input_to:'输入到',related_to:'相关',responsible:'执行负责',accountable:'最终负责',consulted:'被征询',informed:'被知会',explicit:'JD 明确表达',inferred:'谨慎推断',not_disclosed:'JD 未披露'};
    const relationship=$('.model-workbench'); relationship.id='relationship-view'; relationship.setAttribute('role','tabpanel'); relationship.setAttribute('aria-labelledby','relationship-tab');
    const panels={relationship,'value-stream':$('#value-stream-view'),capability:$('#capability-view'),requirement:$('#requirement-view')}, tabs=[...document.querySelectorAll('.view-tab')];
    let closeModelDetail=() => {};
    const showView=(name) => { closeModelDetail(false); document.dispatchEvent(new Event('model-view-change')); Object.entries(panels).forEach(([key,panel]) => { panel.hidden=key !== name; }); tabs.forEach((tab) => tab.setAttribute('aria-selected',String(tab.dataset.viewTarget===name))); };
    tabs.forEach((tab) => tab.addEventListener('click',() => showView(tab.dataset.viewTarget)));
    const drawer=$('#model-detail-drawer'), drawerContent=$('#model-detail-content'); let lastTrigger=null;
    const modelDetailTriggers=new Set();
    const clearModelDetailSelection=() => modelDetailTriggers.forEach((element) => { element.classList.remove('model-detail-selected'); element.setAttribute('aria-expanded','false'); });
    const selectModelDetailTrigger=(trigger) => { clearModelDetailSelection(); if(!trigger) return; trigger.classList.add('model-detail-selected'); trigger.setAttribute('aria-expanded','true'); lastTrigger=trigger; };
    closeModelDetail=(restoreFocus=true) => { drawer.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); clearModelDetailSelection(); if(restoreFocus&&lastTrigger&&lastTrigger.focus) lastTrigger.focus(); };
    const evidence=(item) => { const value=item && item.evidence || {status:'not_disclosed'}; const section=make('section','drawer-section'); section.append(make('h4','来源证据'),make('span',`evidence-status ${value.status || 'not_disclosed'}`,labels[value.status] || value.status)); section.append(make('p','evidence-quote',(value.snippets && value.snippets.length ? value.snippets.join('；') : value.inference_basis) || 'JD 未披露可核验证据。')); return section; };
    const open=(id,trigger) => { const item=all[id]; if(!item) return; selectModelDetailTrigger(trigger || document.activeElement); drawerContent.replaceChildren(make('p',`model-detail-type type-${elementKinds[types[id]] || 'neutral'}`,types[id] || '审阅结论'),make('h3','',item.name || id)); const description=item.description || item.category || item.domain || item.content_category; if(description) drawerContent.append(make('p','',description)); if(types[id]==='工作事项') { const stream=streams[item.value_stream_id], operations=(item.entity_operations || []).map((operation) => `${labels[operation.operation] || operation.operation} · ${entities[operation.entity_id] && entities[operation.entity_id].name || operation.entity_id}`), needs=(item.capability_ids || []).map((capabilityId) => capabilities[capabilityId] && capabilities[capabilityId].name || capabilityId), raci=(model.responsibility_assignments || []).filter((assignment) => assignment.work_item_id===item.id).map((assignment) => `${assignment.raci && assignment.raci.toUpperCase() || 'R'} · ${roles[assignment.role_id] && roles[assignment.role_id].name || assignment.role_id}`); drawerContent.append(make('p','drawer-copy',stream ? `所属价值流：${stream.name}` : '所属价值流：JD 未披露')); drawerContent.append(make('p','drawer-copy',`CRUD 实体：${operations.join('；') || 'JD 未披露'}`),make('p','drawer-copy',`所需能力：${needs.join('、') || 'JD 未披露'}`),make('p','drawer-copy',`责任分配：${raci.join('、') || 'JD 未披露'}`)); } if(types[id]==='业务实体' && item.primary_capability_id) drawerContent.append(make('p','drawer-copy',`主归属能力：${capabilities[item.primary_capability_id] && capabilities[item.primary_capability_id].name || item.primary_capability_id}`)); if(types[id]==='任职要求') drawerContent.append(make('p','drawer-copy',(item.mapping_target_ids || []).length ? `映射对象：${item.mapping_target_ids.map((target) => all[target] && all[target].name || target).join('、')}` : '岗位准入条件：未映射具体模型对象。')); drawerContent.append(evidence(item)); drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false'); };
    const bindModelDetailTrigger=(element,openTrigger) => { element.dataset.modelDetailTrigger='true'; element.classList.add('model-detail-trigger'); element.setAttribute('aria-controls','model-detail-drawer'); element.setAttribute('aria-expanded','false'); modelDetailTriggers.add(element); if(element.tagName!=='BUTTON') { element.tabIndex=0; element.setAttribute('role','button'); element.addEventListener('keydown',(event) => { if(event.key==='Enter'||event.key===' ') { event.preventDefault(); openTrigger(event); } }); } element.addEventListener('click',(event) => { event.stopPropagation(); openTrigger(event); }); return element; };
    $('#model-detail-close').addEventListener('click',() => closeModelDetail(true)); document.addEventListener('keydown',(event) => { if(event.key==='Escape'&&drawer.classList.contains('open')) closeModelDetail(true); }); document.addEventListener('click',(event) => { if(drawer.classList.contains('open')&&!drawer.contains(event.target)&&!event.target.closest('[data-model-detail-trigger]')) closeModelDetail(false); });
    const targetView=(id) => ['价值流','工作事项','责任角色'].includes(types[id]) ? 'value-stream' : ['业务实体','业务能力'].includes(types[id]) ? 'capability' : types[id]==='任职要求' ? 'requirement' : null;
    const link=(id,text,kind='',stayInView=false) => { const legacyKinds={crud:'type-entity',capability:'type-capability',role:'type-role'}, typeClass=legacyKinds[kind] || kind || `type-${elementKinds[types[id]] || 'neutral'}`; const button=make('button',`association-link ${typeClass}`,text || all[id] && all[id].name || id); button.type='button'; return bindModelDetailTrigger(button,() => { const target=targetView(id); if(target && !stayInView) showView(target); requestAnimationFrame(() => open(id,button)); }); };
    const empty=(text) => make('p','empty-state',text);
    const association=(label,buttons) => { const row=make('div','association-row'); row.append(make('span','association-label',label)); const links=make('div','association-links'); buttons.forEach((button) => links.append(button)); row.append(links); return row; };
    const renderValue=() => {
      const board=$('#value-stream-board'), assignments=model.responsibility_assignments || []; board.replaceChildren();
      if(!(model.value_streams || []).length) board.append(empty('JD 未建模出价值流。'));
      (model.value_streams || []).forEach((stream) => { const container=make('section','stream-container'); container.append(make('h3','',stream.name)); const streamWorks=(model.work_items || []).filter((work) => work.value_stream_id===stream.id); if(!streamWorks.length) container.append(empty('该价值流没有已建模工作事项。')); streamWorks.forEach((work) => { const card=make('article','work-card'); card.append(make('h4','',work.name)); const operations=(work.entity_operations || []).map((operation) => link(operation.entity_id,`${labels[operation.operation] || operation.operation} · ${entities[operation.entity_id] && entities[operation.entity_id].name || operation.entity_id}`,'crud',true)); if(operations.length) card.append(association('CRUD 实体',operations)); const needs=(work.capability_ids || []).map((id) => link(id,capabilities[id] && capabilities[id].name || id,'capability',true)); if(needs.length) card.append(association('所需能力',needs)); const workRoles=assignments.filter((assignment) => assignment.work_item_id===work.id).map((assignment) => link(assignment.role_id,`${assignment.raci && assignment.raci.toUpperCase() || 'R'} · ${roles[assignment.role_id] && roles[assignment.role_id].name || assignment.role_id}`,'role',true)); card.append(association('执行角色',workRoles.length ? workRoles : [empty('JD 未明确执行角色。')])); bindModelDetailTrigger(card,() => open(work.id,card)); container.append(card); }); bindModelDetailTrigger(container,() => open(stream.id,container)); board.append(container); });
    };
    const relationCard=(relation, source,target) => { const directional=['depends_on','input_to','parent_of','lifecycle_precedes'].includes(relation.relation_type); const card=make('article',`relation-card${directional ? '' : ' is-neutral'}`); card.append(link(relation.source_id,source[relation.source_id] && source[relation.source_id].name || relation.source_id),make('span','relation-arrow',directional ? `→ ${labels[relation.relation_type] || relation.relation_type} →` : `— ${labels[relation.relation_type] || relation.relation_type} —`),link(relation.target_id,target[relation.target_id] && target[relation.target_id].name || relation.target_id)); return card; };
    const renderCapability=() => {
      const board=$('#capability-board'), capRelations=$('#capability-relations'), entityRelations=$('#entity-relations'); board.replaceChildren(); capRelations.replaceChildren(); entityRelations.replaceChildren();
      if(!(model.business_capabilities || []).length) board.append(empty('JD 未建模出业务能力。'));
      (model.business_capabilities || []).forEach((capability) => { const container=make('section','capability-container'); container.append(make('h3','',capability.name)); const owned=(model.business_entities || []).filter((entity) => entity.primary_capability_id===capability.id); if(!owned.length) container.append(empty('没有主归属到该能力的业务实体。')); owned.forEach((entity) => { const card=make('article','entity-card'); card.append(make('strong','',entity.name)); if(entity.domain) card.append(make('p','empty-state',entity.domain)); bindModelDetailTrigger(card,() => open(entity.id,card)); container.append(card); }); const supported=(capability.supported_work_item_ids || []).map((id) => works[id]).filter(Boolean); if(supported.length) container.append(association('支撑工作事项',supported.map((work) => link(work.id,work.name,'',true)))); bindModelDetailTrigger(container,() => open(capability.id,container)); board.append(container); });
      const capabilityRelations=model.capability_relationships || [], entityRelationships=model.entity_relationships || []; capabilityRelations.length ? capabilityRelations.forEach((relation) => capRelations.append(relationCard(relation,capabilities,capabilities))) : capRelations.append(empty('JD 未建模出能力依赖。')); entityRelationships.length ? entityRelationships.forEach((relation) => entityRelations.append(relationCard(relation,entities,entities))) : entityRelations.append(empty('JD 未建模出实体关联。'));
    };
    const renderRequirements=() => { const board=$('#requirement-board'); board.replaceChildren(); if(!(model.qualification_requirements || []).length) { board.append(empty('JD 未建模出任职要求。')); return; } (model.qualification_requirements || []).forEach((requirement) => { const targets=(requirement.mapping_target_ids || []).filter((id) => all[id]); const row=make('article',`requirement-map${targets.length ? '' : ' is-independent'}`), source=make('button','requirement-trigger'); source.type='button'; source.append(make('strong','',requirement.name)); const meta=make('div','requirement-meta'); [requirement.necessity==='mandatory'?'硬性要求':requirement.necessity==='preferred'?'加分项':'要求强度待确认',requirement.content_category || '类别未说明',requirement.objectivity==='objective'?'客观条件':'主观能力',requirement.mapping_status || '映射状态未说明'].forEach((value) => meta.append(make('span','',value))); source.append(meta); bindModelDetailTrigger(source,() => open(requirement.id,source)); const bridge=make('p','requirement-bridge',targets.length ? `关联层级：${requirement.association_level || '未说明'}` : '岗位准入条件'); const targetBox=make('div','requirement-targets'); if(targets.length) targets.forEach((id) => targetBox.append(link(id,`${types[id]} · ${all[id].name}`, '', true))); else targetBox.append(make('span','field-status','未映射具体模型对象')); row.append(source,bridge,targetBox); board.append(row); }); };
    const renderDetails=() => {
      const groups=$('#detail-groups'); groups.replaceChildren(); [['公司上下文',model.company_context && model.company_context.fields],['岗位画像',model.job_profile && model.job_profile.fields],['工作环境',model.work_environment && model.work_environment.fields],['薪酬福利',model.compensation_benefits && model.compensation_benefits.fields]].forEach(([title,fields]) => { const group=make('section','detail-group'); group.append(make('h3','',title)); const entries=Object.entries(fields || {}); if(!entries.length) group.append(empty('JD 未披露相关字段。')); entries.forEach(([key,value]) => { const row=make('button','fact-row'); row.type='button'; row.append(make('b','',key.replace(/_/g,' ')),make('span','',value && value.value || labels[value && value.status] || labels.not_disclosed)); bindModelDetailTrigger(row,() => { selectModelDetailTrigger(row); drawerContent.replaceChildren(make('p','model-detail-type',title),make('h3','',key.replace(/_/g,' ')),make('p','',value && value.value || labels[value && value.status] || labels.not_disclosed),evidence({evidence:value})); drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false'); }); group.append(row); }); groups.append(group); });
      [['风险',model.risks || [],'risk'],['待确认事项',model.uncertainties || [],'uncertainty']].forEach(([title,items,kind]) => { const group=make('section','detail-group'); group.append(make('h3','',title)); if(!items.length) group.append(empty('没有已建模项目。')); items.forEach((item) => { all[item.id]=item; types[item.id]=title; const card=make('button',`analysis-card ${kind}`); card.type='button'; card.append(make('strong','',item.name),make('p','',item.description || 'JD 未披露具体说明。')); bindModelDetailTrigger(card,() => open(item.id,card)); group.append(card); }); groups.append(group); });
    };
    renderValue(); renderCapability(); renderRequirements(); renderDetails(); showView('relationship');
  })();
  </script>
</body>
</html>'''
    embedded = _embedded_json(
        {
            "title": payload.title,
            "summaryParagraphs": payload.summary_paragraphs,
            "model": payload.model,
            "sourceHref": source_href,
        }
    )
    return (
        template.replace("__TITLE__", html.escape(payload.title))
        .replace("__SOURCE_HREF__", html.escape(source_href, quote=True))
        .replace("__SCHEMA__", html.escape(SCHEMA_VERSION))
        .replace("__DATA__", embedded)
    )


def render_file(input_path: Path, output_path: Path, force: bool = False) -> None:
    """Read a report and atomically write its visual companion after all validation succeeds."""
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if not input_path.is_file():
        raise ReportRenderError(f"输入报告不存在：{input_path}")
    if output_path == input_path:
        raise ReportRenderError("输出文件不能覆盖输入 Markdown 报告")
    if not output_path.parent.is_dir():
        raise ReportRenderError(f"输出目录不存在：{output_path.parent}")
    if output_path.exists() and not force:
        raise ReportRenderError(f"输出文件已存在：{output_path}；如确认覆盖，请传入 --force")
    payload = extract_report_payload(input_path.read_text(encoding="utf-8"))
    source_href = os.path.relpath(input_path, output_path.parent)
    output_path.write_text(build_html(payload, source_href), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从完整元模型 Markdown 报告生成独立 HTML")
    parser.add_argument("report", type=Path, help="含有唯一 JSON 附录的 Markdown 报告")
    parser.add_argument("--output", required=True, type=Path, help="显式指定 HTML 输出路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 HTML 输出")
    args = parser.parse_args(argv)
    try:
        render_file(args.report, args.output, force=args.force)
    except ReportRenderError as exc:
        parser.error(str(exc))
    print(f"已生成完整元模型可视化报告：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
