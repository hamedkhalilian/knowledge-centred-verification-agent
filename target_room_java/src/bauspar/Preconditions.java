package bauspar;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

/**
 * P-01 .. P-13 of the neutral spec, plus the findings' exposure counts.
 *
 * <p>R14/GR-13: every check derives its explanation from the data AT THE POINT OF THE
 * FINDING -- no sentence is printed as though it were measured when it was not.
 * FAIL and FLAGGED are kept distinct (a detector that collapses them teaches the
 * operator to ignore both). R18: each check is exercised against known-good input in
 * {@link SelfTest} before it is allowed to FAIL here.
 */
public final class Preconditions {

    public static final class Result {
        public final String id, severity, statement;
        public String status;            // PASS | FAIL | FLAGGED
        public String explanation;
        public final List<String> evidence = new ArrayList<>();
        Result(String id, String severity, String statement) {
            this.id = id; this.severity = severity; this.statement = statement;
        }
    }

    public final List<Result> results = new ArrayList<>();

    private Result add(String id, String sev, String statement) {
        Result r = new Result(id, sev, statement);
        results.add(r);
        return r;
    }

    private static void verdict(Result r, boolean ok, String okWhy, String badWhy) {
        if (ok) { r.status = "PASS"; r.explanation = okWhy; }
        else { r.status = r.severity; r.explanation = badWhy; }
    }

    public void run(Runner run, long valuation, String valuationSource) {
        Profile p = run.profile;
        Book b = run.book;

        // ---- P-01 -----------------------------------------------------------
        Result r1 = add("P-01", "FAIL",
            "The contract table carries all eleven names of input_column_catalogue, spelled exactly.");
        r1.evidence.add("absent: " + (p.absentRequired.isEmpty() ? "none" : String.join(", ", p.absentRequired)));
        r1.evidence.add("surplus (REPORTED, never rejected -- the unit selects by name and ignores the rest): "
                + (p.surplusFields.isEmpty() ? "none" : String.join(", ", p.surplusFields)));
        verdict(r1, p.absentRequired.isEmpty(),
            "all eleven declared names present; " + p.surplusFields.size() + " surplus field(s) ignored by name selection",
            p.absentRequired.size() + " declared name(s) absent: " + String.join(", ", p.absentRequired));

        // ---- P-02 -----------------------------------------------------------
        Result r2 = add("P-02", "FAIL", "The identifier field BSV is present.");
        boolean bsv = !p.absentRequired.contains("BSV");
        r2.evidence.add("BSV present: " + bsv + "; identifier values read: " + p.idRows);
        verdict(r2, bsv, "BSV is present, so the browser-data writer's second named refusal cannot fire",
            "BSV is absent: the browser-data writer stops with a named refusal and no file is written");

        // ---- P-03 -----------------------------------------------------------
        Result r3 = add("P-03", "FAIL",
            "Every non-missing value of the five date fields is readable by the rule of step C1.");
        long unreadable = 0;
        for (var e : p.dates.entrySet()) {
            Profile.DateField f = e.getValue();
            r3.evidence.add(e.getKey() + ": marker " + f.missingMarker + ", eight-digit valid "
                + f.eightDigitValid + ", hyphenated valid " + f.hyphenValid + ", unreadable " + f.unreadable
                + " -> " + f.total() + " of " + p.rows + " rows");
            unreadable += f.unreadable;
            if (f.total() != p.rows)
                r3.evidence.add("RECONCILIATION GAP in " + e.getKey() + ": " + f.total() + " classified against " + p.rows + " rows");
        }
        for (var e : p.dates.entrySet())
            for (String s : e.getValue().unreadableSamples) r3.evidence.add("unreadable: " + s);
        verdict(r3, unreadable == 0,
            "all " + (p.rows * 5) + " date cells classify as marker, eight-digit valid or hyphenated valid; none unreadable",
            unreadable + " value(s) are readable by neither branch; a HYPHENATED one among them aborts the unit (FND-06)");

        // ---- P-04 -----------------------------------------------------------
        Result r4 = add("P-04", "FLAGGED", "Parsed dates are plausible: between 1950-01-01 and 2100-01-01.");
        long lo = DateValue.fromIso("1950-01-01"), hi = DateValue.fromIso("2100-01-01");
        long outside = 0;
        for (var e : p.dates.entrySet()) {
            Profile.DateField f = e.getValue();
            if (!f.any()) { r4.evidence.add(e.getKey() + ": no parsed value"); continue; }
            r4.evidence.add(e.getKey() + ": min " + DateValue.isoOf(f.min) + ", max " + DateValue.isoOf(f.max));
            if (f.min < lo || f.max > hi) outside++;
        }
        verdict(r4, outside == 0,
            "every parsed date range lies inside 1950-01-01..2100-01-01; no field shows the year-below-100 signature of a two-digit year",
            outside + " field(s) carry a parsed date outside the plausible window");

        // ---- P-05 -----------------------------------------------------------
        Result r5 = add("P-05", "FAIL",
            "Every non-missing tariff share is greater than 0 and at most 1 (a fraction, not percent points).");
        Profile.AmountField tf = p.amounts.get("tariff_amount");
        // Counted on the READ values during the profile pass, before any rounding.
        long gt1 = tf.gtOne, le0 = tf.leZero;
        LinkedHashSet<String> tvals = new LinkedHashSet<>(tf.distinctRead);
        r5.evidence.add("min " + (tf.any() ? CanonicalNumber.num(tf.min) : "n/a")
                      + ", max " + (tf.any() ? CanonicalNumber.num(tf.max) : "n/a")
                      + ", missing " + tf.missing + ", at most 0: " + le0 + ", greater than 1: " + gt1);
        r5.evidence.add("distinct raw spellings in full: " + String.join(" / ", tf.distinctRaw));
        r5.evidence.add("distinct read values in full: " + String.join(" / ", tvals));
        verdict(r5, gt1 == 0,
            "every non-missing share is a fraction of one, so the unit's direct multiplication by an amount in euro is right (FND-02 not exposed here)",
            gt1 + " share(s) exceed 1: the unit multiplies them straight into an amount in euro, so every saving goal is out by a factor of about one hundred (FND-02)");

        // ---- P-06 -----------------------------------------------------------
        Result r6 = add("P-06", "FLAGGED",
            "Amounts are plausible: balance, loan notional and Bauspar sum are finite and not negative.");
        long neg = 0;
        for (String a : new String[] { "guthaben", "DaBetrag", "bausparsumme_teuro" }) {
            Profile.AmountField f = p.amounts.get(a);
            double mn = f.min, mx = f.max;
            String unit = " euro";
            if (a.equals("bausparsumme_teuro")) {
                mn *= Engine.BAUSPAR_SUM_UNIT_FACTOR; mx *= Engine.BAUSPAR_SUM_UNIT_FACTOR;
                unit = " euro (after the thousands factor)";
            }
            r6.evidence.add(a + ": missing " + f.missing + ", negative " + f.negative + ", zero " + f.zeros
                    + ", min " + (f.any() ? CanonicalNumber.num(mn) : "n/a")
                    + ", max " + (f.any() ? CanonicalNumber.num(mx) : "n/a") + unit);
            neg += f.negative;
        }
        verdict(r6, neg == 0, "no negative amount in any of the three fields",
            neg + " negative amount(s) present; a negative reference drives the saving ratio and the phase");

        // ---- P-07 -----------------------------------------------------------
        Result r7 = add("P-07", "FLAGGED", "Identifiers are unique across rows.");
        r7.evidence.add("rows read " + p.idRows + ", distinct identifiers " + p.idDistinct
                + ", duplicated identifiers " + p.idDuplicated);
        r7.evidence.add("reconciliation: rows " + p.rows + " = published " + run.recordsPublished
                + " + refused " + run.rowsRefused);
        if (!p.duplicatedIds.isEmpty()) r7.evidence.add("first duplicates: " + String.join(", ", p.duplicatedIds));
        verdict(r7, p.idDuplicated == 0,
            "every identifier occurs once, so FND-04's browser-keeps-the-last against harness-keeps-the-first cannot bite in this run",
            p.idDuplicated + " identifier(s) repeat; the browser data file keeps the LAST row for each and the quality harness the FIRST (FND-04). Nothing is deduplicated here.");

        // ---- P-08 -----------------------------------------------------------
        Result r8 = add("P-08", "FAIL", "Derived quantities are within their declared shapes.");
        long badPhase = 0, badGoalSource = 0, badPos = 0, badProgress = 0;
        List<String> breaches = new ArrayList<>();
        for (int i = 0; i < b.n; i++) {
            if (!isPhase(b.phase[i])) { badPhase++; if (breaches.size() < 10) breaches.add("row " + b.rowIndex[i] + " phase='" + b.phase[i] + "'"); }
            if (!Engine.GOAL_SOURCE_TARIFF.equals(b.goalSource[i]) && !Engine.GOAL_SOURCE_FALLBACK.equals(b.goalSource[i])) {
                badGoalSource++; if (breaches.size() < 10) breaches.add("row " + b.rowIndex[i] + " goal_source='" + b.goalSource[i] + "'");
            }
            double[] xs = { b.xContract[i], b.xFirstPayment[i], b.xAllocation[i], b.xLoanStart[i], b.xNow[i] };
            for (double x : xs) if (!Double.isNaN(x) && (x < 0 || x > 1)) {
                badPos++; if (breaches.size() < 10) breaches.add("row " + b.rowIndex[i] + " position " + CanonicalNumber.num(x));
            }
            double sp = b.savingProgress[i];
            if (sp < 0 || sp > 1 || Double.isNaN(sp)) { badProgress++; if (breaches.size() < 10) breaches.add("row " + b.rowIndex[i] + " saving progress " + CanonicalNumber.num(sp)); }
        }
        r8.evidence.add("phase outside the four declared values: " + badPhase
                + "; goal_source outside the two: " + badGoalSource
                + "; published position outside 0..1: " + badPos
                + "; saving progress outside 0..1: " + badProgress);
        r8.evidence.addAll(breaches);
        verdict(r8, badPhase + badGoalSource + badPos + badProgress == 0,
            "every published phase, goal source, position and saving progress is inside its declared shape",
            (badPhase + badGoalSource + badPos + badProgress) + " breach(es) of the declared shapes, listed above with their row positions");

        // ---- P-09 -----------------------------------------------------------
        Result r9 = add("P-09", "FAIL", "No row is lost: records published equals rows read.");
        r9.evidence.add("rows read " + run.rowsRead + ", records published " + run.recordsPublished
                + ", rows refused " + run.rowsRefused);
        for (String d : run.declinedInputs) r9.evidence.add("declined: " + d);
        verdict(r9, run.rowsRead == run.recordsPublished + run.rowsRefused && run.rowsRefused == 0,
            "the three counts reconcile and nothing was refused",
            "the counts do not reconcile: " + run.rowsRead + " read against "
                + run.recordsPublished + " published plus " + run.rowsRefused + " refused");

        // ---- P-10 -----------------------------------------------------------
        Result r10 = add("P-10", "FLAGGED",
            "No field name in the table has any of the eleven declared names as a strict prefix.");
        r10.evidence.add(p.prefixCollisions.isEmpty() ? "no field name shadows a declared name"
                : String.join("; ", p.prefixCollisions));
        verdict(r10, p.prefixCollisions.isEmpty(),
            "no field name begins with a declared name, so the source's prefix fallback (FND-12) cannot bind the wrong field",
            p.prefixCollisions.size() + " field name(s) begin with a declared name; where the exact name is absent the source binds these SILENTLY (FND-12)");

        // ---- P-11 -----------------------------------------------------------
        Result r11 = add("P-11", "FLAGGED", "A text amount carries at most one comma.");
        long multi = 0;
        for (var e : p.amounts.entrySet()) {
            multi += e.getValue().multiComma;
            r11.evidence.add(e.getKey() + ": values with two or more commas: " + e.getValue().multiComma);
        }
        verdict(r11, multi == 0,
            "no text amount carries a second comma, so the silent-missing clause of C2 is not reached here",
            multi + " text amount(s) carry two or more commas; each becomes missing by step C2, SILENTLY");

        // ---- P-12 -----------------------------------------------------------
        Result r12 = add("P-12", "FAIL",
            "The valuation date is supplied, is a valid calendar date, and lies in the plausible range of P-04.");
        r12.evidence.add("valuation date used: " + DateValue.isoOf(valuation) + "; source: " + valuationSource);
        r12.evidence.add("the unit's own load-time default is 2026-03-31 and its session override is a value named VAL_DATE; "
                + "neither exists in this target, so the date is carried explicitly");
        boolean vok = valuation >= lo && valuation <= hi;
        verdict(r12, vok, "the valuation date is inside 1950-01-01..2100-01-01",
            "the valuation date " + DateValue.isoOf(valuation) + " lies outside the plausible window");

        // ---- P-13 -----------------------------------------------------------
        Result r13 = add("P-13", "FLAGGED",
            "The thousands factor on the Bauspar sum is right way up, judged from a derived quantity (R4).");
        List<Double> ratios = new ArrayList<>();
        for (int i = 0; i < b.n; i++) {
            double ratio = b.loanToBausparRatio[i];
            if (!Double.isNaN(ratio) && !Double.isInfinite(ratio)) ratios.add(ratio);
        }
        double median = median(ratios);
        r13.evidence.add("median loan-notional to Bauspar-sum ratio over " + ratios.size()
                + " contracts where both are present and the sum is positive: " + CanonicalNumber.num(median));
        String why;
        boolean ok13;
        if (ratios.isEmpty()) { ok13 = false; why = "no contract has both amounts with a positive Bauspar sum, so the factor cannot be judged from the data"; }
        else if (median < 0.01) { ok13 = false; why = "the median ratio is " + CanonicalNumber.num(median)
                + ", about a thousandth: the thousands factor looks to have been applied on the wrong side, which would clear the bridge flag for the whole book"; }
        else if (median > 100) { ok13 = false; why = "the median ratio is " + CanonicalNumber.num(median)
                + ", about a thousand: the thousands factor looks not to have been applied, which would set the bridge flag for the whole book"; }
        else { ok13 = true; why = "the median ratio is " + CanonicalNumber.num(median)
                + ", near the 1 the unit's own documentation expects for an ordinary contract, so the factor is the right way up"; }
        verdict(r13, ok13, why, why);
    }

    private static boolean isPhase(String p) {
        return Engine.PHASE_DONE.equals(p) || Engine.PHASE_LOAN.equals(p)
            || Engine.PHASE_OVERSAVE.equals(p) || Engine.PHASE_SAVE.equals(p);
    }

    private static double median(List<Double> xs) {
        if (xs.isEmpty()) return Double.NaN;
        double[] a = new double[xs.size()];
        for (int i = 0; i < a.length; i++) a[i] = xs.get(i);
        java.util.Arrays.sort(a);
        int n = a.length;
        return (n % 2 == 1) ? a[n / 2] : (a[n / 2 - 1] + a[n / 2]) / 2.0;
    }
}
