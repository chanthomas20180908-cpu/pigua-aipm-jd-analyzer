#!/usr/bin/env python3
"""目的：render_trace_html.py 开发辅助脚本。

定义：scripts/render_trace_html.py 是本地验证或调试脚本。

范围包括：
- 从项目根目录运行的开发辅助逻辑。

范围不包括：
- 不作为线上服务入口。

使用与修改规则：
- 脚本依赖项目路径时使用 Path 定位，避免依赖当前 shell 的偶然状态。

Usage:
    python3 scripts/render_trace_html.py [path/to/trace.md]

If no path is given, defaults to the hardcoded DEFAULT_LOG.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = REPO_ROOT / "logs" / "xxx.md"


def extract_json_blocks(text: str) -> list[Dict[str, Any]]:
    """Extract all top-level JSON objects from markdown code fences."""
    blocks: list[Dict[str, Any]] = []
    for match in re.finditer(r"```(?:json)?\n(.*?)\n```", text, re.DOTALL):
        content = match.group(1).strip()
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            continue
        try:
            blocks.append(json.loads(content[start : end + 1]))
        except json.JSONDecodeError:
            continue
    return blocks


def find_block(blocks: list[Dict[str, Any]], key_path: list[str]) -> Dict[str, Any] | None:
    for block in blocks:
        cur = block
        for key in key_path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                cur = None
                break
        if cur is not None:
            return block
    return None


def find_final_block(blocks: list[Dict[str, Any]]) -> Dict[str, Any] | None:
    for block in blocks:
        if (
            isinstance(block, dict)
            and "recommendation" in block
            and "conclusion_label" in block
            and "supplements" in block
        ):
            return block
    return None


def escape(s: Any) -> str:
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def json_var(name: str, data: Any) -> str:
    return f"const {name} = {json.dumps(data, ensure_ascii=False)};"


def mermaid_id(s: str) -> str:
    """Make a Mermaid-safe node ID."""
    return re.sub(r"[^a-zA-Z0-9]", "_", str(s))


def escape_mermaid(s: Any) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", " ")
    )


def _task_card(t: Dict[str, Any]) -> str:
    inputs = ", ".join(escape(x) for x in (t.get("inputs") or [])[:4]) or "—"
    outputs = ", ".join(escape(x) for x in (t.get("outputs") or [])[:4]) or "—"
    scope_in = "、".join(escape(x) for x in (t.get("scope_includes") or [])[:4]) or "—"
    scope_ex = "、".join(escape(x) for x in (t.get("scope_excludes") or [])[:4]) or "—"
    return f"""
      <div class="task">
        <div class="task-header">
          <span class="task-name">{escape(t.get("task_name"))}</span>
          <span class="task-id">{escape(t.get("task_id"))}</span>
        </div>
        <div class="task-field"><strong>目的：</strong>{escape(t.get("purpose"))}</div>
        <div class="task-field"><strong>定义：</strong>{escape(t.get("definition"))}</div>
        <div class="task-field"><strong>范围包括：</strong>{scope_in}</div>
        <div class="task-field"><strong>范围不包括：</strong>{scope_ex}</div>
        <div class="io-row">
          <div class="io-box input"><strong>输入</strong><br>{inputs}</div>
          <div class="io-arrow">→</div>
          <div class="io-box output"><strong>输出</strong><br>{outputs}</div>
        </div>
      </div>
    """


def _activity_card(a: Dict[str, Any]) -> str:
    tasks = "".join(_task_card(t) for t in (a.get("tasks") or []))
    scope_in = "、".join(escape(x) for x in (a.get("scope_includes") or [])[:4]) or "—"
    scope_ex = "、".join(escape(x) for x in (a.get("scope_excludes") or [])[:4]) or "—"
    return f"""
      <details class="activity">
        <summary>
          <span class="aid">{escape(a.get("activity_id"))}</span>
          <span class="aname">{escape(a.get("activity_name"))}</span>
          <span class="aseq">seq {escape(a.get("sequence"))}</span>
        </summary>
        <div class="activity-body">
          <div class="field"><strong>目的：</strong>{escape(a.get("purpose"))}</div>
          <div class="field"><strong>定义：</strong>{escape(a.get("definition"))}</div>
          <div class="field"><strong>范围包括：</strong>{scope_in}</div>
          <div class="field"><strong>范围不包括：</strong>{scope_ex}</div>
          <div class="tasks">{tasks}</div>
        </div>
      </details>
    """


def _component_card(c: Dict[str, Any]) -> str:
    tasks_html = ""
    for t in (c.get("tasks") or []):
        inputs = ", ".join(escape(x) for x in (t.get("inputs") or [])[:4]) or "—"
        outputs = ", ".join(escape(x) for x in (t.get("outputs") or [])[:4]) or "—"
        scope_in = "、".join(escape(x) for x in (t.get("scope_includes") or [])[:4]) or "—"
        scope_ex = "、".join(escape(x) for x in (t.get("scope_excludes") or [])[:4]) or "—"
        conf = t.get("confidence")
        conf_html = f'<span class="conf">置信度：{escape(conf)}</span>' if conf is not None else ""
        tasks_html += f"""
          <div class="cap-task">
            <div class="cap-task-name">{escape(t.get("task_name"))}</div>
            <div class="cap-task-field"><strong>目的：</strong>{escape(t.get("purpose"))}</div>
            <div class="cap-task-field"><strong>定义：</strong>{escape(t.get("definition"))}</div>
            <div class="cap-task-field"><strong>范围包括：</strong>{scope_in}</div>
            <div class="cap-task-field"><strong>范围不包括：</strong>{scope_ex}</div>
            <div class="io-row small">
              <div class="io-box input"><strong>输入</strong><br>{inputs}</div>
              <div class="io-arrow">→</div>
              <div class="io-box output"><strong>输出</strong><br>{outputs}</div>
            </div>
            {conf_html}
            <div class="evidence">{escape(t.get("evidence_text"))}</div>
          </div>
        """
    return f"""
      <div class="component-card">
        <div class="component-name">{escape(c.get("component_name"))}</div>
        <div class="component-tasks">{tasks_html}</div>
      </div>
    """


def _best_jd_task(text: str, jd_tasks: list[Dict[str, Any]]) -> str | None:
    text = str(text)
    best_score, best_id = 0, None
    for t in jd_tasks:
        score = 0
        if t["task_name"] in text:
            score += 3
        if t.get("activity_name", "") in text:
            score += 1
        if score > best_score:
            best_score, best_id = score, t["task_id"]
    return best_id if best_score > 0 else None


def _best_resume_task(text: str, components: list[Dict[str, Any]]) -> tuple[str | None, str | None]:
    text = str(text)
    best_score, best_result = 0, (None, None)
    for c in components:
        for t in (c.get("tasks") or []):
            score = 0
            if t.get("task_name", "") in text:
                score += 3
            if c.get("component_name", "") in text:
                score += 1
            if score > best_score:
                best_score, best_result = score, (c.get("component_name"), t.get("task_name"))
    return best_result if best_score > 0 else (None, None)


def derive_links(
    activities: list[Dict[str, Any]],
    components: list[Dict[str, Any]],
    task_mappings: list[Dict[str, Any]] | None,
    match_points: list[str],
    gaps: list[str],
    supplements: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build JD task <-> resume task links. Prefer explicit task_mappings; fallback to heuristic."""
    jd_tasks: list[Dict[str, Any]] = []
    for a in activities:
        for t in (a.get("tasks") or []):
            jd_tasks.append(
                {
                    "activity_id": a.get("activity_id"),
                    "task_id": t.get("task_id"),
                    "task_name": t.get("task_name"),
                    "activity_name": a.get("activity_name"),
                }
            )

    resume_tasks: list[Dict[str, Any]] = []
    for c in components:
        for t in (c.get("tasks") or []):
            resume_tasks.append(
                {"component": c.get("component_name"), "task_name": t.get("task_name")}
            )

    matched: list[Dict[str, Any]] = []
    matched_jd_ids: set[str] = set()
    matched_resume_keys: set[tuple[str, str]] = set()

    if task_mappings:
        for m in (task_mappings or []):
            rel = m.get("relationship")
            if rel == "no_match":
                continue
            jd_id = m.get("jd_task_id")
            comp = m.get("resume_component")
            task = m.get("resume_task")
            if not jd_id or not comp or not task:
                continue
            matched.append(
                {
                    "jd_task_id": jd_id,
                    "resume_component": comp,
                    "resume_task": task,
                    "relationship": rel,
                    "source": "task_mapping",
                }
            )
            matched_jd_ids.add(jd_id)
            matched_resume_keys.add((comp, task))
    else:
        # Fallback heuristic 1: supplements that mention a JD task ID
        for sup in (supplements or []):
            target = str(sup.get("target", ""))
            m = re.search(r"([A-Z]\d+-T\d+)", target)
            if not m:
                continue
            jd_id = m.group(1)
            desc = sup.get("description", "")
            comp, task = _best_resume_task(desc, components)
            if comp and task:
                rel_type = {
                    "missed_match": "partial_match",
                    "overclaimed_gap": "overclaimed",
                    "hard_requirement": "gap",
                    "context_missing": "related",
                    "other": "related",
                }.get(sup.get("type"), "related")
                matched.append(
                    {
                        "jd_task_id": jd_id,
                        "resume_component": comp,
                        "resume_task": task,
                        "relationship": rel_type,
                        "source": "supplement",
                    }
                )
                matched_jd_ids.add(jd_id)
                matched_resume_keys.add((comp, task))

        # Fallback heuristic 2: match_points text overlap
        for mp in (match_points or []):
            jd_id = _best_jd_task(mp, jd_tasks)
            comp, task = _best_resume_task(mp, components)
            if jd_id and comp and task:
                matched.append(
                    {
                        "jd_task_id": jd_id,
                        "resume_component": comp,
                        "resume_task": task,
                        "relationship": "direct_match",
                        "source": "match_point",
                    }
                )
                matched_jd_ids.add(jd_id)
                matched_resume_keys.add((comp, task))

    unmatched_jd = [t for t in jd_tasks if t["task_id"] not in matched_jd_ids]
    unmatched_resume = [t for t in resume_tasks if (t["component"], t["task_name"]) not in matched_resume_keys]

    return {"matched": matched, "unmatched_jd": unmatched_jd, "unmatched_resume": unmatched_resume}


def build_activity_diagram(activities: list[Dict[str, Any]]) -> str:
    lines = ["flowchart LR"]
    for a in activities:
        aid = mermaid_id(a.get("activity_id"))
        lines.append(f'  {aid}["{escape_mermaid(a.get("activity_name"))}"]')
    sorted_activities = sorted(activities, key=lambda x: x.get("sequence", 0))
    for i in range(1, len(sorted_activities)):
        prev = mermaid_id(sorted_activities[i - 1].get("activity_id"))
        cur = mermaid_id(sorted_activities[i].get("activity_id"))
        lines.append(f"  {prev} --> {cur}")
    for a in sorted_activities:
        src = mermaid_id(a.get("activity_id"))
        for target in (a.get("feedback_to_activities") or []):
            lines.append(f"  {src} -.-> {mermaid_id(target)}")
    lines.append("  classDef activityNode fill:#e6f4ff,stroke:#3b82f6,stroke-width:2px")
    for a in sorted_activities:
        lines.append(f'  class {mermaid_id(a.get("activity_id"))} activityNode')
    return "\n".join(lines)


def build_capability_diagram(components: list[Dict[str, Any]]) -> str:
    lines = ["flowchart TB"]
    colors = [
        ("#f5f3ff", "#8b5cf6"),
        ("#ecfdf5", "#10b981"),
        ("#fffbeb", "#f59e0b"),
        ("#eff6ff", "#3b82f6"),
        ("#fdf2f8", "#ec4899"),
        ("#f0fdfa", "#14b8a6"),
    ]
    for idx, c in enumerate(components):
        cid = mermaid_id("C_" + str(c.get("component_name")))
        lines.append(f'  subgraph {cid}["{escape_mermaid(c.get("component_name"))}"]')
        for t in (c.get("tasks") or []):
            tid = mermaid_id("RES_" + str(c.get("component_name")) + "_" + str(t.get("task_name")))
            lines.append(f'    {tid}["{escape_mermaid(t.get("task_name"))}"]')
        lines.append("  end")
        fill, stroke = colors[idx % len(colors)]
        lines.append(f"  style {cid} fill:{fill},stroke:{stroke},stroke-width:2px")
    return "\n".join(lines)


def build_match_diagram(links: Dict[str, Any]) -> str:
    jd_tasks = links.get("unmatched_jd", []) + [m for m in links.get("matched", [])]
    # Build a deduped jd task list
    jd_task_map: Dict[str, Dict[str, Any]] = {}
    for t in links.get("unmatched_jd", []):
        jd_task_map[t["task_id"]] = t
    resume_task_map: Dict[tuple[str, str], Dict[str, Any]] = {}
    for t in links.get("unmatched_resume", []):
        resume_task_map[(t["component"], t["task_name"])] = t
    for m in links.get("matched", []):
        jd_task_map.setdefault(
            m["jd_task_id"], {"task_id": m["jd_task_id"], "task_name": "", "activity_name": ""}
        )
        resume_task_map.setdefault(
            (m["resume_component"], m["resume_task"]),
            {"component": m["resume_component"], "task_name": m["resume_task"]},
        )

    lines = ["flowchart LR"]
    lines.append('  subgraph JDTasks["JD 任务"]')
    for tid, t in jd_task_map.items():
        node_id = mermaid_id("JD_" + tid)
        label = escape_mermaid(f"{tid} {t.get('task_name', '')}").strip()
        lines.append(f'    {node_id}["{label}"]')
    lines.append("  end")

    lines.append('  subgraph ResTasks["简历能力任务"]')
    for (comp, task), t in resume_task_map.items():
        node_id = mermaid_id("RES_" + comp + "_" + task)
        label = escape_mermaid(task)
        lines.append(f'    {node_id}["{label}"]')
    lines.append("  end")

    edge_styles: list[str] = []
    seen_edges: set[tuple[str, str]] = set()
    edge_index = 0
    for lk in links.get("matched", []):
        jd_id = mermaid_id("JD_" + lk["jd_task_id"])
        res_id = mermaid_id("RES_" + lk["resume_component"] + "_" + lk["resume_task"])
        edge_key = (jd_id, res_id)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        rel = escape_mermaid(lk.get("relationship", ""))
        lines.append(f'  {jd_id} -- "{rel}" --> {res_id}')
        rel_raw = lk.get("relationship", "")
        if rel_raw == "direct_match":
            style = "stroke:#10b981,stroke-width:2px"
        elif rel_raw == "partial_match":
            style = "stroke:#f59e0b,stroke-width:2px,stroke-dasharray: 5 5"
        elif rel_raw == "related":
            style = "stroke:#3b82f6,stroke-width:2px,stroke-dasharray: 3 3"
        elif rel_raw in ("overclaimed", "gap"):
            style = "stroke:#ef4444,stroke-width:2px,stroke-dasharray: 3 3"
        else:
            style = "stroke:#6b7280,stroke-width:1px"
        edge_styles.append(f"linkStyle {edge_index} {style}")
        edge_index += 1

    for t in links.get("unmatched_jd", []):
        node_id = mermaid_id("JD_" + t["task_id"])
        lines.append(f"  style {node_id} fill:#fef2f2,stroke:#ef4444,stroke-width:2px")
    for t in links.get("unmatched_resume", []):
        node_id = mermaid_id("RES_" + t["component"] + "_" + t["task_name"])
        lines.append(f"  style {node_id} fill:#f3f4f6,stroke:#9ca3af,stroke-width:2px")

    lines.extend(edge_styles)
    return "\n".join(lines)


CSS = """
    :root {
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #e5e7eb;
      --blue: #3b82f6;
      --blue-light: #eff6ff;
      --green: #10b981;
      --green-light: #ecfdf5;
      --amber: #f59e0b;
      --amber-light: #fffbeb;
      --red: #ef4444;
      --red-light: #fef2f2;
      --purple: #8b5cf6;
      --purple-light: #f5f3ff;
    }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; line-height: 1.6; }
    .container { max-width: 1400px; margin: 0 auto; }
    h1 { font-size: 22px; margin-bottom: 8px; }
    .subtitle { color: var(--muted); margin-bottom: 24px; }
    .summary-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .summary-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .summary-card h3 { margin: 0 0 8px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .summary-card p { margin: 0; font-size: 15px; }
    section { margin-bottom: 40px; }
    h2 { font-size: 18px; border-left: 4px solid var(--blue); padding-left: 10px; margin: 24px 0 16px; }
    h3 { font-size: 15px; margin: 20px 0 10px; }
    .value-stream { background: linear-gradient(90deg, var(--blue-light), var(--purple-light)); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    .value-stream h3 { margin: 0 0 8px; color: var(--purple); }
    .value-stream .field { font-size: 13px; margin-bottom: 6px; }
    .mermaid { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    details.activity { background: var(--card); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 12px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    details.activity summary { cursor: pointer; padding: 14px 16px; background: #fafafa; font-weight: 600; list-style: none; display: flex; gap: 12px; align-items: center; }
    details.activity summary::-webkit-details-marker { display: none; }
    details.activity summary .aid { color: var(--muted); font-size: 12px; font-family: monospace; }
    details.activity summary .aname { flex: 1; }
    details.activity summary .aseq { font-weight: normal; color: var(--muted); font-size: 12px; }
    .activity-body { padding: 16px; border-top: 1px solid var(--border); }
    .field { font-size: 13px; margin-bottom: 8px; }
    .tasks { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 12px; }
    .task { border: 1px solid var(--border); border-radius: 10px; padding: 12px; background: #fafafa; }
    .task-header { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
    .task-name { font-weight: 600; font-size: 14px; }
    .task-id { font-size: 11px; color: var(--muted); font-family: monospace; }
    .task-field { font-size: 12px; color: var(--text); margin-bottom: 4px; }
    .io-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
    .io-row.small { margin-top: 8px; }
    .io-box { flex: 1; min-width: 80px; background: var(--blue-light); border: 1px solid #bfdbfe; border-radius: 8px; padding: 8px; font-size: 12px; }
    .io-box.output { background: var(--purple-light); border-color: #ddd6fe; }
    .io-arrow { color: var(--muted); font-size: 14px; }
    .component-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .component-name { font-weight: 700; font-size: 16px; margin-bottom: 12px; color: var(--purple); }
    .component-tasks { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
    .cap-task { border: 1px solid var(--border); border-radius: 10px; padding: 12px; background: #fafafa; }
    .cap-task-name { font-weight: 600; font-size: 14px; margin-bottom: 6px; }
    .cap-task-field { font-size: 12px; margin-bottom: 4px; }
    .conf { font-size: 12px; color: var(--muted); margin-top: 6px; }
    .evidence { font-size: 12px; color: var(--muted); border-left: 3px solid var(--border); padding-left: 8px; margin-top: 8px; }
    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
    .simple-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; font-size: 13px; }
    .simple-title { font-weight: 600; margin-bottom: 6px; }
    .simple-title .meta { font-weight: normal; color: var(--muted); }
    .simple-row { margin-bottom: 4px; }
    .tag { font-size: 11px; padding: 2px 6px; border-radius: 999px; background: var(--blue-light); color: var(--blue); border: 1px solid #bfdbfe; margin-left: 4px; }
    .tag.high { background: var(--green-light); color: var(--green); border-color: #a7f3d0; }
    .tag.medium { background: var(--amber-light); color: var(--amber); border-color: #fde68a; }
    .tag.low { background: var(--red-light); color: var(--red); border-color: #fecaca; }
    .match-box { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px; }
    .match-box h4 { margin: 0 0 8px; }
    .match-box ul { margin: 0; padding-left: 18px; font-size: 13px; }
    .match-box li { margin-bottom: 4px; }
    .strength { color: var(--green); }
    .weak { color: var(--red); }
    .match-legend { display: flex; gap: 16px; margin-top: 12px; font-size: 12px; flex-wrap: wrap; }
    .legend-item { display: flex; align-items: center; gap: 6px; }
    .legend-item::before { content: ""; width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
    .legend-item.matched::before { background: var(--green); }
    .legend-item.partial::before { background: var(--amber); }
    .legend-item.related::before { background: var(--blue); }
    .legend-item.unmatched-jd::before { background: var(--red-light); border: 1px solid var(--red); }
    .legend-item.unmatched-res::before { background: #f3f4f6; border: 1px solid #9ca3af; }
    .conclusion-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
    .conclusion-badge { font-size: 20px; font-weight: 700; padding: 8px 20px; border-radius: 999px; background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; }
    .recommendation { font-size: 16px; padding: 6px 14px; border-radius: 8px; background: var(--amber-light); color: var(--amber); border: 1px solid #fde68a; }
    .match-score { font-size: 28px; font-weight: 700; color: var(--blue); }
    .match-score::before { content: "匹配度 "; font-size: 14px; font-weight: 400; color: var(--muted); }
    .summary-box { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; font-size: 15px; line-height: 1.8; margin-bottom: 20px; }
    .conclusion-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .conclusion-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
    .conclusion-card.strengths { border-left: 4px solid var(--green); }
    .conclusion-card.risks { border-left: 4px solid var(--red); }
    .conclusion-card.next-actions { border-left: 4px solid var(--blue); }
    .conclusion-card h4 { margin: 0 0 10px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); }
    .conclusion-card ul { margin: 0; padding-left: 18px; font-size: 13px; }
    .conclusion-card li { margin-bottom: 6px; }
    .supplements-section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
    .supplements-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .supplements-table th { text-align: left; padding: 10px 8px; border-bottom: 2px solid var(--border); color: var(--muted); font-weight: 600; }
    .supplements-table td { padding: 10px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
    .supplements-table tr:last-child td { border-bottom: none; }
    .type-badge { font-size: 11px; padding: 2px 8px; border-radius: 999px; display: inline-block; white-space: nowrap; }
    .type-missed_match { background: var(--green-light); color: var(--green); }
    .type-overclaimed_gap { background: var(--purple-light); color: var(--purple); }
    .type-hard_requirement { background: var(--red-light); color: var(--red); }
    .type-context_missing { background: var(--amber-light); color: var(--amber); }
    .type-other { background: #f3f4f6; color: #6b7280; }
"""


def render_html(
    jd_block: Dict[str, Any], candidate_block: Dict[str, Any], final_block: Dict[str, Any]
) -> str:
    jd = jd_block.get("job_analysis", {})
    cand = candidate_block.get("candidate_analysis", {})
    final = final_block or {}
    business_flow = jd.get("business_flow") or {}
    value_stream = business_flow.get("value_stream") or {}
    activities = business_flow.get("activities") or []
    candidate_evidence = cand.get("candidate_evidence") or {}
    components = candidate_evidence.get("modeled_capabilities") or []
    task_mappings = candidate_evidence.get("task_mappings")
    match_points = cand.get("match_points") or []
    gaps = cand.get("gaps") or []
    supplements = final.get("supplements") or []

    activity_cards = "".join(_activity_card(a) for a in activities)
    component_cards = "".join(_component_card(c) for c in components)

    incomplete_cards = "".join(
        f"""
      <div class="simple-card">
        <div class="simple-title">{escape(c.get("capability_name"))}</div>
        <div class="simple-row"><strong>已知：</strong>{escape((c.get("known") or {}).get("task"))}</div>
        <div class="simple-row"><strong>未知：</strong>{"、".join(escape(x) for x in (c.get("unknown") or []))}</div>
        <div class="conf">置信度：{escape(c.get("confidence"))}</div>
      </div>
    """
        for c in (candidate_evidence.get("incomplete_capabilities") or [])
    )

    fact_cards = "".join(
        f"""
      <div class="simple-card">
        <div class="simple-title">{escape(f.get("fact_name"))} <span class="meta">[{escape(f.get("fact_type"))}]</span></div>
        <div class="simple-row">{escape(f.get("value"))} <span class="tag {escape(f.get('verifiability'))}">{escape(f.get('verifiability'))}</span></div>
      </div>
    """
        for f in (candidate_evidence.get("objective_facts") or [])
    )

    claim_cards = "".join(
        f"""
      <div class="simple-card">
        <div class="simple-title">{escape(c.get("claim_name"))} = {escape(c.get("value"))} <span class="tag {escape(c.get('evidence_strength'))}">{escape(c.get('evidence_strength'))}</span></div>
        <div class="simple-row evidence">{escape(c.get("evidence_text"))}</div>
      </div>
    """
        for c in (candidate_evidence.get("subjective_claims") or [])
    )

    match_points_html = "\n".join(f"<li>{escape(mp)}</li>" for mp in match_points)
    gaps_html = "\n".join(f"<li>{escape(g)}</li>" for g in gaps)

    links = derive_links(activities, components, task_mappings, match_points, gaps, supplements)
    activity_diagram = build_activity_diagram(activities)
    capability_diagram = build_capability_diagram(components)
    match_diagram = build_match_diagram(links)

    value_stream_html = f"""
      <h3>{escape(value_stream.get("name"))}</h3>
      <div class="field"><strong>目的：</strong>{escape(value_stream.get("purpose"))}</div>
      <div class="field"><strong>定义：</strong>{escape(value_stream.get("definition"))}</div>
      <div class="field"><strong>范围包括：</strong>{"、".join(escape(x) for x in (value_stream.get("scope_includes") or []))}</div>
      <div class="field"><strong>范围不包括：</strong>{"、".join(escape(x) for x in (value_stream.get("scope_excludes") or []))}</div>
    """

    key_requirements_html = "\n".join(
        f"<li>{escape(k)}</li>" for k in (jd.get("key_requirements") or [])
    )

    parts: list[str] = []
    parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trace 可视化</title>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: false, theme: 'base', themeVariables: {{ primaryColor: '#e6f4ff', primaryTextColor: '#1f2937', primaryBorderColor: '#3b82f6', lineColor: '#6b7280' }} }});
    window.renderMermaid = async () => {{
      await mermaid.run({{ querySelector: '.mermaid' }});
    }};
  </script>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <h1>v3 Trace 可视化</h1>
    <p class="subtitle">岗位：{escape(jd.get("business_context"))} · 候选人：{escape(cand.get("candidate_profile"))}</p>

    <div class="summary-bar">
      <div class="summary-card">
        <h3>岗位核心判断</h3>
        <p>{escape(jd.get("jd_core_judgment"))}</p>
      </div>
      <div class="summary-card">
        <h3>候选人匹配判断</h3>
        <p>{escape(cand.get("candidate_match_summary"))}</p>
      </div>
      <div class="summary-card">
        <h3>角色错配</h3>
        <p>{"是" if cand.get("role_mismatch_flag") else "否"}</p>
      </div>
    </div>

    <section>
      <h2>一、岗位业务架构</h2>
      <div class="value-stream">{value_stream_html}</div>
      <div class="mermaid" id="flow-diagram">{escape(activity_diagram)}</div>
      <div>{activity_cards}</div>
      <div style="margin-top:16px;">
        <h3>关键要求 / 硬性条件</h3>
        <ul>{key_requirements_html}</ul>
      </div>
    </section>

    <section>
      <h2>二、候选人能力建模</h2>
      <div class="mermaid" id="capability-graph">{escape(capability_diagram)}</div>
      <h3>可建模能力</h3>
      <div>{component_cards}</div>

      <h3>不完整任务能力</h3>
      <div class="grid-2">{incomplete_cards}</div>

      <h3>客观背景事实</h3>
      <div class="grid-2">{fact_cards}</div>

      <h3>主观能力声明</h3>
      <div class="grid-2">{claim_cards}</div>

      <div class="grid-2" style="margin-top:24px;">
        <div class="match-box">
          <h4 class="strength">匹配点</h4>
          <ul>{match_points_html}</ul>
        </div>
        <div class="match-box">
          <h4 class="weak">缺口</h4>
          <ul>{gaps_html}</ul>
        </div>
      </div>
    </section>

    <section>
      <h2>三、任务级匹配关系</h2>
      <div class="mermaid" id="match-graph">{escape(match_diagram)}</div>
      <div class="match-legend">
        <span class="legend-item matched">直接匹配</span>
        <span class="legend-item partial">部分匹配</span>
        <span class="legend-item related">相关</span>
        <span class="legend-item unmatched-jd">JD 未覆盖</span>
        <span class="legend-item unmatched-res">简历未覆盖</span>
      </div>
    </section>

    <section>
      <h2>四、终局判断</h2>
      <div class="conclusion-header">
        <span class="conclusion-badge" id="conclusion-badge"></span>
        <span class="recommendation" id="recommendation"></span>
        <span class="match-score" id="match-score"></span>
      </div>
      <div class="summary-box" id="summary"></div>
      <div class="conclusion-grid">
        <div class="conclusion-card strengths">
          <h4>优势</h4>
          <ul id="strengths-list"></ul>
        </div>
        <div class="conclusion-card risks">
          <h4>风险</h4>
          <ul id="risks-list"></ul>
        </div>
        <div class="conclusion-card next-actions">
          <h4>下一步</h4>
          <ul id="next-actions-list"></ul>
        </div>
      </div>
      <div class="supplements-section">
        <h3>查漏补充</h3>
        <table class="supplements-table">
          <thead>
            <tr><th>类型</th><th>目标</th><th>描述</th><th>建议</th></tr>
          </thead>
          <tbody id="supplements-body"></tbody>
        </table>
      </div>
    </section>
  </div>

  <script type="module">
""")
    parts.append(json_var("finalData", final))
    parts.append("""
    function escapeHtml(str) {
      if (!str) return "";
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    document.getElementById("conclusion-badge").textContent = finalData.conclusion_label || "";
    document.getElementById("recommendation").textContent = finalData.recommendation || "";
    document.getElementById("match-score").textContent = String(finalData.match_score ?? "");
    document.getElementById("summary").textContent = finalData.summary || "";

    ["strengths", "risks", "next_actions"].forEach((key) => {
      const list = document.getElementById(key.replace("_", "-") + "-list");
      list.innerHTML = (finalData[key] || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
    });

    const tbody = document.getElementById("supplements-body");
    tbody.innerHTML = (finalData.supplements || []).map((s) => `
      <tr>
        <td><span class="type-badge type-${escapeHtml(s.type)}">${escapeHtml(s.type)}</span></td>
        <td>${escapeHtml(s.target)}</td>
        <td>${escapeHtml(s.description)}</td>
        <td>${escapeHtml(s.suggested_action)}</td>
      </tr>
    `).join("");

    window.renderMermaid();
  </script>
</body>
</html>
""")
    return "".join(parts)


def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    if not log_path.exists():
        print(f"Log not found: {log_path}", file=sys.stderr)
        return 1

    text = log_path.read_text(encoding="utf-8")
    blocks = extract_json_blocks(text)
    jd_block = find_block(blocks, ["job_analysis", "business_flow"])
    candidate_block = find_block(blocks, ["candidate_analysis", "candidate_evidence"])
    final_block = find_final_block(blocks)
    if not jd_block:
        print("Could not find JD business_flow block", file=sys.stderr)
        return 1
    if not candidate_block:
        print("Could not find candidate evidence block", file=sys.stderr)
        return 1

    out_path = REPO_ROOT / "outputs" / f"{log_path.stem}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(jd_block, candidate_block, final_block or {})
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
