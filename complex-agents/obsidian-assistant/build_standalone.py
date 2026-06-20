"""
---
title: Obsidian Standalone Graph Builder
category: complex-agents
tags: [complex-agents, obsidian, knowledge-base, mobile, export]
difficulty: beginner
description: Bakes an Obsidian vault's knowledge graph into a single self-contained, mobile-friendly HTML file you can open anywhere (e.g. on a phone) with no server.
demonstrates:
  - Exporting a knowledge graph as a portable, offline-capable HTML file
  - Inlining graph data so the viewer needs no fetch/server (works from file://)
  - A touch-friendly D3 graph layout for mobile browsers
---

Build a standalone, phone-friendly graph viewer
===============================================

The interactive ``graph-viewer/index.html`` normally fetches
``vault/graph.json``, which needs a static server. This script instead inlines
the graph data into a single HTML file (``graph-viewer/standalone.html``) so you
can email/AirDrop it to a phone and open it directly — no server required.

    python build_standalone.py            # uses ./vault
    python build_standalone.py --vault ~/MyVault --out my-graph.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from obsidian_vault import ObsidianVault

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
  <title>__TITLE__</title>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  <style>
    :root {
      --bg:#1e1e1e; --panel:#252526; --border:#333; --text:#d4d4d4;
      --muted:#888; --accent:#7c6fd6; --accent-dim:#4a4470; --link:#555;
    }
    * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
    html,body { margin:0; height:100%; font-family:system-ui,sans-serif; background:var(--bg); color:var(--text); overflow:hidden; }
    #graph { position:fixed; inset:0; }
    .bar { position:fixed; top:0; left:0; right:0; display:flex; gap:8px; padding:10px; z-index:5; }
    input[type=search] { flex:1; background:var(--panel); color:var(--text); border:1px solid var(--border);
      border-radius:8px; padding:11px 12px; font-size:16px; }
    .node circle { cursor:pointer; }
    .node text { fill:var(--text); font-size:12px; pointer-events:none; }
    .node.dim { opacity:.12; }
    line.edge { stroke:var(--link); stroke-opacity:.6; }
    line.edge.hl { stroke:var(--accent); stroke-opacity:1; stroke-width:2; }
    /* Bottom sheet for note details (mobile-first). */
    #sheet { position:fixed; left:0; right:0; bottom:0; background:var(--panel);
      border-top:1px solid var(--border); border-radius:16px 16px 0 0; padding:16px 18px 24px;
      transform:translateY(110%); transition:transform .25s ease; z-index:10; max-height:55vh; overflow-y:auto; }
    #sheet.open { transform:translateY(0); }
    .grip { width:40px; height:4px; background:#555; border-radius:2px; margin:0 auto 12px; }
    .detail-title { font-size:20px; margin:0 0 10px; color:#fff; }
    .pill { display:inline-block; background:var(--accent-dim); color:#cfc8ff; border-radius:11px; padding:3px 10px; font-size:12px; margin:0 5px 5px 0; }
    .section { margin-top:14px; }
    .section h2 { font-size:12px; text-transform:uppercase; color:var(--muted); margin:0 0 6px; letter-spacing:.05em; }
    .section a { color:var(--accent); display:block; padding:7px 0; text-decoration:none; font-size:16px; }
    .empty { color:var(--muted); font-size:14px; }
    .hint { position:fixed; bottom:10px; left:0; right:0; text-align:center; color:var(--muted); font-size:12px; pointer-events:none; }
  </style>
</head>
<body>
  <div id="graph"></div>
  <div class="bar"><input id="search" type="search" placeholder="Filter notes…" /></div>
  <div id="sheet">
    <div class="grip"></div>
    <div id="detail"></div>
  </div>
  <div class="hint">Tap a note · drag to move · pinch to zoom</div>

  <script>
    const GRAPH = __GRAPH_DATA__;
    const W = () => window.innerWidth, H = () => window.innerHeight;

    const svg = d3.select('#graph').append('svg').attr('width','100%').attr('height','100%');
    const container = svg.append('g');
    svg.call(d3.zoom().scaleExtent([0.2,4]).on('zoom', e => container.attr('transform', e.transform)));

    const links = GRAPH.edges.map(e => ({ source:e.source, target:e.target }));
    const nodes = GRAPH.nodes.map(n => ({ ...n }));

    const link = container.append('g').selectAll('line').data(links).join('line').attr('class','edge');
    const node = container.append('g').selectAll('g').data(nodes).join('g').attr('class','node')
      .call(d3.drag()
        .on('start',(e,d)=>{ if(!e.active) sim.alphaTarget(.3).restart(); d.fx=d.x; d.fy=d.y; })
        .on('drag',(e,d)=>{ d.fx=e.x; d.fy=e.y; })
        .on('end',(e,d)=>{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }));

    node.append('circle')
      .attr('r', d => 9 + Math.min(16,(d.links+d.backlinks)*2))
      .attr('fill', d => (d.tags&&d.tags.length)?'var(--accent)':'#6a6a6a');
    node.append('text').attr('x',14).attr('y',5).text(d=>d.id);
    node.on('click',(_e,d)=>showDetail(d.id));

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d=>d.id).distance(90))
      .force('charge', d3.forceManyBody().strength(-320))
      .force('center', d3.forceCenter(W()/2, H()/2))
      .force('collide', d3.forceCollide(34))
      .on('tick', () => {
        link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
        node.attr('transform', d=>`translate(${d.x},${d.y})`);
      });

    function showDetail(id) {
      const n = nodes.find(x=>x.id===id); if(!n) return;
      const out = links.filter(e=>(e.source.id||e.source)===id).map(e=>e.target.id||e.target);
      const inc = links.filter(e=>(e.target.id||e.target)===id).map(e=>e.source.id||e.source);
      const list = arr => arr.length ? [...new Set(arr)].map(t=>`<a onclick="showDetail('${t.replace(/'/g,"\\\\'")}')">${t}</a>`).join('') : '<span class="empty">None</span>';
      document.getElementById('detail').innerHTML =
        `<div class="detail-title">${n.id}</div>` +
        `<div>${(n.tags||[]).map(t=>`<span class="pill">#${t}</span>`).join('')||'<span class="empty">no tags</span>'}</div>` +
        `<div class="section"><h2>Links to (${new Set(out).size})</h2>${list(out)}</div>` +
        `<div class="section"><h2>Backlinks (${new Set(inc).size})</h2>${list(inc)}</div>`;
      document.getElementById('sheet').classList.add('open');
      const conn = new Set([id,...out,...inc]);
      node.classed('dim', d=>!conn.has(d.id));
      link.classed('hl', d=>(d.source.id||d.source)===id||(d.target.id||d.target)===id);
    }

    document.getElementById('search').addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      node.classed('dim', d => q && !d.id.toLowerCase().includes(q));
    });
    // Tap empty space to close the sheet and clear highlights.
    svg.on('click', e => { if (e.target.tagName === 'svg') {
      document.getElementById('sheet').classList.remove('open');
      node.classed('dim', false); link.classed('hl', false);
    }});
  </script>
</body>
</html>
"""


def build(vault_dir: str | Path, out: str | Path | None = None, title: str = "My Knowledge Graph") -> Path:
    vault = ObsidianVault(vault_dir)
    graph = vault.build_graph()
    html = (
        TEMPLATE.replace("__GRAPH_DATA__", json.dumps(graph))
        .replace("__TITLE__", title)
    )
    out_path = Path(out) if out else Path(vault_dir).parent / "graph-viewer" / "standalone.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build a standalone, phone-friendly graph HTML.")
    p.add_argument("--vault", default="vault")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="My Knowledge Graph")
    args = p.parse_args(argv)
    path = build(args.vault, args.out, args.title)
    print(f"Wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
