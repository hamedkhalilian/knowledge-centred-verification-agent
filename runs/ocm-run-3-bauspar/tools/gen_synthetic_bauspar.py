#!/usr/bin/env python3
"""Run 3 synthetic input generator -- merged_data_with_tariff_amount stand-in.

PROVENANCE: everything this produces is `observed_in_synthetic_input`, never
`observed_in_real_input` (lessons, finding 3). Facts seen only here cap the
verdict under R2 and must never harden into a contract the target enforces.

WHY A STAND-IN AT ALL: the real input table is not in the delivered bundle, and
neither is the enrichment script that builds it (DISCOVER finding F1). The
engine therefore cannot be executed on real data as delivered. This generator
exists so that OBSERVE_SOURCE and OBSERVE_TARGET can run the same inputs at
all; it is not a convenience.

Deterministic: fixed seed, no clock, no environment. Re-running reproduces the
file byte for byte.

The 11 columns are the ones the engine mechanically reads from a contract row,
cross-checked two independent ways (the R detector's column usage, and a direct
scan of `contract[[...]]` / `contract$` accesses). They agree exactly:

    BSV, DaBetrag, Tilgungsbeginn, Vertragsende, abschlussdatum,
    bausparsumme_teuro, contract_type, einloesungsdatum,
    erstmalige_zuteilungsanwartschaft, guthaben, tariff_amount

IN-FORMAT, NOT MERELY PLAUSIBLE: the engine's own comments document two type
quirks -- date columns arriving either as R Date objects or as raw YYYYMMDD,
and amount columns carrying a German decimal comma. A stand-in that emits only
the tidy form would leave both parsers untested, which is how run 2's finding 5
happened: an expectation that was only ever exercised where two readings
coincide. Both forms appear here, and the empty-marker vocabulary the source
treats as "this event has not happened" ("", "0", "00000000", "NA") appears
too.

Emits:
  merged_data_synthetic.csv   all values as text, in-format
  synthetic_manifest.json     seed, row count, per-column coercions the R
                              harness must apply, and branch coverage counts
"""
import argparse
import csv
import datetime
import json
import os
import random

SEED = 20260922
VALUATION_DATE = datetime.date(2026, 3, 31)

COLUMNS = [
    "BSV", "abschlussdatum", "einloesungsdatum",
    "erstmalige_zuteilungsanwartschaft", "Tilgungsbeginn", "Vertragsende",
    "DaBetrag", "bausparsumme_teuro", "guthaben", "tariff_amount",
    "contract_type",
]

# Columns the R harness coerces to class Date after reading, to exercise the
# "already a Date" branch of parse_date_field. The rest stay raw YYYYMMDD text
# so the other branch is exercised too. Declared here, applied by the harness,
# recorded in the manifest -- never inferred on either side.
DATE_CLASS_COLUMNS = ["abschlussdatum", "einloesungsdatum"]
RAW_YYYYMMDD_COLUMNS = ["erstmalige_zuteilungsanwartschaft", "Tilgungsbeginn", "Vertragsende"]

EMPTY_MARKERS = ["", "0", "00000000", "NA"]
CONTRACT_TYPES = ["BS1", "BS2", "BSK", "VL7", ""]


def iso(d):
    return d.isoformat() if d else ""


def ymd(d):
    return d.strftime("%Y%m%d") if d else ""


def de_number(value, decimals=2):
    """German decimal comma, with a thousands dot above 9999."""
    text = "%.*f" % (decimals, value)
    whole, _, frac = text.partition(".")
    if len(whole) > 4:
        groups = []
        while len(whole) > 3:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        groups.insert(0, whole)
        whole = ".".join(groups)
    return "%s,%s" % (whole, frac) if frac else whole


def plain_number(value, decimals=2):
    return ("%.*f" % (decimals, value)).rstrip("0").rstrip(".")


class Builder:
    """Assembles rows and records which branch each one is designed to reach."""

    def __init__(self):
        self.rows = []
        self.coverage = {}

    def add(self, bsv, contract_start, first_payment, allocation, loan_start,
            contract_end, da_betrag, bauspar_teuro, guthaben, tariff,
            contract_type, branches, german=False):
        num = de_number if german else plain_number
        self.rows.append({
            "BSV": str(bsv),
            "abschlussdatum": contract_start if isinstance(contract_start, str) else iso(contract_start),
            "einloesungsdatum": first_payment if isinstance(first_payment, str) else iso(first_payment),
            "erstmalige_zuteilungsanwartschaft": allocation if isinstance(allocation, str) else ymd(allocation),
            "Tilgungsbeginn": loan_start if isinstance(loan_start, str) else ymd(loan_start),
            "Vertragsende": contract_end if isinstance(contract_end, str) else ymd(contract_end),
            "DaBetrag": da_betrag if isinstance(da_betrag, str) else num(da_betrag),
            "bausparsumme_teuro": bauspar_teuro if isinstance(bauspar_teuro, str) else num(bauspar_teuro, 3),
            "guthaben": guthaben if isinstance(guthaben, str) else num(guthaben),
            "tariff_amount": tariff if isinstance(tariff, str) else num(tariff, 4),
            "contract_type": contract_type,
        })
        for branch in branches:
            self.coverage[branch] = self.coverage.get(branch, 0) + 1


def d(year, month, day):
    return datetime.date(year, month, day)


def build_edge_cases(b):
    """Hand-designed rows, one per branch the engine can take.

    Randomness alone does not guarantee a branch is reached, and an unreached
    branch is an untested branch that still gets migrated.
    """
    V = VALUATION_DATE

    # phase = done: contract end already passed.
    b.add(900001, d(2001, 3, 1), d(2001, 4, 1), d(2011, 4, 1), d(2011, 6, 1),
          d(2022, 6, 1), 30000, 30.0, 12000, 0.40, "BS1", ["phase_done"])

    # phase = loan: repayment started, contract still running.
    b.add(900002, d(2007, 5, 1), d(2007, 6, 1), d(2020, 1, 1), d(2020, 3, 1),
          d(2031, 3, 1), 20000, 20.0, 11230, 0.40, "BS1", ["phase_loan"])

    # phase = save: still saving, allocation ahead, below goal.
    b.add(900003, d(2019, 1, 1), d(2019, 2, 1), d(2029, 2, 1), "",
          "", 40000, 40.0, 4000, 0.40, "BS2", ["phase_save", "no_loan_start"])

    # phase = oversave: balance at or above the goal fraction.
    b.add(900004, d(2014, 1, 1), d(2014, 2, 1), d(2028, 2, 1), "",
          "", 25000, 25.0, 23000, 0.40, "BS2",
          ["phase_oversave", "warn_loan_pointless"])

    # Fortsetzer: allocated, no repayment, still saving -- x_now sits right of
    # the vertex. The engine's comment calls this legitimate, never an alarm.
    b.add(900005, d(2008, 1, 1), d(2008, 2, 1), d(2018, 2, 1), "",
          "", 30000, 30.0, 9000, 0.40, "BS1",
          ["saving_after_allocation", "phase_save"])

    # Bridge loan: DaBetrag far above Bausparsumme, so the saving reference
    # switches to the Bausparsumme.
    b.add(900006, d(2007, 1, 1), d(2007, 2, 1), d(2020, 1, 1), d(2020, 2, 1),
          d(2032, 2, 1), 101853, 20.0, 11230, 0.40, "BS1",
          ["is_bridge_loan", "phase_loan"])

    # Allocation missing -> estimated from first payment + 10y, label "~YYYY".
    b.add(900007, d(2015, 6, 1), d(2015, 7, 1), "00000000", "",
          "", 18000, 18.0, 3000, 0.40, "BSK", ["allocation_estimated"])

    # tariff_amount absent -> goal_source falls back, never silently.
    b.add(900008, d(2016, 2, 1), d(2016, 3, 1), d(2027, 3, 1), "",
          "", 22000, 22.0, 5000, "NA", "VL7", ["goal_source_fallback"])

    # tariff_amount present and non-flat -> goal_source = tariff.
    b.add(900009, d(2017, 2, 1), d(2017, 3, 1), d(2028, 3, 1), "",
          "", 24000, 24.0, 6000, 0.30, "BS2", ["goal_source_tariff"])

    # Contract start missing -> falls back to first payment.
    b.add(900010, "", d(2013, 8, 1), d(2024, 8, 1), "",
          "", 26000, 26.0, 7000, 0.40, "BS1", ["start_from_first_payment"])

    # Both start dates missing -> falls back to valuation - 7 years.
    b.add(900011, "", "", d(2025, 1, 1), "",
          "", 28000, 28.0, 8000, 0.40, "BS1",
          ["start_from_valuation_fallback", "allocation_in_past"])

    # Bausparsumme zero -> ratio undefined, savings_ratio guarded.
    # Bausparsumme zero but DaBetrag present: the ratio is undefined, so the
    # contract is NOT flagged as a bridge and DaBetrag remains the reference.
    # savings_ratio stays finite here -- see 900022/900023 for the NA paths.
    b.add(900012, d(2018, 1, 1), d(2018, 2, 1), d(2029, 2, 1), "",
          "", 15000, 0.0, 2000, 0.40, "BSK",
          ["bauspar_sum_zero", "ratio_undefined_not_bridge"])

    # German decimal comma throughout, including a thousands dot.
    b.add(900013, d(2010, 9, 1), d(2010, 10, 1), d(2021, 10, 1), "",
          "", 36263.14, 36.263, 15369.66, 0.40, "BS1",
          ["german_decimal_comma", "allocation_in_past",
           "saving_after_allocation"], german=True)

    # Every empty marker the source recognises, one per date column.
    b.add(900014, "NA", "0", "00000000", "", "", 21000, 21.0, 4200, 0.40, "BS2",
          ["all_empty_markers", "allocation_estimated"])

    # "special": Bausparsumme above twice DaBetrag -- the v4 red alarm.
    b.add(900015, d(2012, 4, 1), d(2012, 5, 1), d(2023, 5, 1), "",
          "", 10000, 45.0, 9500, 0.40, "BS1", ["special_alarm"])

    # Empty contract_type -> passed through as-is, not defaulted.
    b.add(900016, d(2016, 7, 1), d(2016, 8, 1), d(2027, 8, 1), "",
          "", 19000, 19.0, 3800, 0.40, "", ["empty_contract_type"])

    # Repayment starts exactly on the valuation date: `>=` boundary.
    b.add(900017, d(2009, 1, 1), d(2009, 2, 1), d(2019, 2, 1), VALUATION_DATE,
          d(2035, 1, 1), 32000, 32.0, 12800, 0.40, "BS1",
          ["boundary_repayment_today", "phase_loan"])

    # Contract ends exactly on the valuation date: `>=` boundary, done wins.
    b.add(900018, d(2004, 1, 1), d(2004, 2, 1), d(2014, 2, 1), d(2014, 4, 1),
          VALUATION_DATE, 27000, 27.0, 10800, 0.40, "BS1",
          ["boundary_end_today", "phase_done"])

    # Allocation exactly on the valuation date: `>` boundary, NOT in the past.
    b.add(900019, d(2016, 3, 31), d(2016, 4, 30), VALUATION_DATE, "",
          "", 23000, 23.0, 4600, 0.40, "BS2", ["boundary_allocation_today"])

    # savings_ratio exactly at the warn threshold (0.90) and at goal.
    b.add(900020, d(2015, 1, 1), d(2015, 2, 1), d(2026, 12, 1), "",
          "", 10000, 10.0, 9000, 0.40, "BS1",
          ["boundary_warn_exact", "phase_oversave"])

    # loan_to_bauspar_ratio exactly at the bridge cutoff (2): `>` means NOT a
    # bridge. The strict comparison is the whole point of the row.
    b.add(900021, d(2011, 1, 1), d(2011, 2, 1), d(2022, 2, 1), "",
          "", 40000, 20.0, 8000, 0.40, "BS1", ["boundary_bridge_exact"])

    # Saving reference undefined: DaBetrag missing AND Bausparsumme zero, so
    # savings_ratio takes its NA guard and bauspar_loan is not a number.
    #
    # Row 900012 below was MEANT to reach this and did not: zeroing the
    # Bausparsumme alone leaves DaBetrag as the reference, so the ratio stayed
    # finite. The gap was invisible until the branch tally was actually run
    # against the engine's output. A designed branch is not a reached branch --
    # the same distinction lessons finding 11 makes about guards.
    b.add(900022, d(2013, 1, 1), d(2013, 2, 1), d(2024, 2, 1), "",
          "", "", 0.0, 1500, 0.40, "BS1", ["saving_reference_missing"])

    # Saving reference exactly zero rather than missing: the `> 0` guard, not
    # the is.finite one. Two different ways to be unusable, two rows.
    b.add(900023, d(2013, 6, 1), d(2013, 7, 1), d(2024, 7, 1), "",
          "", 0, 0.0, 1200, 0.40, "BS2", ["saving_reference_zero"])


def build_bulk(b, count, rng):
    """Seeded bulk rows, in the same formats, to exercise volume and mixing."""
    for i in range(count):
        start_year = rng.randint(1998, 2022)
        start = d(start_year, rng.randint(1, 12), rng.randint(1, 28))
        first = start + datetime.timedelta(days=rng.randint(20, 400))
        allocated = rng.random() < 0.80
        allocation = first + datetime.timedelta(days=rng.randint(2500, 5200)) if allocated else ""
        repaying = allocated and rng.random() < 0.45
        loan_start = allocation + datetime.timedelta(days=rng.randint(0, 900)) if repaying else ""
        ended = repaying and rng.random() < 0.20
        contract_end = (loan_start + datetime.timedelta(days=rng.randint(1200, 5000))
                        if ended else "")
        bauspar_teuro = round(rng.choice([10, 15, 20, 24, 25, 30, 36, 40, 45, 50])
                              + rng.random(), 3)
        bridge = rng.random() < 0.15
        da_betrag = (bauspar_teuro * 1000 * rng.uniform(2.2, 6.0) if bridge
                     else bauspar_teuro * 1000 * rng.uniform(0.85, 1.05))
        guthaben = da_betrag * rng.uniform(0.02, 0.95)
        tariff = rng.choice([0.40, 0.40, 0.30, 0.35, 0.50, "NA"])
        branches = ["bulk"]
        if bridge:
            branches.append("is_bridge_loan")
        if tariff == "NA":
            branches.append("goal_source_fallback")
        b.add(800000 + i, start, first, allocation, loan_start, contract_end,
              round(da_betrag, 2), bauspar_teuro, round(guthaben, 2), tariff,
              rng.choice(CONTRACT_TYPES), branches,
              german=(rng.random() < 0.25))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--bulk", type=int, default=480,
                        help="seeded bulk rows added after the edge cases")
    args = parser.parse_args()

    rng = random.Random(SEED)
    builder = Builder()
    build_edge_cases(builder)
    edge_count = len(builder.rows)
    build_bulk(builder, args.bulk, rng)

    os.makedirs(args.out_dir, exist_ok=True)
    csv_path = os.path.join(args.out_dir, "merged_data_synthetic.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(builder.rows)

    manifest = {
        "provenance": "synthetic",
        "generator": "gen_synthetic_bauspar.py",
        "seed": SEED,
        "valuation_date": VALUATION_DATE.isoformat(),
        "row_count": len(builder.rows),
        "edge_case_rows": edge_count,
        "bulk_rows": len(builder.rows) - edge_count,
        "columns": COLUMNS,
        "harness_coercions": {
            "to_date_class": DATE_CLASS_COLUMNS,
            "left_as_raw_yyyymmdd": RAW_YYYYMMDD_COLUMNS,
            "note": "Both branches of parse_date_field must be exercised. The "
                    "harness applies these coercions identically on both sides; "
                    "neither side infers them.",
        },
        "empty_markers_used": EMPTY_MARKERS,
        "branch_coverage": dict(sorted(builder.coverage.items())),
        "caveat": "R2: every fact observed here is observed_in_synthetic_input. "
                  "It caps the verdict and must not harden into a target-enforced "
                  "contract (lessons, finding 3).",
    }
    manifest_path = os.path.join(args.out_dir, "synthetic_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=False)
        fh.write("\n")

    print("wrote %s (%d rows: %d edge cases + %d bulk)"
          % (csv_path, len(builder.rows), edge_count, len(builder.rows) - edge_count))
    print("wrote %s (%d branches covered)" % (manifest_path, len(builder.coverage)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
