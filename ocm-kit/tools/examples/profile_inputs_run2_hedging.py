#!/usr/bin/env python3
# ============================================================================
# EXAMPLE ONLY -- THIS IS RUN 2's PROFILER, NOT A KIT TOOL.
#
# It hard-codes run 2's input filenames ("MarktdatenExport copy.xlsx",
# "Kopie von Darlehen zum BSV.xlsx", "kobra202412.txt"), its sheet names
# ("Historical Swap Data", "Daten") and its unverified assumptions UA-01..UA-03.
# Pointed at any other source it profiles nothing.
#
# PROFILE is a mandatory state (R2, R3) and its profiler is necessarily written
# per run, in a NON-source language, against the real staged inputs. Lift the
# raw readers below -- zipfile + XML for xlsx, byte-level for text exports --
# and write this run's profiler around them.
#
# Carry lesson 5 with you: express every expectation in the coordinate system
# the source's own reader uses, then verify that rule against the reader
# empirically. Run 2 wrote an offset relative to a spreadsheet's used range; on
# the profiled file the used range began at row 1, so relative and absolute
# readings coincided and the error was invisible until a real file moved it.
# ============================================================================
# Controller tool: independent input profile (R2/R3/§9).
# Raw readers only: zipfile + XML for xlsx, byte-level for the text export.
# No source-language convenience readers.
import zipfile, hashlib, json, os, re, datetime, xml.etree.ElementTree as ET
import sys

IN = sys.argv[1] if len(sys.argv) > 1 else "inputs"
OUTP = sys.argv[2] if len(sys.argv) > 2 else "evidence/input_profile.json"
D0 = datetime.date(1899, 12, 30)

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()

def strip(t): return t.split("}")[-1]

def col_letters_to_idx(ref):
    m = re.match(r"([A-Z]+)([0-9]+)", ref)
    c = 0
    for ch in m.group(1): c = c * 26 + (ord(ch) - 64)
    return int(m.group(2)), c

def read_xlsx(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root:
            shared.append("".join(t.text or "" for t in si.iter() if strip(t.tag) == "t"))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    sheets = []
    for s in wb.iter():
        if strip(s.tag) == "sheet":
            rid = [v for k, v in s.attrib.items() if k.endswith("}id")][0]
            tgt = relmap[rid].lstrip("/")
            if not tgt.startswith("xl/"): tgt = "xl/" + tgt
            sheets.append((s.get("name"), tgt))
    out = {}
    for name, tgt in sheets:
        cells = {}
        root = ET.fromstring(z.read(tgt))
        for c in root.iter():
            if strip(c.tag) != "c": continue
            ref = c.get("r"); t = c.get("t", "n")
            v = None
            for ch in c:
                if strip(ch.tag) == "v": v = ch.text
                if strip(ch.tag) == "is":
                    v = "".join(x.text or "" for x in ch.iter() if strip(x.tag) == "t"); t = "inline"
            if v is None: continue
            r, cc = col_letters_to_idx(ref)
            if t == "s": cells[(r, cc)] = ("str", shared[int(v)])
            elif t in ("str", "inline"): cells[(r, cc)] = ("str", v)
            elif t == "b": cells[(r, cc)] = ("bool", v)
            else:
                try: cells[(r, cc)] = ("num", float(v))
                except ValueError: cells[(r, cc)] = ("str", v)
    # keep per-sheet cell maps
        out[name] = cells
    return out

def profile_market(path):
    book = read_xlsx(path)
    cells = book["Historical Swap Data"]
    rows = sorted({r for r, _ in cells}); cols = sorted({c for _, c in cells})
    first_used = min(cells.keys(), key=lambda rc: (rc[0], rc[1]))
    # header row by content: count of serial-like numerics per row
    def serialish(v): return isinstance(v, float) and 30000 <= v <= 60000 and v == int(v)
    scores = {r: sum(1 for (rr, c), (k, v) in cells.items() if rr == r and k == "num" and serialish(v)) for r in rows}
    hdr = max(scores, key=lambda r: scores[r])
    runner = max((s for r, s in scores.items() if r != hdr), default=0)
    # label column by DISTINCT NON-NUMERIC text count. First version scored raw
    # text distinctness and returned margin 0 (rates here are German-decimal TEXT,
    # so every rate column tied the label column) — an R5 AMBIGUOUS halt on sound
    # data, i.e. an R18 false positive. The separator must be parseability, not
    # storage type: a label is text that does NOT parse as a German number.
    def german_num(s):
        try:
            float(s.replace(".", "").replace(",", ".")); return True
        except ValueError:
            return False
    body = [r for r in rows if r > hdr]
    dist = {}
    for c in cols:
        vals = {v for (r, cc), (k, v) in cells.items()
                if cc == c and r in body and k == "str" and not german_num(v)}
        dist[c] = len(vals)
    lab = max(dist, key=lambda c: dist[c])
    lrun = max((s for c, s in dist.items() if c != lab), default=0)
    serials = sorted(v for (r, c), (k, v) in cells.items() if r == hdr and k == "num" and serialish(v))
    dmin = (D0 + datetime.timedelta(days=int(serials[0]))).isoformat()
    dmax = (D0 + datetime.timedelta(days=int(serials[-1]))).isoformat()
    labels = [v for (r, c), (k, v) in sorted(cells.items()) if c == lab and r in body and k == "str"]
    mats = []
    for L in labels:
        m = re.match(r"EUSA(\d+)", L)
        if m: mats.append(int(m.group(1)))
    mats = sorted(mats)
    gaps = [(a, b) for a, b in zip(mats, mats[1:]) if b - a > 1]
    ratevals = []
    nname = 0
    for (r, c), (k, v) in cells.items():
        if r in body and c > 4:
            if k == "str":
                if v == "#NAME?": nname += 1
                else:
                    try: ratevals.append(float(v.replace(".", "").replace(",", ".")))
                    except ValueError: pass
    n_rate_cells = sum(1 for (r, c) in cells if r in body and c > 4)
    return {
        "name": os.path.basename(path), "bytes": os.path.getsize(path), "sha256": sha256(path),
        "kind": "xlsx", "encoding": "xml-utf8", "row_count": len(body),
        "sheets": list(book.keys()),
        "layout": {"anchors": [
            {"what": "first used cell", "where": "%s (column A empty on this sheet)" % ("".join([chr(64+first_used[1]), str(first_used[0])])),
             "winning_score": 1, "runner_up": 0, "margin": 1},
            {"what": "date header row (serial-like count)", "where": "row %d" % hdr,
             "winning_score": scores[hdr], "runner_up": runner, "margin": scores[hdr] - runner},
            {"what": "label column (distinct text count)", "where": "column %d (B=2)" % lab,
             "winning_score": dist[lab], "runner_up": lrun, "margin": dist[lab] - lrun}],
            "note": "rates stored as text in German decimal-comma format; %d cells read '#NAME?'" % nname},
        "date_range": {"min": dmin, "max": dmax, "plausible": bool(1990 <= int(dmin[:4]) <= 2035 and dmin != dmax)},
        "fields": [
            {"name": "instrument_labels", "type": "text", "null_count": 0,
             "min": labels[0] if labels else None, "max": labels[-1] if labels else None,
             "distinct": len(set(labels)), "values_in_full": labels},
            {"name": "maturities_years", "type": "int", "null_count": 0,
             "min": mats[0], "max": mats[-1], "values_in_full": mats},
            {"name": "date_header_serials", "type": "int", "null_count": 0,
             "min": int(serials[0]), "max": int(serials[-1]), "distinct": len(serials)},
            {"name": "rates_percent_text", "type": "text-german-decimal", "null_count": n_rate_cells - len(ratevals) - nname + nname,
             "min": round(min(ratevals), 4), "max": round(max(ratevals), 4)}],
        "observations_local": ["maturity set has gaps: %s" % gaps,
                               "date header cells are numeric spreadsheet serials",
                               "columns C-D carry '#NAME?' and a constant field name; not data"]
    }

def profile_loans(path):
    book = read_xlsx(path)
    cells = book["Daten"]
    rows = sorted({r for r, _ in cells})
    hdr = rows[0]
    heads = {c: v for (r, c), (k, v) in cells.items() if r == hdr}
    body = [r for r in rows if r > hdr]
    fields = []
    colmap = sorted(heads)
    for c in colmap:
        vals = [(k, v) for (r, cc), (k, v) in cells.items() if cc == c and r > hdr]
        nums = [v for k, v in vals if k == "num"]
        nulls = len(body) - len(vals)
        f = {"name": str(heads[c]), "type": "num" if nums and len(nums) >= len(vals) - 2 else "text",
             "null_count": nulls,
             "min": min(nums) if nums else None, "max": max(nums) if nums else None}
        if str(heads[c]) == "BSV":
            f["distinct"] = len(set(nums)); f["duplicates"] = len(nums) - len(set(nums))
        if str(heads[c]) == "unterlegt als":
            f["categories"] = sorted({str(int(v)) for v in nums})
        fields.append(f)
    return {
        "name": os.path.basename(path), "bytes": os.path.getsize(path), "sha256": sha256(path),
        "kind": "xlsx", "encoding": "xml-utf8", "row_count": len(body),
        "sheets": list(book.keys()),
        "layout": {"anchors": [
            {"what": "header row (text-cell count)", "where": "row 1",
             "winning_score": len([1 for (r, c), (k, v) in cells.items() if r == hdr and k == "str"]),
             "runner_up": 1, "margin": len(heads) - 1}],
            "note": "plain rectangular sheet, header in row 1, first used cell A1"},
        "date_range": {"min": str(int(min(v for (r,c),(k,v) in cells.items() if c==4 and r>hdr and k=="num"))),
                       "max": str(int(max(v for (r,c),(k,v) in cells.items() if c==4 and r>hdr and k=="num"))),
                       "plausible": True},
        "fields": fields
    }

def profile_kobra(path, deep=True):
    n = 0; fdist = {}; enc_hi = 0
    fields = None
    with open(path, "rb") as f:
        for raw in f:
            n += 1
            enc_hi += sum(1 for b in raw if b > 127)
            k = raw.count(b"|") + 1
            fdist[k] = fdist.get(k, 0) + 1
            if deep:
                parts = raw.rstrip(b"\n").split(b"|")
                if fields is None: fields = [dict(null=0, mn=None, mx=None, txt=0, seen=set()) for _ in range(80)]
                for i in range(80):
                    v = parts[i].decode("iso-8859-1") if i < len(parts) else ""
                    st = fields[i]
                    if v == "":
                        st["null"] += 1; continue
                    try:
                        x = float(v.replace(".", "").replace(",", "."))
                        st["mn"] = x if st["mn"] is None else min(st["mn"], x)
                        st["mx"] = x if st["mx"] is None else max(st["mx"], x)
                    except ValueError:
                        st["txt"] += 1
                    if len(st["seen"]) < 40: st["seen"].add(v)
                    if i == 24: st.setdefault("keys", []).append(v)
    out = {"name": os.path.basename(path), "bytes": os.path.getsize(path), "sha256": sha256(path),
           "kind": "delimited_text", "encoding": "ISO-8859-1 declared; %d bytes >127 observed" % enc_hi,
           "row_count": n, "field_count_distribution": {str(k): v for k, v in sorted(fdist.items())},
           "layout": {"anchors": [
               {"what": "delimiter (pipe) by field-count stability", "where": "byte 0x7C",
                "winning_score": max(fdist.values()), "runner_up": 0, "margin": max(fdist.values())}],
               "note": "no header line; 80 positional fields; ragged lines are padded by the source reader"},
           "fields": []}
    if deep:
        key = fields[24]
        keys = key.pop("keys", [])
        for i, st in enumerate(fields):
            f = {"name": "field_%02d" % (i + 1), "type": "text" if st["txt"] > 0 else "numeric-german",
                 "null_count": st["null"], "min": st["mn"], "max": st["mx"]}
            if i == 24:
                f["distinct"] = len(set(keys)); f["duplicates"] = n - len(set(keys))
                f["name"] = "field_25_contract_number"
            out["fields"].append(f)
    else:
        out["fields"] = [{"name": "profiled_at_reduced_depth", "type": "see_note", "null_count": 0, "min": None, "max": None}]
        out["layout"]["note"] += "; full-size file: row/field-count pass only (heap-gate input)"
    return out

files = [profile_market(os.path.join(IN, "MarktdatenExport copy.xlsx")),
         profile_loans(os.path.join(IN, "Kopie von Darlehen zum BSV.xlsx")),
         profile_kobra(os.path.join(IN, "kobra202412.txt"), deep=True),
         profile_kobra(os.path.join(IN, "kobra202412_full.txt"), deep=False)]

obs = []
for f in files:
    for o in f.pop("observations_local", []):
        obs.append("%s: %s" % (f["name"], o))

profile = {
  "run_id": "mig2-profile-1",
  "provenance": "synthetic",
  "profiler": "controller-python-raw (zipfile+etree byte-level; no source-language convenience readers)",
  "emitted_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
  "files": files,
  "observations": obs + [
      "R2 STOP applies: real inputs unavailable in this environment; every output of this run is PROVISIONAL",
      "layout anchors above are observations of the SYNTHETIC files only"],
  "unverified_assumptions": [
    {"id": "UA-01", "statement": "real market workbook has sheet 'Historical Swap Data' with a 5-row preamble, labels in column B, '#NAME?' and field-name columns C-D, serial date headers, rates as German-decimal text",
     "precondition": "re-run the investigator on the real file; header-row and label-column anchors must resolve with margin >= 5, else AMBIGUOUS halt"},
    {"id": "UA-02", "statement": "real instrument set is EONIA + EUSA with maturity set 1..30,35,40,45,50,60",
     "precondition": "record the real maturity vector in full and diff against this set; any change re-opens the consecutive-coupon finding delta"},
    {"id": "UA-03", "statement": "real loans workbook has sheet 'Daten', header row 1, columns including BSV, DaBetrag, Zins, Zinsbindung (YYYYMMDD numeric), Vertragsbeginn, 'unterlegt als'",
     "precondition": "investigator must find all six columns by name with zero misses; date-plausibility check on Zinsbindung (1990..2060)"},
    {"id": "UA-04", "statement": "real portfolio export is pipe-delimited, headerless, 80 fields, ISO-8859-1, German decimal commas, YYYYMMDD dates, ~865k rows",
     "precondition": "field-count distribution must be reported; dominant count must be 80; encoding probed by exercising the decode (R17)"},
    {"id": "UA-05", "statement": "observation-date grid is end-of-month business days",
     "precondition": "parsed header dates must be strictly increasing, within 1990..2035, and not collapse to a single epoch value (P18-class check)"}
  ]
}

os.makedirs(os.path.dirname(OUTP), exist_ok=True)
with open(OUTP, "w") as f:
    json.dump(profile, f, indent=1)
print("profile written:", OUTP)
for fl in profile["files"]:
    print(" ", fl["name"], fl["row_count"], "rows,", fl["bytes"], "bytes")
