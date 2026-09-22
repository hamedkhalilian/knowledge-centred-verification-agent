#!/usr/bin/env python3
# Controller COMPARE (ladder layer 5): source vs target checkpoint digests.
import json, sys, datetime
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "evidence/checkpoints_source.json"
TGT = sys.argv[2] if len(sys.argv) > 2 else "evidence/checkpoints_target.json"
OUT = sys.argv[3] if len(sys.argv) > 3 else "evidence/comparison_layer5.json"

s = json.load(open(SRC)); t = json.load(open(TGT))

# inputs must agree byte-for-byte (contract section 7)
si = {(i["name"], i["sha256"], i["bytes"]) for i in s["inputs"]}
ti = {(i["name"], i["sha256"], i["bytes"]) for i in t["inputs"]}
inputs_ok = si == ti

def index(ck):
    d = {}
    for u in ck["units"]:
        for o in u["objects"]:
            d[(u["unit"], o["name"])] = o
    return d

S, T = index(s), index(t)
keys_s, keys_t = set(S), set(T)
only_s = sorted(keys_s - keys_t); only_t = sorted(keys_t - keys_s)
common = sorted(keys_s & keys_t)

agree, differ = [], []
for k in common:
    a, b = S[k], T[k]
    if a["digest"]["value"] == b["digest"]["value"] and \
       a["digest"]["canonicalisation"] == b["digest"]["canonicalisation"]:
        agree.append(k)
    else:
        # localise: shape, then probes
        loc = {"unit": k[0], "object": k[1],
               "rows": [a.get("rows"), b.get("rows")],
               "cols": [a.get("cols"), b.get("cols")],
               "colnames_differ": a.get("colnames") != b.get("colnames"),
               "coverage_src": a.get("coverage"), "coverage_tgt": b.get("coverage"),
               "probe_diffs": []}
        for pa, pb in zip(a.get("probes", []), b.get("probes", [])):
            if pa["fields"] != pb["fields"]:
                fd = {f: (pa["fields"].get(f), pb["fields"].get(f))
                      for f in set(pa["fields"]) | set(pb["fields"])
                      if pa["fields"].get(f) != pb["fields"].get(f)}
                loc["probe_diffs"].append({"rule": pa["selection_rule"], "fields": fd})
        differ.append(loc)

report = {
  "state": "COMPARE", "layer": 5,
  "emitted_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
  "source_file": SRC, "target_file": TGT,
  "inputs_bound_identically": inputs_ok,
  "objects_source": len(keys_s), "objects_target": len(keys_t),
  "only_in_source": only_s, "only_in_target": only_t,
  "agree": len(agree), "differ": len(differ),
  "divergences": differ}
json.dump(report, open(OUT, "w"), indent=1)

print("inputs bound identically:", inputs_ok)
print("objects: source %d | target %d | common %d" % (len(keys_s), len(keys_t), len(common)))
print("AGREE (byte-identical digests): %d" % len(agree))
print("DIFFER: %d" % len(differ))
for d in differ:
    print(" - %s :: %s  rows %s cols %s colnames_differ=%s probe_diffs=%d" %
          (d["unit"], d["object"], d["rows"], d["cols"], d["colnames_differ"], len(d["probe_diffs"])))
if only_s: print("only in source:", only_s)
if only_t: print("only in target:", only_t)
