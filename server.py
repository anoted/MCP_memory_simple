from __future__ import annotations

import json
from urllib.parse import urlencode
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from memory_store import (
    create_link,
    create_memory_record,
    graph_snapshot,
    graph_search,
    initialize_store,
    link_candidates,
    query_graph_snapshot,
    update_memory,
)


mcp = FastMCP(
    "Hybrid Graph Memory MCP",
    instructions=(
        "File-backed teaching demo for hybrid graph memory. "
        "Stores records, entities, graph edges, deterministic embeddings, timestamps, and provenance."
    ),
    host="127.0.0.1",
    port=2618,
    streamable_http_path="/mcp",
)


@mcp.tool()
def memory_record(text: str, source: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Record a memory, extract simple entities, embed it, and propose graph links."""
    return create_memory_record(text=text, source=source, tags=tags)


@mcp.tool()
def memory_link_candidates(record_id: str, top_k: int = 10) -> dict[str, Any]:
    """Find record and entity candidates that may be related to a memory."""
    return link_candidates(record_id=record_id, top_k=top_k)


@mcp.tool()
def memory_create_link(
    from_id: str,
    to_id: str,
    link_type: str,
    reason: str,
    confidence: float,
) -> dict[str, Any]:
    """Create a verified graph edge between two records or a record and entity."""
    return create_link(
        from_id=from_id,
        to_id=to_id,
        link_type=link_type,
        reason=reason,
        confidence=confidence,
    )


@mcp.tool()
def memory_graph_search(query: str, hops: int = 2, top_k: int = 10) -> dict[str, Any]:
    """Search records, expand through verified graph links, and return evidence."""
    return graph_search(query=query, hops=hops, top_k=top_k)


@mcp.tool()
def memory_update(record_id: str, new_text: str, update_type: str, reason: str) -> dict[str, Any]:
    """Create a new memory linked to an old one instead of overwriting history."""
    return update_memory(
        record_id=record_id,
        new_text=new_text,
        update_type=update_type,
        reason=reason,
    )


@mcp.tool()
def memory_graph_app() -> dict[str, str]:
    """Return the local app URL for visualizing the complete memory graph."""
    return {
        "name": "Complete Memory Graph",
        "url": "http://localhost:2618/apps/memory-graph",
        "json_url": "http://localhost:2618/apps/memory-graph.json",
    }


@mcp.tool()
def memory_query_graph_app(query: str = "MCP course learning outcomes", hops: int = 2, top_k: int = 10) -> dict[str, str]:
    """Return the local app URL for visualizing query-related memory graph levels."""
    params = urlencode({"q": query, "hops": hops, "top_k": top_k})
    return {
        "name": "Query Memory Graph",
        "url": f"http://localhost:2618/apps/query-graph?{params}",
        "json_url": f"http://localhost:2618/apps/query-graph.json?{params}",
    }


@mcp.custom_route("/apps/memory-graph.json", methods=["GET"])
async def memory_graph_json(request: Request) -> JSONResponse:
    return JSONResponse(graph_snapshot())


@mcp.custom_route("/apps/query-graph.json", methods=["GET"])
async def query_graph_json(request: Request) -> JSONResponse:
    query = request.query_params.get("q") or "MCP course learning outcomes"
    hops = _int_param(request, "hops", 2)
    top_k = _int_param(request, "top_k", 10)
    return JSONResponse(query_graph_snapshot(query=query, hops=hops, top_k=top_k))


@mcp.custom_route("/apps/memory-graph", methods=["GET"])
async def memory_graph_app_route(request: Request) -> HTMLResponse:
    data = graph_snapshot()
    return HTMLResponse(_render_graph_app(data, mode="all"))


@mcp.custom_route("/apps/query-graph", methods=["GET"])
async def query_graph_app_route(request: Request) -> HTMLResponse:
    query = request.query_params.get("q") or "MCP course learning outcomes"
    hops = _int_param(request, "hops", 2)
    top_k = _int_param(request, "top_k", 10)
    data = query_graph_snapshot(query=query, hops=hops, top_k=top_k)
    return HTMLResponse(_render_graph_app(data, mode="query"))


def _int_param(request: Request, name: str, default: int) -> int:
    try:
        return int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        return default


def _render_graph_app(data: dict[str, Any], mode: str) -> str:
    title = "Complete Memory Graph" if mode == "all" else "Query Memory Graph"
    data_json = json.dumps(data)
    controls = ""
    if mode == "query":
        query = str(data.get("query", ""))
        hops = int(data.get("hops", 2))
        top_k = int(data.get("top_k", 10))
        controls = f"""
        <form class="toolbar" method="get" action="/apps/query-graph">
          <input name="q" value="{_escape_attr(query)}" aria-label="Query" />
          <label>Hops <input name="hops" type="number" min="0" max="4" value="{hops}" /></label>
          <label>Top K <input name="top_k" type="number" min="1" max="50" value="{top_k}" /></label>
          <button type="submit">Search</button>
          <a class="button" href="/apps/query-graph.json?{urlencode({'q': query, 'hops': hops, 'top_k': top_k})}">JSON</a>
        </form>
        """
    else:
        controls = '<div class="toolbar"><a class="button" href="/apps/memory-graph.json">JSON</a><a class="button" href="/apps/query-graph">Query graph</a></div>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --line: #cbd5e1;
      --text: #0f172a;
      --muted: #475569;
      --record: #2563eb;
      --direct: #16a34a;
      --entity: #d97706;
      --old: #94a3b8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    h1 {{ font-size: 18px; margin: 0; letter-spacing: 0; }}
    .toolbar {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
      min-width: 300px;
    }}
    input {{
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 8px;
      font-size: 14px;
      min-width: 280px;
    }}
    input[type="number"] {{ width: 72px; min-width: 72px; }}
    label {{ color: var(--muted); font-size: 13px; display: inline-flex; align-items: center; gap: 6px; }}
    button, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      text-decoration: none;
      font-size: 14px;
      cursor: pointer;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 12px;
      padding: 12px;
    }}
    .graph, aside {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    svg {{ display: block; width: 100%; min-height: 640px; }}
    aside {{ padding: 14px; max-height: calc(100vh - 78px); overflow: auto; }}
    h2 {{ font-size: 14px; margin: 0 0 10px; }}
    .stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 14px; }}
    .stat {{ border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: #f8fafc; }}
    .stat strong {{ display: block; font-size: 18px; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .details {{ border-top: 1px solid var(--line); padding-top: 12px; }}
    .details p {{ margin: 6px 0; line-height: 1.35; }}
    .muted {{ color: var(--muted); }}
    .pill {{ display: inline-block; padding: 2px 6px; border-radius: 999px; background: #e2e8f0; font-size: 12px; margin-right: 4px; }}
    .evidence {{ margin: 0; padding: 0; list-style: none; }}
    .evidence li {{ border-top: 1px solid var(--line); padding: 8px 0; }}
    .node text {{ font-size: 12px; paint-order: stroke; stroke: #fff; stroke-width: 4px; stroke-linejoin: round; fill: var(--text); }}
    .edge {{ stroke: #94a3b8; stroke-width: 1.25; opacity: 0.72; }}
    .edge-label {{ font-size: 10px; fill: #475569; }}
    @media (max-width: 980px) {{
      header, main {{ display: block; }}
      .toolbar {{ justify-content: flex-start; margin-top: 10px; }}
      main {{ padding: 8px; }}
      aside {{ margin-top: 8px; max-height: none; }}
      input {{ min-width: 180px; width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    {controls}
  </header>
  <main>
    <section class="graph"><svg id="graph" role="img"></svg></section>
    <aside>
      <h2>Stats</h2>
      <div id="stats" class="stats"></div>
      <div id="evidence-wrap"></div>
      <div class="details" id="details">
        <h2>Selection</h2>
        <p class="muted">Select a node in the graph.</p>
      </div>
    </aside>
  </main>
  <script>
    const graphData = {data_json};
    const mode = {json.dumps(mode)};
    const svg = document.getElementById("graph");
    const details = document.getElementById("details");
    const width = 1120;
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    const short = (value, limit=82) => {{
      const text = String(value ?? "");
      return text.length > limit ? text.slice(0, limit - 1) + "..." : text;
    }};
    function color(node) {{
      if (node.status === "superseded") return "var(--old)";
      if (node.direct_match) return "var(--direct)";
      if (node.kind === "entity") return "var(--entity)";
      return "var(--record)";
    }}
    function layout(nodes) {{
      const records = nodes.filter(n => n.kind === "record").sort((a, b) => (a.level ?? 9) - (b.level ?? 9) || a.id.localeCompare(b.id));
      const entities = nodes.filter(n => n.kind === "entity").sort((a, b) => a.label.localeCompare(b.label));
      const height = Math.max(640, (Math.max(records.length, entities.length) + 2) * 62);
      const levelCounts = new Map();
      const entityX = mode === "query" ? 950 : 720;
      for (const node of records) {{
        const level = mode === "query" ? Number(node.level ?? 0) : 0;
        const count = levelCounts.get(level) || 0;
        levelCounts.set(level, count + 1);
        node.x = mode === "query" ? 92 + level * 235 : 96;
        node.y = 76 + count * 62;
      }}
      entities.forEach((node, index) => {{
        node.x = entityX;
        node.y = 76 + index * 46;
      }});
      return height;
    }}
    function draw() {{
      const nodes = graphData.nodes || [];
      const edges = graphData.edges || [];
      const nodeById = new Map(nodes.map(n => [n.id, n]));
      const height = layout(nodes);
      svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
      svg.innerHTML = "";

      const labels = document.createElementNS("http://www.w3.org/2000/svg", "g");
      labels.innerHTML = mode === "query"
        ? '<text x="76" y="32" class="edge-label">Direct</text><text x="310" y="32" class="edge-label">Level 1</text><text x="545" y="32" class="edge-label">Level 2+</text><text x="925" y="32" class="edge-label">Entities</text>'
        : '<text x="72" y="32" class="edge-label">Records</text><text x="696" y="32" class="edge-label">Entities</text>';
      svg.appendChild(labels);

      for (const edge of edges) {{
        const a = nodeById.get(edge.source);
        const b = nodeById.get(edge.target);
        if (!a || !b) continue;
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", a.x);
        line.setAttribute("y1", a.y);
        line.setAttribute("x2", b.x);
        line.setAttribute("y2", b.y);
        line.setAttribute("class", "edge");
        line.innerHTML = `<title>${{esc(edge.type)}}: ${{esc(edge.reason)}}</title>`;
        svg.appendChild(line);
        if (edge.type !== "mentions") {{
          const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
          label.setAttribute("x", (a.x + b.x) / 2);
          label.setAttribute("y", (a.y + b.y) / 2 - 4);
          label.setAttribute("class", "edge-label");
          label.textContent = edge.type;
          svg.appendChild(label);
        }}
      }}

      for (const node of nodes) {{
        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.setAttribute("class", "node");
        group.setAttribute("tabindex", "0");
        group.style.cursor = "pointer";
        group.addEventListener("click", () => showNode(node));
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", node.x);
        circle.setAttribute("cy", node.y);
        circle.setAttribute("r", node.direct_match ? "12" : "9");
        circle.setAttribute("fill", color(node));
        circle.setAttribute("stroke", "#ffffff");
        circle.setAttribute("stroke-width", "2");
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", node.x + 16);
        text.setAttribute("y", node.y + 4);
        text.textContent = node.kind === "record" ? `${{node.id}} ${{short(node.text, 54)}}` : short(node.label, 38);
        group.appendChild(circle);
        group.appendChild(text);
        svg.appendChild(group);
      }}
    }}
    function showNode(node) {{
      const tags = (node.tags || []).map(tag => `<span class="pill">${{esc(tag)}}</span>`).join("");
      const status = node.status ? `<p><strong>Status:</strong> ${{esc(node.status)}}</p>` : "";
      const score = node.score ? `<p><strong>Score:</strong> ${{esc(node.score)}}</p>` : "";
      const level = node.level !== undefined ? `<p><strong>Level:</strong> ${{esc(node.level)}}</p>` : "";
      details.innerHTML = `<h2>${{esc(node.id)}}</h2>
        <p>${{esc(node.text || node.label)}}</p>
        ${{status}}${{score}}${{level}}
        <p><strong>Type:</strong> ${{esc(node.type || node.kind)}}</p>
        <p>${{tags}}</p>
        <p class="muted">${{esc(node.source || "")}} ${{esc(node.created_at || "")}}</p>`;
    }}
    function drawStats() {{
      const stats = graphData.stats || {{}};
      document.getElementById("stats").innerHTML = Object.entries(stats).map(([key, value]) =>
        `<div class="stat"><strong>${{esc(value)}}</strong><span>${{esc(key.replaceAll("_", " "))}}</span></div>`
      ).join("");
    }}
    function drawEvidence() {{
      const wrap = document.getElementById("evidence-wrap");
      const evidence = graphData.evidence || [];
      if (!evidence.length) {{
        wrap.innerHTML = "";
        return;
      }}
      wrap.innerHTML = `<h2>Evidence</h2><ul class="evidence">${{evidence.map(item =>
        `<li><strong>${{esc(item.record.id)}}</strong> <span class="muted">${{esc(item.status)}} score ${{esc(item.score)}}</span><br>${{esc(item.record.text)}}</li>`
      ).join("")}}</ul>`;
    }}
    drawStats();
    drawEvidence();
    draw();
  </script>
</body>
</html>"""


def _escape_attr(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


if __name__ == "__main__":
    initialize_store()
    mcp.run(transport="streamable-http")
