/*
 * 目的：D3 图谱渲染模块。
 * 定义：把 element_modeling 输出渲染为关系图、流程图和 CRUD 矩阵。
 * 范围包括：
 * - 数据归一化、SVG 绘制、tab 切换、详情浮层和 fitView。
 * 范围不包括：
 * - 不发起 API 请求，不修改后端返回。
 * 使用与修改规则：
 * - 后端 element_modeling schema 变化时同步数据读取和字段标签。
 */

/* ===================================================================
 * graph-renderer.js — D3 三视图图谱渲染
 * 入口: renderGraph(elementModelingData)
 * 依赖: d3.v7.min.js (需先加载)
 * =================================================================== */

/* -------------------------------------------------------------------
 * 常量
 * ------------------------------------------------------------------- */

const COLORS = {
  VS: '#1f5b46',
  WI: '#2f8d5b',
  ENJ: '#d69035',
  CAP: '#a0472d'
};

const DOMAIN_COLORS = {
  business: '#a0472d',
  product: '#2f8d5b',
  data_knowledge: '#d69035',
  ai_capability: '#1f5b46',
  software_system: '#667067',
  runtime_delivery: '#8b6f4e',
  governance_constraint: '#d9534f'
};

const GRAPH_LABEL_FONT_SIZE = 13;
const GRAPH_LABEL_BASELINE_OFFSET = 18;
const GRAPH_LABEL_BOTTOM_PADDING = 4;

/* -------------------------------------------------------------------
 * 模块级状态（支持清理 + 懒渲染）
 * ------------------------------------------------------------------- */

let simForce = null;         // force simulation 引用
let lastRaw = null;          // 上次渲染的原始数据
const VIEW_RENDERED = { 1: false, 2: false, 3: false };
let activeViewIndex = 1;

/* -------------------------------------------------------------------
 * 工具函数
 * ------------------------------------------------------------------- */

function nodeRadius(d) {
  return 12 + (d.confidence || 0) * 16;
}

function nodeColor(d) {
  if (d.type === 'ENJ') return DOMAIN_COLORS[d.domain] || COLORS.ENJ;
  return COLORS[d.type] || '#999';
}

function labelText(d) {
  const n = d.name || '';
  return n.length > 8 ? n.slice(0, 8) + '…' : n;
}

function nodeVisualBounds(d) {
  const r = nodeRadius(d);
  const labelWidth = Math.max(36, labelText(d).length * GRAPH_LABEL_FONT_SIZE);
  let shapeHalfWidth = r;
  let shapeTop = -r;
  let shapeBottom = r;

  if (d.type === 'VS') {
    shapeHalfWidth = r * 1.6;
    shapeTop = -r * 0.7;
    shapeBottom = r * 0.7;
  } else if (d.type === 'ENJ') {
    shapeHalfWidth = r * 1.2;
    shapeTop = -r * 1.2;
    shapeBottom = r * 1.2;
  } else if (d.type === 'CAP') {
    shapeHalfWidth = r * 1.1;
    shapeTop = -r * 1.1;
    shapeBottom = r * 1.1;
  }

  return {
    left: -Math.max(shapeHalfWidth, labelWidth / 2),
    right: Math.max(shapeHalfWidth, labelWidth / 2),
    top: shapeTop,
    bottom: Math.max(shapeBottom, r + GRAPH_LABEL_BASELINE_OFFSET + GRAPH_LABEL_BOTTOM_PADDING)
  };
}

function forceVisualBoundsCollision(padding = 12) {
  let forceNodes = [];

  function force(alpha) {
    for (let i = 0; i < forceNodes.length; i++) {
      const a = forceNodes[i];
      const aBounds = nodeVisualBounds(a);
      const aCenterX = a.x + (aBounds.left + aBounds.right) / 2;
      const aCenterY = a.y + (aBounds.top + aBounds.bottom) / 2;

      for (let j = i + 1; j < forceNodes.length; j++) {
        const b = forceNodes[j];
        const bBounds = nodeVisualBounds(b);
        const bCenterX = b.x + (bBounds.left + bBounds.right) / 2;
        const bCenterY = b.y + (bBounds.top + bBounds.bottom) / 2;
        const overlapX = Math.min(aCenterX + (aBounds.right - aBounds.left) / 2 + padding, bCenterX + (bBounds.right - bBounds.left) / 2 + padding) -
          Math.max(aCenterX - (aBounds.right - aBounds.left) / 2 - padding, bCenterX - (bBounds.right - bBounds.left) / 2 - padding);
        const overlapY = Math.min(aCenterY + (aBounds.bottom - aBounds.top) / 2 + padding, bCenterY + (bBounds.bottom - bBounds.top) / 2 + padding) -
          Math.max(aCenterY - (aBounds.bottom - aBounds.top) / 2 - padding, bCenterY - (bBounds.bottom - bBounds.top) / 2 - padding);

        if (overlapX <= 0 || overlapY <= 0) continue;

        const strength = Math.max(alpha, 0.2) * 0.5;
        if (overlapX < overlapY) {
          const shift = overlapX * strength;
          if (aCenterX <= bCenterX) {
            a.vx -= shift;
            b.vx += shift;
          } else {
            a.vx += shift;
            b.vx -= shift;
          }
        } else {
          const shift = overlapY * strength;
          if (aCenterY <= bCenterY) {
            a.vy -= shift;
            b.vy += shift;
          } else {
            a.vy += shift;
            b.vy -= shift;
          }
        }
      }
    }
  }

  force.initialize = nodes => { forceNodes = nodes; };
  return force;
}

/* -------------------------------------------------------------------
 * 构建 nodes / links（从 API 数据）
 * ------------------------------------------------------------------- */

function buildGraph(raw) {
  const nodes = [];
  const links = [];

  (raw.value_streams || []).forEach(vs => {
    nodes.push({
      id: vs.id, type: 'VS', name: vs.value_stream_name,
      purpose: vs.purpose, evidence: vs.source_evidence,
      evidenceType: vs.evidence_type, confidence: vs.confidence,
      raw: vs
    });
    (vs.work_item_ids || []).forEach(wid => {
      links.push({ source: vs.id, target: wid, type: 'contains' });
    });
  });

  (raw.work_items || []).forEach(wi => {
    nodes.push({
      id: wi.id, type: 'WI', name: wi.work_item_name,
      purpose: wi.purpose, evidence: wi.source_evidence,
      evidenceType: wi.evidence_type, confidence: wi.confidence,
      raw: wi
    });
    (wi.entity_operations || []).forEach(op => {
      links.push({
        source: wi.id, target: op.entity_id,
        type: 'operates_on', operation: op.operation,
        opDesc: op.operation_description
      });
    });
    (wi.capability_ids || []).forEach(cid => {
      links.push({ source: wi.id, target: cid, type: 'requires' });
    });
  });

  (raw.bussiness_entitys || []).forEach(enj => {
    nodes.push({
      id: enj.id, type: 'ENJ', name: enj.entity_name,
      domain: enj.entity_domain, entityType: enj.entity_type,
      purpose: (enj.entity_domain || '') + ' / ' + (enj.entity_type || ''),
      evidence: enj.source_evidence,
      evidenceType: enj.evidence_type, confidence: enj.confidence,
      raw: enj
    });
  });

  (raw.capabilities || []).forEach(cap => {
    nodes.push({
      id: cap.id, type: 'CAP', name: cap.capability_name,
      purpose: cap.definition,
      evidence: cap.source_evidence,
      evidenceType: cap.evidence_type, confidence: cap.confidence,
      primaryEntityIds: cap.primary_entity_ids,
      raw: cap
    });
    (cap.primary_entity_ids || []).forEach(eid => {
      links.push({ source: cap.id, target: eid, type: 'manages' });
    });
  });

  return { nodes, links };
}

/* -------------------------------------------------------------------
 * 空数据降级
 * ------------------------------------------------------------------- */

function renderEmptyGraph() {
  const wrap = document.getElementById('svgWrap');
  if (!wrap) return;
  wrap.querySelectorAll('svg, .graph-empty').forEach(node => node.remove());
  wrap.insertAdjacentHTML('afterbegin', '<div class="graph-empty"><p>图谱数据暂不可用</p><p class="graph-empty-hint">分析仍在进行中，或该岗位描述未能提取出足够的建模元素</p></div>');
}

/* -------------------------------------------------------------------
 * 详情面板
 * ------------------------------------------------------------------- */

function showDetail(d, nodes, links) {
  const detailPanel = document.getElementById('detailPanel');
  const dpContent = document.getElementById('dpContent');
  if (!detailPanel || !dpContent) return;

  const typeLabel = { VS: '价值流', WI: '工作事项', ENJ: '业务实体', CAP: '能力' };
  const domainLabel = d.domain ? ' · ' + d.domain : '';

  const relatedLinks = links.filter(l => {
    const sid = l.source?.id || l.source;
    const tid = l.target?.id || l.target;
    return sid === d.id || tid === d.id;
  });
  const relatedNodeIds = relatedLinks.map(l => {
    const sid = l.source?.id || l.source;
    const tid = l.target?.id || l.target;
    return sid === d.id ? tid : sid;
  });
  const relatedNames = [...new Set(relatedNodeIds)].map(id => {
    const n = nodes.find(nn => nn.id === id);
    return n ? '<span class="dp-chip entity">' + esc(n.name) + '</span>' : '';
  }).join('');

  let evidenceHtml = '';
  if (d.evidence && d.evidence.length) {
    evidenceHtml = d.evidence.map(e => '<span class="dp-chip evidence">' + esc(e.slice(0, 40)) + '…</span>').join('<br>');
  }

  let domainChip = '';
  if (d.type === 'ENJ' && d.domain) {
    const dc = DOMAIN_COLORS[d.domain] || '#999';
    domainChip = '<span class="dp-chip" style="background:' + dc + ';color:#fff;">' + esc(d.domain) + '</span>';
  }

  const conf = d.confidence != null ? d.confidence : 1.0;
  const evType = d.evidenceType || 'explicit';

  dpContent.innerHTML =
    '<h3>' + esc(d.name) + '</h3>' +
    '<div class="dp-type">' + esc(typeLabel[d.type] || d.type || '关系') + domainLabel + ' ' + domainChip + '</div>' +
    '<div style="font-size:13px;line-height:1.6;color:var(--ink);">' + esc(d.purpose || '') + '</div>' +
    '<div class="dp-section"><h4>关联节点</h4>' + (relatedNames || '<span style="color:var(--muted);font-size:12px;">无</span>') + '</div>' +
    '<div class="dp-section"><h4>来源证据</h4>' + (evidenceHtml || '<span style="color:var(--muted);font-size:12px;">无</span>') + '</div>' +
    '<div class="dp-section"><h4>置信度</h4>' +
    '<div style="height:4px;background:var(--line);border-radius:2px;margin-top:4px;">' +
    '<div style="height:100%;width:' + (conf * 100) + '%;background:var(--green);border-radius:2px;"></div>' +
    '</div>' +
    '<span style="font-size:11px;color:var(--muted);">' + conf + ' · ' + esc(evType) + '</span>' +
    '</div>';

  detailPanel.classList.add('open');
}

function esc(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(s)));
  return div.innerHTML;
}

/* -------------------------------------------------------------------
 * View 1: 力导向图
 * ------------------------------------------------------------------- */

function renderView1(raw) {
  const svgWrap = document.getElementById('svgWrap');
  const tooltip = document.getElementById('tooltip');
  const detailPanel = document.getElementById('detailPanel');
  if (!svgWrap) return;

  // 清理
  svgWrap.querySelectorAll('svg, .graph-empty').forEach(s => s.remove());

  const { nodes, links } = buildGraph(raw);

  const width = svgWrap.clientWidth || 800;
  const height = svgWrap.clientHeight || 500;

  const svg = d3.select('#svgWrap')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const g = svg.append('g');
  let hasUserAdjustedView = false;

  const zoom = d3.zoom()
    .scaleExtent([0.2, 3])
    .filter(event => event.type !== 'wheel')
    .on('start', (event) => {
      if (event.sourceEvent) hasUserAdjustedView = true;
    })
    .on('zoom', (event) => { g.attr('transform', event.transform); });
  svg.call(zoom);
  svg._zoom = zoom;

  function viewportSize() {
    const rect = svgWrap.getBoundingClientRect();
    const nextWidth = Math.max(rect.width || svgWrap.clientWidth || width, 320);
    const nextHeight = Math.max(rect.height || svgWrap.clientHeight || height, 240);
    svg.attr('width', nextWidth).attr('height', nextHeight);
    simForce.force('center', d3.forceCenter(nextWidth / 2, nextHeight / 2));
    return { width: nextWidth, height: nextHeight };
  }

  function fitView(duration, force = false) {
    if (hasUserAdjustedView && !force) return;
    const visibleNodes = nodes.filter(d => Number.isFinite(d.x) && Number.isFinite(d.y));
    if (visibleNodes.length === 0) return;
    const size = viewportSize();
    const x0 = Math.min(...visibleNodes.map(d => d.x + nodeVisualBounds(d).left));
    const x1 = Math.max(...visibleNodes.map(d => d.x + nodeVisualBounds(d).right));
    const y0 = Math.min(...visibleNodes.map(d => d.y + nodeVisualBounds(d).top));
    const y1 = Math.max(...visibleNodes.map(d => d.y + nodeVisualBounds(d).bottom));
    const pad = 80;
    const graphW = Math.max(x1 - x0, 1);
    const graphH = Math.max(y1 - y0, 1);
    const scale = Math.min(size.width / (graphW + pad * 2), size.height / (graphH + pad * 2), 1.35);
    const tx = size.width / 2 - (x0 + x1) / 2 * scale;
    const ty = size.height / 2 - (y0 + y1) / 2 * scale;
    const target = d3.zoomIdentity.translate(tx, ty).scale(scale);
    if (duration > 0) {
      svg.transition().duration(duration).call(zoom.transform, target);
    } else {
      svg.call(zoom.transform, target);
    }
  }

  // arrow markers
  g.append('defs').selectAll('marker')
    .data(['contains', 'operates_on', 'requires', 'manages'])
    .join('marker')
    .attr('id', d => 'arrow-' + d)
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-4L8,0L0,4')
    .attr('fill', d => {
      if (d === 'contains') return COLORS.VS;
      if (d === 'requires') return COLORS.CAP;
      return COLORS.ENJ;
    });

  // force simulation
  simForce = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
      if (d.type === 'contains') return 100;
      if (d.type === 'operates_on') return 120;
      if (d.type === 'requires') return 100;
      return 140;
    }))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('visual-bounds-collision', forceVisualBoundsCollision());

  // shape renderers
  function drawNode(sel) {
    sel.each(function (d) {
      const el = d3.select(this);
      const r = nodeRadius(d);
      if (d.type === 'VS') {
        el.append('rect')
          .attr('x', -r * 1.6).attr('y', -r * 0.7)
          .attr('width', r * 3.2).attr('height', r * 1.4)
          .attr('rx', 8).attr('ry', 8)
          .attr('fill', nodeColor(d))
          .attr('stroke', d.evidenceType === 'inferred' ? '#999' : 'none')
          .attr('stroke-dasharray', d.evidenceType === 'inferred' ? '4 2' : 'none')
          .attr('stroke-width', 1.5);
      } else if (d.type === 'WI') {
        el.append('circle')
          .attr('r', r)
          .attr('fill', nodeColor(d))
          .attr('stroke', d.evidenceType === 'inferred' ? '#999' : 'none')
          .attr('stroke-dasharray', d.evidenceType === 'inferred' ? '4 2' : 'none')
          .attr('stroke-width', 1.5);
      } else if (d.type === 'ENJ') {
        const s = r * 1.2;
        el.append('polygon')
          .attr('points', '0,' + (-s) + ' ' + s + ',0 0,' + s + ' ' + (-s) + ',0')
          .attr('fill', nodeColor(d))
          .attr('stroke', d.evidenceType === 'inferred' ? '#999' : 'none')
          .attr('stroke-dasharray', d.evidenceType === 'inferred' ? '4 2' : 'none')
          .attr('stroke-width', 1.5);
      } else if (d.type === 'CAP') {
        const pts = [];
        for (let i = 0; i < 6; i++) {
          const a = Math.PI / 6 + i * Math.PI / 3;
          pts.push([r * 1.1 * Math.cos(a), r * 1.1 * Math.sin(a)]);
        }
        el.append('polygon')
          .attr('points', pts.map(p => p.join(',')).join(' '))
          .attr('fill', nodeColor(d))
          .attr('stroke', d.evidenceType === 'inferred' ? '#999' : 'none')
          .attr('stroke-dasharray', d.evidenceType === 'inferred' ? '4 2' : 'none')
          .attr('stroke-width', 1.5);
      }
    });
  }

  // links
  const linkG = g.append('g').attr('class', 'links');
  const link = linkG.selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', d => {
      if (d.type === 'contains') return COLORS.VS;
      if (d.type === 'requires' || d.type === 'manages') return COLORS.CAP;
      return COLORS.ENJ;
    })
    .attr('stroke-width', d => d.type === 'contains' ? 2 : 1.2)
    .attr('stroke-dasharray', d => {
      if (d.type === 'operates_on') return '6 3';
      if (d.type === 'requires') return '3 3';
      return 'none';
    })
    .attr('stroke-opacity', 0.5)
    .attr('marker-end', d => 'url(#arrow-' + d.type + ')');

  // nodes
  const nodeG = g.append('g').attr('class', 'nodes');
  const node = nodeG.selectAll('g')
    .data(nodes)
    .join('g')
    .attr('class', d => 'node node-' + d.type)
    .attr('tabindex', 0)
    .attr('role', 'button')
    .attr('aria-label', d => '查看' + d.name + '的详情')
    .call(drawNode)
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simForce.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) simForce.alphaTarget(0); d.fx = null; d.fy = null; })
    );

  // labels
  const labelG = g.append('g').attr('class', 'labels');
  const label = labelG.selectAll('text')
    .data(nodes)
    .join('text')
    .text(d => labelText(d))
    .attr('font-size', GRAPH_LABEL_FONT_SIZE)
    .attr('font-weight', 700)
    .attr('text-anchor', 'middle')
    .attr('dy', d => nodeRadius(d) + GRAPH_LABEL_BASELINE_OFFSET)
    .attr('fill', 'var(--ink)')
    .attr('stroke', 'var(--surface)')
    .attr('stroke-width', 3)
    .attr('paint-order', 'stroke')
    .attr('stroke-linejoin', 'round')
    .style('pointer-events', 'none')
    .style('user-select', 'none');

  // tick
  simForce.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
    label.attr('x', d => d.x).attr('y', d => d.y);
  });

  // tooltip
  node.on('mouseenter', function (event, d) {
    const deps = links.filter(l => l.source.id === d.id || l.target.id === d.id);
    node.style('opacity', n => n.id === d.id || deps.some(l => l.source.id === n.id || l.target.id === n.id) ? 1 : 0.15);
    link.style('opacity', l => l.source.id === d.id || l.target.id === d.id ? 0.9 : 0.08);

    tooltip.innerHTML =
      '<div class="tt-name">' + esc(d.name) + '</div>' +
      '<div class="tt-meta">' + d.type + ' · confidence ' + (d.confidence || 0) + ' · ' + (d.evidenceType || '') + '</div>' +
      '<div style="margin-top:4px;font-size:11px;">' + esc(d.purpose || '') + '</div>';
    tooltip.classList.add('visible');
  })
    .on('mousemove', function (event) {
      const [mx, my] = d3.pointer(event, svgWrap);
      tooltip.style.left = (mx + 16) + 'px';
      tooltip.style.top = (my - 10) + 'px';
    })
    .on('mouseleave', function () {
      node.style('opacity', 1);
      link.style('opacity', 0.5);
      tooltip.classList.remove('visible');
    });

  // click → detail
  node.on('click', function (event, d) {
    event.stopPropagation();
    showDetail(d, nodes, links);
  });
  node.on('keydown', function (event, d) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      event.stopPropagation();
      showDetail(d, nodes, links);
    }
  });

  svg.on('click', function () {
    if (detailPanel) detailPanel.classList.remove('open');
  });

  // filters
  const filterState = { VS: true, WI: true, ENJ: true, CAP: true };

  function applyFilters() {
    node.style('display', d => filterState[d.type] ? null : 'none');
    label.style('display', d => filterState[d.type] ? null : 'none');
    link.style('display', l => {
      return filterState[l.source.type] && filterState[l.target.type] ? null : 'none';
    });
  }

  document.querySelectorAll('.filter-btn[data-type]').forEach(btn => {
    const clone = btn.cloneNode(true);
    btn.parentNode.replaceChild(clone, btn);
    clone.addEventListener('click', function () {
      const t = this.dataset.type;
      filterState[t] = !filterState[t];
      this.classList.toggle('active', filterState[t]);
      applyFilters();
    });
  });

  // fit button
  const fitBtn = document.getElementById('btnFit');
  if (fitBtn) {
    const newFitBtn = fitBtn.cloneNode(true);
    fitBtn.parentNode.replaceChild(newFitBtn, fitBtn);
    newFitBtn.addEventListener('click', () => fitView(600, true));
  }

  document.querySelectorAll('[data-graph-zoom]').forEach(btn => {
    const clone = btn.cloneNode(true);
    btn.parentNode.replaceChild(clone, btn);
    clone.addEventListener('click', () => {
      hasUserAdjustedView = true;
      const factor = clone.dataset.graphZoom === 'in' ? 1.2 : 1 / 1.2;
      svg.transition().duration(180).call(zoom.scaleBy, factor);
    });
  });

  // initial fit after sim stabilizes
  window.setTimeout(() => fitView(0), 360);
  simForce.on('end', () => fitView(600));
}

/* -------------------------------------------------------------------
 * View 2: 流程图（泳道）
 * ------------------------------------------------------------------- */

function renderView2(raw) {
  const wrap = document.getElementById('swimlaneWrap');
  const tooltip = document.getElementById('tooltip');
  if (!wrap) return;
  wrap.innerHTML = '';

  const valueStreams = raw.value_streams || [];
  if (valueStreams.length === 0) return;

  const workItemsMap = {};
  (raw.work_items || []).forEach(wi => { workItemsMap[wi.id] = wi; });

  const viewportW = Math.max(wrap.clientWidth, 800);
  const paddingX = 44;
  const paddingY = 32;
  const containerPadX = 32;
  const titleH = 56;
  const cardW = 238;
  const cardH = 78;
  const cardGap = 54;
  const containerH = 188;
  const rowGap = 28;

  const maxContentW = d3.max(valueStreams, vs => {
    const wiCount = Math.max((vs.work_item_ids || []).length, 1);
    return containerPadX * 2 + wiCount * cardW + Math.max(wiCount - 1, 0) * cardGap;
  }) || 0;
  const width = Math.max(viewportW, paddingX * 2 + maxContentW);
  const totalH = paddingY * 2 + valueStreams.length * containerH + Math.max(valueStreams.length - 1, 0) * rowGap;

  const svg = d3.select(wrap)
    .append('svg')
    .attr('width', width)
    .attr('height', Math.max(totalH, wrap.clientHeight || 400));

  svg.append('defs').append('marker')
    .attr('id', 'arrow-flow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 10).attr('refY', 0)
    .attr('markerWidth', 7).attr('markerHeight', 7)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-4L8,0L0,4')
    .attr('fill', COLORS.VS);

  function wrapText(text, maxChars, maxLines) {
    const lines = [];
    let rest = text || '';
    while (rest.length > 0 && lines.length < maxLines) {
      let line = rest.slice(0, maxChars);
      rest = rest.slice(maxChars);
      if (rest.length > 0 && lines.length === maxLines - 1) line = line.slice(0, Math.max(maxChars - 1, 1)) + '…';
      lines.push(line);
    }
    return lines.length ? lines : [''];
  }

  valueStreams.forEach((vs, vsIdx) => {
    const rowY = paddingY + vsIdx * (containerH + rowGap);
    const wiIds = vs.work_item_ids || [];
    const wiCount = wiIds.length;
    const flowW = Math.max(wiCount, 1) * cardW + Math.max(wiCount - 1, 0) * cardGap;
    const containerW = Math.max(viewportW - paddingX * 2, containerPadX * 2 + flowW);
    const containerX = paddingX;
    const cardY = rowY + titleH + 22;
    const firstCardX = containerX + containerPadX;

    const vsNode = { id: vs.id, type: 'VS', name: vs.value_stream_name, purpose: vs.purpose, evidence: vs.source_evidence, evidenceType: vs.evidence_type, confidence: vs.confidence };
    const vsG = svg.append('g').attr('class', 'flow-vs-container').style('cursor', 'pointer');

    vsG.append('rect')
      .attr('x', containerX).attr('y', rowY)
      .attr('width', containerW).attr('height', containerH)
      .attr('rx', 16).attr('ry', 16)
      .attr('fill', 'rgba(47,141,91,0.035)')
      .attr('stroke', COLORS.VS)
      .attr('stroke-dasharray', '8 5')
      .attr('stroke-width', 1.5);

    vsG.append('text')
      .attr('x', containerX + 24).attr('y', rowY + 28)
      .attr('fill', COLORS.VS)
      .attr('font-size', 15).attr('font-weight', 700)
      .text((vs.value_stream_name || '').length > 34 ? vs.value_stream_name.slice(0, 33) + '…' : (vs.value_stream_name || ''));

    vsG.append('text')
      .attr('x', containerX + 24).attr('y', rowY + 49)
      .attr('fill', 'var(--muted)')
      .attr('font-size', 11)
      .text((vs.id || '') + ' · 端到端价值流');

    vsG.on('mouseenter', () => {
      tooltip.innerHTML = '<div class="tt-name">' + esc(vsNode.name) + '</div><div class="tt-meta">VS · ' + (vsNode.evidenceType || '') + '</div><div style="margin-top:4px;font-size:11px;">' + esc(vsNode.purpose || '') + '</div>';
      tooltip.classList.add('visible');
    })
      .on('mousemove', (event) => {
        const [mx, my] = d3.pointer(event, wrap);
        tooltip.style.left = (mx + 16) + 'px';
        tooltip.style.top = (my - 10) + 'px';
      })
      .on('mouseleave', () => { tooltip.classList.remove('visible'); })
      .on('click', (event) => { event.stopPropagation(); showDetail(vsNode, [], []); });

    wiIds.forEach((wid, wiIdx) => {
      const wi = workItemsMap[wid];
      if (!wi) return;
      const cardX = firstCardX + wiIdx * (cardW + cardGap);

      const wiG = svg.append('g').attr('class', 'flow-wi-card').style('cursor', 'pointer');

      wiG.append('rect')
        .attr('x', cardX).attr('y', cardY)
        .attr('width', cardW).attr('height', cardH)
        .attr('rx', 10).attr('ry', 10)
        .attr('fill', 'rgba(47,141,91,0.12)')
        .attr('stroke', wi.evidence_type === 'inferred' ? '#999' : 'none')
        .attr('stroke-dasharray', wi.evidence_type === 'inferred' ? '4 2' : 'none')
        .attr('stroke-width', 1.5);

      wiG.append('text')
        .attr('x', cardX + 16).attr('y', cardY + 24)
        .attr('fill', COLORS.WI)
        .attr('font-size', 11).attr('font-weight', 700)
        .text(wi.id);

      const labelLines = wrapText(wi.work_item_name, 15, 2);
      const label = wiG.append('text')
        .attr('x', cardX + 16).attr('y', cardY + 47)
        .attr('fill', 'var(--ink)')
        .attr('font-size', 13)
        .attr('font-weight', 600)
        .style('pointer-events', 'none').style('user-select', 'none');
      labelLines.forEach((line, lineIdx) => {
        label.append('tspan')
          .attr('x', cardX + 16)
          .attr('dy', lineIdx === 0 ? 0 : 18)
          .text(line);
      });

      const wiNode = { id: wi.id, type: 'WI', name: wi.work_item_name, purpose: wi.purpose, evidence: wi.source_evidence, evidenceType: wi.evidence_type, confidence: wi.confidence };
      wiG.on('mouseenter', () => {
        tooltip.innerHTML = '<div class="tt-name">' + esc(wiNode.name) + '</div><div class="tt-meta">WI · ' + (wiNode.evidenceType || '') + '</div><div style="margin-top:4px;font-size:11px;">' + esc(wiNode.purpose || '') + '</div>';
        tooltip.classList.add('visible');
      })
        .on('mousemove', (event) => {
          const [mx, my] = d3.pointer(event, wrap);
          tooltip.style.left = (mx + 16) + 'px';
          tooltip.style.top = (my - 10) + 'px';
        })
        .on('mouseleave', () => { tooltip.classList.remove('visible'); })
        .on('click', (event) => { event.stopPropagation(); showDetail(wiNode, [], []); });
    });

    for (let i = 0; i < wiCount - 1; i++) {
      const fromX = firstCardX + i * (cardW + cardGap) + cardW;
      const toX = fromX + cardGap;
      svg.append('line')
        .attr('x1', fromX + 8).attr('y1', cardY + cardH / 2)
        .attr('x2', toX - 8).attr('y2', cardY + cardH / 2)
        .attr('stroke', COLORS.VS).attr('stroke-width', 2)
        .attr('marker-end', 'url(#arrow-flow)');
    }
  });

  svg.on('click', () => {
    const dp = document.getElementById('detailPanel');
    if (dp) dp.classList.remove('open');
  });
}

/* -------------------------------------------------------------------
 * View 3: CRUD 矩阵
 * ------------------------------------------------------------------- */

function renderView3(raw) {
  const wrap = document.getElementById('matrixWrap');
  const tooltip = document.getElementById('tooltip');
  if (!wrap) return;
  wrap.innerHTML = '';

  const valueStreams = raw.value_streams || [];
  const allWiIds = [];
  valueStreams.forEach(vs => { (vs.work_item_ids || []).forEach(wid => { if (!allWiIds.includes(wid)) allWiIds.push(wid); }); });
  const wis = allWiIds.map(wid => (raw.work_items || []).find(w => w.id === wid)).filter(Boolean);

  const entities = raw.bussiness_entitys || [];
  const capabilities = raw.capabilities || [];

  if (wis.length === 0 && entities.length === 0 && capabilities.length === 0) return;

  const cellW = 80, cellH = 34;
  const rowHeaderW = 150;
  const colHeaderH = 90;
  const titleH = 28;

  const colsE = entities.length;
  const rowsW = wis.length;
  const colsC = capabilities.length;

  const maxGridW = Math.max(colsE, colsC) * cellW;
  const svgW = rowHeaderW + Math.max(maxGridW, 200) + 40;
  const gridH1 = colHeaderH + rowsW * cellH;
  const gridH2 = colHeaderH + rowsW * cellH;
  const svgH = gridH1 + titleH + gridH2 + 40;

  const svg = d3.select(wrap)
    .append('svg')
    .attr('width', svgW)
    .attr('height', svgH);

  const CRUD_COLORS = { create: '#2f8d5b', read: '#8bb8a0', update: '#d69035', delete: '#a0472d' };
  const CRUD_SYMBOLS = { create: 'C', read: 'R', update: 'U', delete: 'D' };

  function renderMatrix(startY, columns, colLabels, colDomains, getCellOp) {
    const cols = columns.length;
    if (cols === 0) return startY;

    columns.forEach((col, ci) => {
      const cx = rowHeaderW + ci * cellW + cellW / 2;
      const cy = startY + colHeaderH - 16;

      if (colDomains && colDomains[ci]) {
        svg.append('rect')
          .attr('x', rowHeaderW + ci * cellW + 4)
          .attr('y', startY)
          .attr('width', cellW - 8)
          .attr('height', 4)
          .attr('rx', 2)
          .attr('fill', DOMAIN_COLORS[colDomains[ci]] || '#999');
      }

      const name = colLabels[ci] || '';
      const displayName = name.length > 8 ? name.slice(0, 8) + '…' : name;
      svg.append('text')
        .attr('x', cx)
        .attr('y', startY + 28)
        .attr('transform', 'rotate(-45, ' + cx + ', ' + (startY + 28) + ')')
        .attr('text-anchor', 'end')
        .attr('fill', 'var(--ink)')
        .attr('font-size', 10)
        .attr('font-weight', 600)
        .text(displayName);

      svg.append('text')
        .attr('x', cx)
        .attr('y', cy + 10)
        .attr('text-anchor', 'middle')
        .attr('fill', 'var(--muted)')
        .attr('font-size', 9)
        .text(col.id);
    });

    wis.forEach((wi, ri) => {
      const ry = startY + colHeaderH + ri * cellH;
      const rcy = ry + cellH / 2;

      svg.append('rect')
        .attr('x', 4).attr('y', ry)
        .attr('width', rowHeaderW - 8).attr('height', cellH)
        .attr('fill', ri % 2 === 0 ? 'rgba(31,39,34,0.02)' : 'transparent');

      const wiName = (wi.work_item_name || '').length > 8 ? wi.work_item_name.slice(0, 8) + '…' : (wi.work_item_name || '');
      svg.append('text')
        .attr('x', rowHeaderW - 10).attr('y', rcy)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'central')
        .attr('fill', 'var(--ink)')
        .attr('font-size', 11)
        .attr('font-weight', 500)
        .text(wiName);

      columns.forEach((col, ci) => {
        const cx = rowHeaderW + ci * cellW;
        const cellOp = getCellOp(wi, col);

        const cellRect = svg.append('rect')
          .attr('x', cx + 1).attr('y', ry + 1)
          .attr('width', cellW - 2).attr('height', cellH - 2)
          .attr('rx', 3)
          .attr('fill', cellOp ? (CRUD_COLORS[cellOp.op] || '#eee') : 'rgba(31,39,34,0.04)')
          .attr('stroke', 'var(--line)')
          .attr('stroke-width', 0.5)
          .style('cursor', cellOp ? 'pointer' : 'default');

        if (cellOp) {
          svg.append('text')
            .attr('x', cx + cellW / 2).attr('y', rcy)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'central')
            .attr('fill', '#fff')
            .attr('font-size', 16)
            .attr('font-weight', 700)
            .style('pointer-events', 'none')
            .text(CRUD_SYMBOLS[cellOp.op] || '?');

          cellRect.on('mouseenter', () => {
            tooltip.innerHTML = '<div class="tt-name">' + esc(wi.work_item_name || '') + '</div><div class="tt-meta">' + (cellOp.op || '').toUpperCase() + ' → ' + esc(col.entity_name || col.capability_name || '') + '</div><div style="margin-top:4px;font-size:11px;">' + esc(cellOp.desc || '') + '</div>';
            tooltip.classList.add('visible');
          })
            .on('mousemove', (event) => {
              const [mx, my] = d3.pointer(event, wrap);
              tooltip.style.left = (mx + 16) + 'px';
              tooltip.style.top = (my - 10) + 'px';
            })
            .on('mouseleave', () => { tooltip.classList.remove('visible'); })
            .on('click', (event) => {
              event.stopPropagation();
              const detailObj = {
                id: (wi.id || '') + '-' + (col.id || ''),
                type: (cellOp.op || '').toUpperCase(),
                name: (wi.work_item_name || '') + ' → ' + (col.entity_name || col.capability_name || ''),
                purpose: cellOp.desc || '',
                evidence: wi.source_evidence || [],
                evidenceType: wi.evidence_type || 'explicit',
                confidence: wi.confidence || 1.0
              };
              showDetail(detailObj, [], []);
            });
        }
      });
    });

    return startY + colHeaderH + rowsW * cellH;
  }

  // Matrix 1: WI x ENJ
  svg.append('text')
    .attr('x', rowHeaderW).attr('y', 24)
    .attr('fill', 'var(--ink)')
    .attr('font-size', 13).attr('font-weight', 700)
    .text('工作事项 × 业务实体');

  const enjLabels = entities.map(e => e.entity_name || '');
  const enjDomains = entities.map(e => e.entity_domain || '');
  const endY1 = renderMatrix(32, entities, enjLabels, enjDomains, (wi, enj) => {
    const op = (wi.entity_operations || []).find(o => o.entity_id === enj.id);
    return op ? { op: op.operation, desc: op.operation_description } : null;
  });

  // Matrix 2: WI x CAP
  const mat2Y = endY1 + titleH;
  svg.append('text')
    .attr('x', rowHeaderW).attr('y', mat2Y - 8)
    .attr('fill', 'var(--ink)')
    .attr('font-size', 13).attr('font-weight', 700)
    .text('工作事项 × 能力');

  const capLabels = capabilities.map(c => c.capability_name || '');
  renderMatrix(mat2Y, capabilities, capLabels, null, (wi, cap) => {
    const has = (wi.capability_ids || []).includes(cap.id);
    return has ? { op: 'create', desc: '需要 ' + (cap.capability_name || '') } : null;
  });

  svg.on('click', () => {
    const dp = document.getElementById('detailPanel');
    if (dp) dp.classList.remove('open');
  });
}

/* -------------------------------------------------------------------
 * Tab 切换
 * ------------------------------------------------------------------- */

function switchView(viewIndex) {
  activeViewIndex = viewIndex;
  document.querySelectorAll('.graph-view-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.view) === viewIndex);
  });
  document.querySelectorAll('.view-pane').forEach(pane => {
    const isActive = parseInt(pane.dataset.view) === viewIndex;
    pane.classList.toggle('active', isActive);
    pane.hidden = !isActive;
  });

  // handle zoom for view 1
  const svgEl = d3.select('#svgWrap svg');
  if (!svgEl.empty()) {
    if (viewIndex !== 1) {
      svgEl.on('.zoom', null);
    } else {
      if (svgEl._zoom) svgEl.call(svgEl._zoom);
    }
  }

  // show/hide legends
  const l1 = document.getElementById('legend1');
  const l2 = document.getElementById('legend2');
  const l3 = document.getElementById('legend3');
  if (l1) l1.hidden = (viewIndex !== 1);
  if (l2) l2.hidden = (viewIndex !== 2);
  if (l3) l3.hidden = (viewIndex !== 3);

  // lazy render
  if (!VIEW_RENDERED[viewIndex]) {
    VIEW_RENDERED[viewIndex] = true;
    if (lastRaw) {
      if (viewIndex === 1) renderView1(lastRaw);
      else if (viewIndex === 2) renderView2(lastRaw);
      else if (viewIndex === 3) renderView3(lastRaw);
    }
  }
}

function refreshGraphLayout() {
  if (!lastRaw) return;
  if (simForce) {
    simForce.stop();
    simForce = null;
  }
  if (activeViewIndex === 1) renderView1(lastRaw);
  else if (activeViewIndex === 2) renderView2(lastRaw);
  else if (activeViewIndex === 3) renderView3(lastRaw);
}

/* -------------------------------------------------------------------
 * 入口：renderGraph(data)
 * data = API 返回的 element_modeling 对象
 * ------------------------------------------------------------------- */

function renderGraph(data) {
  // 停止上一次 simulation
  if (simForce) {
    simForce.stop();
    simForce = null;
  }

  // 重置渲染状态
  VIEW_RENDERED[1] = false;
  VIEW_RENDERED[2] = false;
  VIEW_RENDERED[3] = false;
  activeViewIndex = 1;

  // 校验数据
  const raw = data || {};
  const hasAny =
    (raw.value_streams && raw.value_streams.length > 0) ||
    (raw.work_items && raw.work_items.length > 0) ||
    (raw.bussiness_entitys && raw.bussiness_entitys.length > 0) ||
    (raw.capabilities && raw.capabilities.length > 0);

  if (!hasAny) {
    renderEmptyGraph();
    return;
  }

  lastRaw = raw;

  // 绑定 tab 按钮事件
  document.querySelectorAll('.graph-view-btn').forEach(btn => {
    const clone = btn.cloneNode(true);
    btn.parentNode.replaceChild(clone, btn);
    clone.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      switchView(parseInt(clone.dataset.view));
    });
  });

  // 绑定详情面板关闭
  const dpClose = document.getElementById('dpClose');
  if (dpClose) {
    const newDpClose = dpClose.cloneNode(true);
    dpClose.parentNode.replaceChild(newDpClose, dpClose);
    newDpClose.addEventListener('click', () => {
      document.getElementById('detailPanel').classList.remove('open');
    });
  }

  // 延迟一帧确保容器可见且有尺寸
  requestAnimationFrame(() => {
    // 渲染默认视图（View 1 力导向图）
    switchView(1);
  });
}

// 暴露到全局
window.renderGraph = renderGraph;
window.refreshGraphLayout = refreshGraphLayout;
