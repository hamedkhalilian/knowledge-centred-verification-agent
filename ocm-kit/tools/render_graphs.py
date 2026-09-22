#!/usr/bin/env python3
# R10 FULL-tier artifacts: render graph_source.svg / graph_target.svg from the
# flow manifests (hand-written SVG; no libraries), plus the alias-applied diff.
#
# Unit order and run identity are taken from the per-run alias map, NOT baked
# into this tool. A hard-coded ORDER silently degenerates on any run whose
# units are named differently: every module falls into the same "unknown"
# bucket and the sort becomes a no-op, so the diagram looks rendered while
# expressing no declared order at all.
import json, html, os
import sys

src_path = sys.argv[1] if len(sys.argv) > 1 else "source_room/out/flow_manifest_source.json"
tgt_path = sys.argv[2] if len(sys.argv) > 2 else "evidence/flow_manifest_target.json"
alias_path = sys.argv[3] if len(sys.argv) > 3 else "contracts/alias_map.json"
out_dir = sys.argv[4] if len(sys.argv) > 4 else "evidence"

S = json.load(open(src_path))
T = json.load(open(tgt_path))
alias_doc = json.load(open(alias_path))
AL = {e["source"]: e["target"] for e in alias_doc["entries"]}

RUN_ID = alias_doc.get("run_id") or "(run id undeclared in %s)" % os.path.basename(alias_path)

# Declared unit order: the alias map's target ids, in the order the map lists
# them. Modules the map does not mention sort after them, by id, so an
# undeclared module is visibly last rather than silently interleaved.
ORDER = [e["target"].replace("mod:", "") for e in alias_doc["entries"]]
if not ORDER:
    print("render_graphs: alias map %s declares no entries; falling back to "
          "manifest order. The rendered order is NOT a declared order."
          % alias_path, file=sys.stderr)

def unit_of(m, alias):
    # map module ids to canonical unit order key
    def key(mid):
        u = alias.get(mid, mid).replace("mod:", "")
        return u
    return key

def render(man, alias, path, title):
    key = unit_of(man, alias)
    mods = [n for n in man["nodes"] if n["kind"] == "module"]
    objs = {n["id"]: n for n in man["nodes"] if n["kind"] == "object"}
    ins  = [n for n in man["nodes"] if n["id"].startswith("in:")]
    produced = {}   # module id -> [obj ids]
    for e in man["edges"]:
        if e["kind"] == "PRODUCE" and e["to"] in objs:
            produced.setdefault(e["from"], []).append(e["to"])
    reads = [(e["from"], e["to"]) for e in man["edges"] if e["kind"] == "READ" and not e["from"].startswith("in:") and not e["to"].startswith("in:")]
    mods.sort(key=lambda n: (ORDER.index(key(n["id"])) if key(n["id"]) in ORDER else len(ORDER),
                            key(n["id"])))

    ROW_H, OBJ_W, OBJ_H, MOD_W = 26, 232, 20, 250
    PAD, COLS = 14, 4
    rows = []
    y = 70
    mod_y = {}
    obj_pos = {}
    for m in mods:
        os_ = sorted(produced.get(m["id"], []))
        n_rows = max(1, (len(os_) + COLS - 1) // COLS)
        h = max(46, n_rows * ROW_H + 18)
        mod_y[m["id"]] = (y, h)
        for i, o in enumerate(os_):
            cx = 300 + (i % COLS) * (OBJ_W + 10)
            cy = y + 12 + (i // COLS) * ROW_H
            obj_pos[o] = (cx, cy)
        y += h + PAD
    H = y + 60
    W = 300 + COLS * (OBJ_W + 10) + 30

    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="Helvetica,Arial,sans-serif">' % (W, H, W, H))
    p.append('<rect width="%d" height="%d" fill="#fbfbf8"/>' % (W, H))
    p.append('<text x="24" y="34" font-size="19" font-weight="bold" fill="#1a1a1a">%s</text>' % html.escape(title))
    p.append('<text x="24" y="52" font-size="11" fill="#666">%d modules, %d objects, %d edges | provenance: %s</text>'
             % (len(mods), len(objs), len(man["edges"]), man["provenance"]))
    # read edges (thin, behind)
    for f, t_ in reads:
        if f in obj_pos and t_ in mod_y:
            x1, y1 = obj_pos[f][0], obj_pos[f][1] + OBJ_H / 2
            y2, _ = mod_y[t_]
            x2 = 24 + MOD_W
            ym = (y1 + y2 + 20) / 2
            p.append('<path d="M %d %d C %d %d, %d %d, %d %d" fill="none" stroke="#b9c6d8" stroke-width="0.8" opacity="0.7"/>'
                     % (x1, y1, x1 - 60, ym, x2 + 70, ym, x2, y2 + 20))
    for m in mods:
        y0, h = mod_y[m["id"]]
        lbl = key(m["id"])
        full = m["label"]
        p.append('<rect x="24" y="%d" width="%d" height="%d" rx="7" fill="#eef3fa" stroke="#5b83b8" stroke-width="1.3"/>' % (y0, MOD_W, h))
        p.append('<text x="36" y="%d" font-size="13" font-weight="bold" fill="#274a75">%s</text>' % (y0 + 19, html.escape(lbl)))
        if full != lbl:
            p.append('<text x="36" y="%d" font-size="10" fill="#4a6a94">%s</text>' % (y0 + 34, html.escape(full[:34])))
        for o in sorted(produced.get(m["id"], [])):
            cx, cy = obj_pos[o]
            name = objs[o]["label"]
            p.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#8fae8f" stroke-width="1"/>' % (24 + MOD_W, y0 + h / 2, cx, cy + OBJ_H / 2))
            p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="#f4f9f2" stroke="#7ba05b" stroke-width="0.9"/>' % (cx, cy, OBJ_W, OBJ_H))
            p.append('<text x="%d" y="%d" font-size="10" fill="#2f4a1f">%s</text>' % (cx + 6, cy + 14, html.escape(name[:36])))
    if ins:
        p.append('<text x="24" y="%d" font-size="11" fill="#8a6d3b">input files: %s</text>'
                 % (H - 26, html.escape(", ".join(n["label"] for n in ins))))
    p.append('<text x="24" y="%d" font-size="9" fill="#999">OCM v4.4 %s | R10 FULL artifact | boxes left: modules; right: published objects (PRODUCE solid, READ curves)</text>' % (H - 10, html.escape(RUN_ID)))
    p.append("</svg>")
    open(path, "w").write("\n".join(p))
    print("rendered", path, "(%dx%d)" % (W, H))

os.makedirs(out_dir, exist_ok=True)
render(S, AL, os.path.join(out_dir, "graph_source.svg"), "Data-flow graph — SOURCE (static analysis)")
render(T, {}, os.path.join(out_dir, "graph_target.svg"), "Data-flow graph — TARGET (dynamic, observed run)")
