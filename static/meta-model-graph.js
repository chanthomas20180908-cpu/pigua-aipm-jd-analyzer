/*
 * 目的：渲染 `/meta-model` 页面的图谱与定义双视图。
 * 定义：基于 D3 把元模型九节点关系图和文字定义面板同步展示。
 * 范围包括：
 * - 力导向图、点击选中、定义面板和节点库。
 * 范围不包括：
 * - 不请求后端接口，不修改数据源内容。
 * 使用与修改规则：
 * - 图谱数据由 `meta-model-data.js` 提供；若字段变化需同步面板渲染。
 */

(function () {
  if (!window.d3 || !window.META_MODEL_GRAPH_DATA) return;

  const DATA = window.META_MODEL_GRAPH_DATA;
  const SVG_ID = "metaGraphSvg";
  const WRAP_ID = "metaGraphWrap";
  const DETAIL_TITLE_ID = "metaNodeTitle";
  const DETAIL_SUMMARY_ID = "metaNodeSummary";
  const DETAIL_RELATIONS_ID = "metaNodeRelations";
  const LIBRARY_ID = "metaNodeLibrary";
  const FIT_ID = "metaFitView";

  const COLORS = {
    context: "#1f5b46",
    job: "#2f8d5b",
    flow: "#d69035",
    work: "#a0472d",
    entity: "#6b7c5b",
    capability: "#4c6f77",
    requirement: "#b57a34",
    environment: "#7d5c83",
    risk: "#d9534f",
  };

  const relationStroke = {
    context: "#1f5b46",
    primary: "#2f8d5b",
    entity: "#6b7c5b",
    capability: "#4c6f77",
    requirement: "#b57a34",
    environment: "#7d5c83",
    risk: "#d9534f",
  };

  const state = {
    selectedId: DATA.nodes[0] && DATA.nodes[0].id,
    simulation: null,
    resizeObserver: null,
  };

  function cloneNode(node) {
    return { ...node };
  }

  function buildGraph() {
    return {
      nodes: DATA.nodes.map(cloneNode),
      links: DATA.relations.map((relation) => ({ ...relation })),
    };
  }

  function nodeById(id) {
    return DATA.nodes.find((node) => node.id === id);
  }

  function relatedRelations(nodeId) {
    return DATA.relations.filter((relation) => relation.source === nodeId || relation.target === nodeId);
  }

  function relatedNodeIds(nodeId) {
    return relatedRelations(nodeId).map((relation) => (relation.source === nodeId ? relation.target : relation.source));
  }

  function escapeHtml(value) {
    const el = document.createElement("div");
    el.appendChild(document.createTextNode(String(value)));
    return el.innerHTML;
  }

  function renderDetail(node) {
    const title = document.getElementById(DETAIL_TITLE_ID);
    const summary = document.getElementById(DETAIL_SUMMARY_ID);
    const relations = document.getElementById(DETAIL_RELATIONS_ID);
    if (!title || !summary || !relations) return;

    const selected = node || DATA.nodes[0];
    const related = relatedNodeIds(selected.id).map(nodeById).filter(Boolean);

    title.textContent = selected.label;
    summary.textContent = selected.summary;

    const detailsHtml = selected.details
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("");

    const cardsHtml = selected.cards
      .map((item) => `<span class="meta-mini-chip">${escapeHtml(item)}</span>`)
      .join("");

    const relatedHtml = related
      .map((item) => `<span class="meta-link-chip" data-node-id="${item.id}">${escapeHtml(item.label)}</span>`)
      .join("");

    relations.innerHTML =
      `<div class="meta-detail-block">` +
      `<p class="meta-detail-label">怎么看</p>` +
      `<ul class="meta-detail-list">${detailsHtml}</ul>` +
      `</div>` +
      `<div class="meta-detail-block">` +
      `<p class="meta-detail-label">字段抓手</p>` +
      `<div class="meta-chip-row">${cardsHtml}</div>` +
      `</div>` +
      `<div class="meta-detail-block">` +
      `<p class="meta-detail-label">关联节点</p>` +
      `<div class="meta-chip-row">${relatedHtml || '<span class="meta-empty">无</span>'}</div>` +
      `</div>`;

    relations.querySelectorAll("[data-node-id]").forEach((chip) => {
      chip.addEventListener("click", () => {
        const nextNode = nodeById(chip.getAttribute("data-node-id"));
        if (nextNode) {
          state.selectedId = nextNode.id;
          renderDetail(nextNode);
          updateLibrarySelection();
          highlightNode(nextNode.id);
        }
      });
    });
  }

  function renderLibrary() {
    const mount = document.getElementById(LIBRARY_ID);
    if (!mount) return;

    mount.innerHTML = DATA.nodes
      .map(
        (node) =>
          `<button class="meta-library-card" type="button" data-node-id="${node.id}">` +
          `<span class="meta-library-kind">${escapeHtml(node.label)}</span>` +
          `<strong>${escapeHtml(node.summary)}</strong>` +
          `</button>`
      )
      .join("");

    mount.querySelectorAll("[data-node-id]").forEach((button) => {
      button.addEventListener("click", () => {
        const nextNode = nodeById(button.getAttribute("data-node-id"));
        if (nextNode) {
          state.selectedId = nextNode.id;
          renderDetail(nextNode);
          updateLibrarySelection();
          highlightNode(nextNode.id);
        }
      });
    });
  }

  function updateLibrarySelection() {
    const mount = document.getElementById(LIBRARY_ID);
    if (!mount) return;
    mount.querySelectorAll(".meta-library-card").forEach((button) => {
      button.classList.toggle("is-active", button.getAttribute("data-node-id") === state.selectedId);
    });
  }

  function highlightNode(nodeId) {
    const svg = d3.select(`#${SVG_ID}`);
    if (svg.empty()) return;
    svg.selectAll(".meta-node").classed("is-active", (d) => d.id === nodeId);
    svg.selectAll(".meta-link").classed("is-active", (d) => d.source.id === nodeId || d.target.id === nodeId);
  }

  function renderGraph() {
    const wrap = document.getElementById(WRAP_ID);
    const svgNode = document.getElementById(SVG_ID);
    const fitButton = document.getElementById(FIT_ID);
    if (!wrap || !svgNode) return;

    const { nodes, links } = buildGraph();
    const width = Math.max(760, wrap.clientWidth || 0);
    const height = Math.max(540, wrap.clientHeight || 0);

    const svg = d3.select(svgNode);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const root = svg.append("g").attr("class", "meta-graph-root");

    const zoom = d3.zoom().scaleExtent([0.35, 2.4]).on("zoom", (event) => {
      root.attr("transform", event.transform);
    });
    svg.call(zoom);
    svg.node().__zoom = d3.zoomIdentity;

    const defs = svg.append("defs");
    defs
      .selectAll("marker")
      .data(["context", "primary", "entity", "capability", "requirement", "environment", "risk"])
      .join("marker")
      .attr("id", (d) => `meta-arrow-${d}`)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 18)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", (d) => relationStroke[d] || "#667067");

    const link = root
      .append("g")
      .attr("class", "meta-links")
      .selectAll("g")
      .data(links)
      .join("g")
      .attr("class", "meta-link");

    link
      .append("line")
      .attr("stroke", (d) => relationStroke[d.kind] || "#667067")
      .attr("stroke-width", 1.8)
      .attr("stroke-dasharray", (d) => {
        if (d.kind === "requirement") return "6 4";
        if (d.kind === "environment") return "4 4";
        if (d.kind === "risk") return "2 5";
        return "0";
      })
      .attr("marker-end", (d) => `url(#meta-arrow-${d.kind})`);

    link
      .append("text")
      .attr("class", "meta-link-label")
      .attr("text-anchor", "middle")
      .attr("dy", -6)
      .text((d) => d.label);

    const node = root
      .append("g")
      .attr("class", "meta-nodes")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "meta-node")
      .attr("tabindex", 0)
      .attr("role", "button")
      .attr("aria-label", (d) => `查看${d.label}的定义`)
      .call(
        d3.drag()
          .on("start", (event, d) => {
            if (!event.active && state.simulation) state.simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active && state.simulation) state.simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    node
      .append("circle")
      .attr("r", (d) => d.radius || 28)
      .attr("fill", (d) => COLORS[d.kind] || "#667067")
      .attr("stroke", "#f7f2e9")
      .attr("stroke-width", 3);

    node
      .append("text")
      .attr("class", "meta-node-label")
      .attr("text-anchor", "middle")
      .attr("dy", -4)
      .text((d) => d.label);

    node
      .append("text")
      .attr("class", "meta-node-subtitle")
      .attr("text-anchor", "middle")
      .attr("dy", 15)
      .text((d) => d.kind.toUpperCase());

    const simulation = d3
      .forceSimulation(nodes)
      .force("link", d3.forceLink(links).id((d) => d.id).distance((d) => (d.kind === "primary" ? 130 : 148)).strength(0.85))
      .force("charge", d3.forceManyBody().strength(-760))
      .force("collide", d3.forceCollide().radius((d) => (d.radius || 28) + 16))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(0.06))
      .force("y", d3.forceY(height / 2).strength(0.06));

    state.simulation = simulation;

    simulation.on("tick", () => {
      link.select("line")
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);

      link.select("text")
        .attr("x", (d) => (d.source.x + d.target.x) / 2)
        .attr("y", (d) => (d.source.y + d.target.y) / 2);

      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    node
      .on("click", (_, d) => {
        state.selectedId = d.id;
        renderDetail(d);
        updateLibrarySelection();
        highlightNode(d.id);
      })
      .on("mouseenter", (_, d) => {
        highlightNode(d.id);
      })
      .on("mouseleave", () => {
        highlightNode(state.selectedId);
      })
      .on("keydown", (event, d) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          state.selectedId = d.id;
          renderDetail(d);
          updateLibrarySelection();
          highlightNode(d.id);
        }
      });

    renderDetail(nodeById(state.selectedId));
    updateLibrarySelection();
    highlightNode(state.selectedId);

    if (fitButton) {
      fitButton.addEventListener("click", () => {
        const bounds = svgNode.getBBox();
        const dx = bounds.width;
        const dy = bounds.height;
        const scale = Math.min(1.2, 0.82 / Math.max(dx / width, dy / height));
        const translate = [
          width / 2 - scale * (bounds.x + dx / 2),
          height / 2 - scale * (bounds.y + dy / 2),
        ];
        svg
          .transition()
          .duration(500)
          .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
      });
    }

    if ("ResizeObserver" in window) {
      if (state.resizeObserver) {
        state.resizeObserver.disconnect();
      }
      state.resizeObserver = new ResizeObserver(() => {
        const nextWidth = Math.max(760, wrap.clientWidth || 0);
        const nextHeight = Math.max(540, wrap.clientHeight || 0);
        simulation.force("center", d3.forceCenter(nextWidth / 2, nextHeight / 2));
        simulation.force("x", d3.forceX(nextWidth / 2).strength(0.06));
        simulation.force("y", d3.forceY(nextHeight / 2).strength(0.06));
        svg.attr("viewBox", `0 0 ${nextWidth} ${nextHeight}`);
        simulation.alpha(0.3).restart();
      });
      state.resizeObserver.observe(wrap);
    }
  }

  function init() {
    renderLibrary();
    renderGraph();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
