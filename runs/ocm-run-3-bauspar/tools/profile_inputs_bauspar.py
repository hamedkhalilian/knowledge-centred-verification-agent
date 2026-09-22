#!/usr/bin/env python3
"""Run 3 input profiler -- emits input_profile.json (PROFILE, §9/R2/R3).

Written per run, in a NON-source language, using raw readers only: no R, and
no convenience reader that would reproduce the source's own parsing decisions
and so hide a disagreement with them (§9).

R3: small structurally decisive vectors are recorded as VALUES, not counts.
Run 2's only divergence came from a spec that stated a name list as a count
plus constraints; two lists satisfied the constraints and the implementer
guessed wrong. Every column here whose distinct values are few enough to be
decisive is written out in full.

R2: provenance is `synthetic`, and this is not a formality. The real input
table is absent from the bundle (DISCOVER finding F1), so every fact below
describes a stand-in. Nothing here may harden into a contract the target
enforces against real data.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
import re

VALUES_IN_FULL_MAX = 24
EMPTY_MARKERS = {"", "0", "00", "0000", "00000000", "NA", "<NA>"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YYYYMMDD = re.compile(r"^\d{8}$")
DE_NUMBER = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d+$|^-?\d+,\d+$")
PLAIN_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def classify(value):
    if value in EMPTY_MARKERS:
        return "empty_marker"
    if ISO_DATE.match(value):
        return "date_iso"
    if YYYYMMDD.match(value):
        return "date_yyyymmdd"
    if DE_NUMBER.match(value):
        return "number_de_comma"
    if PLAIN_NUMBER.match(value):
        return "number_plain"
    return "text"


def to_number(value):
    if DE_NUMBER.match(value):
        return float(value.replace(".", "").replace(",", "."))
    if PLAIN_NUMBER.match(value):
        return float(value)
    return None


def to_date(value):
    try:
        if ISO_DATE.match(value):
            return datetime.date.fromisoformat(value)
        if YYYYMMDD.match(value):
            return datetime.datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None
    return None


def profile_file(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    reader = csv.DictReader(text.splitlines())
    columns = list(reader.fieldnames)
    rows = list(reader)

    # Field-count distribution: ragged files are where positional readers
    # mis-assign silently (§9). Recorded even when the file is rectangular,
    # because "it was rectangular" is itself the observation.
    #
    # Counted with a real CSV reader, NOT line.split(","). The first version of
    # this profiler split on commas and reported 11/14/15 fields per line --
    # false raggedness on a file that is exactly rectangular, because German
    # decimal-comma amounts are quoted and contain commas. A controller
    # detector that cries wolf on sound input is lessons finding 7, and it had
    # reappeared here in a tool written to enforce the lessons.
    counts = collections.Counter(len(r) for r in csv.reader(text.splitlines()))

    # The naive reading is still worth recording -- as a hazard for the target,
    # not as a property of the file. Any implementation that hand-rolls a comma
    # splitter instead of parsing CSV quoting will mis-assign exactly these
    # lines, and will do so silently.
    naive_counts = collections.Counter(len(line.split(",")) for line in lines[1:])
    quoted_lines = sum(1 for line in lines[1:] if '"' in line)

    fields = []
    for name in columns:
        values = [r[name] if r[name] is not None else "" for r in rows]
        kinds = collections.Counter(classify(v) for v in values)
        nulls = sum(1 for v in values if v in EMPTY_MARKERS)
        distinct = sorted(set(values))
        numbers = [n for n in (to_number(v) for v in values) if n is not None]
        dates = [d for d in (to_date(v) for v in values) if d is not None]

        entry = {
            "name": name,
            "type": "+".join("%s:%d" % (k, c) for k, c in sorted(kinds.items())),
            "null_count": nulls,
            "min": None,
            "max": None,
            "distinct": len(distinct),
            "duplicates": len(values) - len(distinct),
        }
        if numbers:
            entry["min"] = min(numbers)
            entry["max"] = max(numbers)
        elif dates:
            entry["min"] = min(dates).isoformat()
            entry["max"] = max(dates).isoformat()
        if len(distinct) <= VALUES_IN_FULL_MAX:
            entry["values_in_full"] = distinct          # R3: values, not a count
            entry["categories"] = distinct
        if numbers:
            mags = collections.Counter()
            for n in numbers:
                if n == 0:
                    mags["0"] += 1
                else:
                    mags[str(len(str(int(abs(n)))))] += 1
            entry["magnitude_distribution"] = dict(sorted(mags.items()))
        fields.append(entry)

    all_dates = [d for r in rows for d in
                 (to_date(r[c] or "") for c in columns) if d is not None]

    return {
        "name": os.path.basename(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "kind": "delimited_text",
        "encoding": "utf-8",
        "row_count": len(rows),
        "field_count_distribution": {str(k): v for k, v in sorted(counts.items())},
        "layout": {
            "anchors": [{
                "what": "quoting hazard: fields per line under a naive comma split",
                "where": "%d of %d data lines carry quoted commas; naive split sees %s"
                         % (quoted_lines, len(lines) - 1,
                            dict(sorted(naive_counts.items()))),
                "winning_score": float(max(counts)),
                "runner_up": float(max(naive_counts)),
                "margin": float(max(naive_counts) - max(counts)),
            }, {
                "what": "header row",
                "where": "line 1",
                "winning_score": 1.0,
                "runner_up": 0.0,
                "margin": 1.0,
            }],
            "note": "Generated file: the header is at line 1 by construction, so "
                    "this anchor is asserted, not discovered. On a real input it "
                    "would have to be scored against alternatives -- and the score "
                    "expressed in the coordinate system the source's own reader "
                    "uses, then checked against that reader empirically (lessons, "
                    "finding 5).",
        },
        "date_range": {
            "min": min(all_dates).isoformat() if all_dates else None,
            "max": max(all_dates).isoformat() if all_dates else None,
            "plausible": bool(all_dates and
                              min(all_dates) > datetime.date(1950, 1, 1) and
                              max(all_dates) < datetime.date(2100, 1, 1)),
        },
        "fields": fields,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--inputs", default="source_room/inputs/merged_data_synthetic.csv")
    parser.add_argument("--out", default="runs/ocm-run-3-bauspar/evidence/input_profile.json")
    parser.add_argument("--run-id", default="ocm-run-3-bauspar")
    args = parser.parse_args()

    profile = {
        "run_id": args.run_id,
        "provenance": "synthetic",
        "profiler": "profile_inputs_bauspar.py (python stdlib csv/re only; no R, "
                    "no source-language convenience reader)",
        "emitted_utc": datetime.datetime(2026, 9, 22, 0, 0, 0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": [profile_file(args.inputs)],
        "observations": [
            "The engine reads exactly 11 columns from a contract row. The list was "
            "established two independent ways -- the R detector's mechanical column "
            "usage, and a direct scan of contract[[...]] / contract$ accesses -- "
            "which agree exactly. Recorded as values, not a count (R3).",
            "Date columns appear in two forms on purpose: ISO text coerced to R "
            "Date class by the harness, and raw YYYYMMDD left as text. The source's "
            "parse_date_field has a branch for each, and a stand-in that emitted "
            "only one form would leave the other untested.",
            "Amount columns appear both as plain decimals and in German "
            "decimal-comma form, including a thousands dot, because the source's "
            "parse_de_number strips dots before switching comma to point.",
            "The empty-marker vocabulary the source treats as 'this event has not "
            "happened' -- '', '0', '00000000', 'NA' -- is present in the date "
            "columns rather than described.",
            "HAZARD for any implementation that hand-rolls a delimiter split: "
            "German decimal-comma amounts are CSV-quoted and contain commas, so a "
            "naive split on ',' sees 14 or 15 fields on those lines instead of 11 "
            "and mis-assigns every column after the first amount. Under proper CSV "
            "quoting the file is exactly rectangular at 11 fields. This profiler's "
            "own first version made that mistake and reported the file as ragged.",
        ],
        "unverified_assumptions": [
            {
                "id": "UA-01",
                "statement": "The real merged_data_with_tariff_amount carries these "
                             "11 columns under these names.",
                "precondition": "The real table is absent from the bundle (F1). The "
                                "names come from the source's own accesses, so they "
                                "are what the engine DEMANDS -- not evidence that "
                                "the real table supplies them.",
            },
            {
                "id": "UA-02",
                "statement": "Real inputs mix Date-class and raw YYYYMMDD columns as "
                             "the engine's header comment describes.",
                "precondition": "Asserted by the source's comments only. Comments are "
                                "not evidence (R1); no real file was available to "
                                "check which columns arrive in which form.",
            },
            {
                "id": "UA-03",
                "statement": "Real tariff_amount values are fractions in (0,1] and "
                             "absent values mean the tariff code found no match.",
                "precondition": "Inferred from the engine's use of the field and its "
                                "goal_source='fallback_no_tariff' branch. Distribution "
                                "and absence rate in real data are unknown.",
            },
            {
                "id": "UA-04",
                "statement": "Contract identifiers (BSV) are unique per row.",
                "precondition": "Enforced by this generator so the checkpoint's "
                                "canonical order is total. The real table may repeat "
                                "a BSV -- qa_sample_customers_v4.R takes match(bsv, "
                                "bsv_chr), the FIRST row for a BSV, which implies "
                                "duplicates are expected there.",
            },
        ],
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2)
        fh.write("\n")
    print("wrote %s" % args.out)
    f = profile["files"][0]
    print("  %s: %d rows, %d columns, %d bytes" % (f["name"], f["row_count"], len(f["fields"]), f["bytes"]))
    print("  field-count distribution: %s" % f["field_count_distribution"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
