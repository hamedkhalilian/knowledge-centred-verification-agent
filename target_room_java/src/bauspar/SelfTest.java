package bauspar;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * GR-13 self-tests, run BEFORE anything is emitted and at the DECLARED language level
 * (R13 -- build.sh reads the level from project.properties and this class is compiled
 * and run under it).
 *
 * <p>Three kinds of check, deliberately not one kind three times (R8):
 * <ol>
 *   <li>CONTRACT vectors -- the canonicalisation contract's reference vectors and the
 *       spec's sixteen measured rounding vectors. These are memorised constants and
 *       they are exactly what the contract and the spec require to be memorised; they
 *       are the weakest check and they are labelled as such.</li>
 *   <li>PROPERTY checks -- clamp bounds, phase/flag implications, mapping identity,
 *       document shape, digest determinism. These survive data changes.</li>
 *   <li>DETECTOR CALIBRATION (R18) -- every precondition is run against known-GOOD
 *       input and against known-BAD input, and the separation is reported, before any
 *       of them is allowed to FAIL on the real run.</li>
 * </ol>
 */
public final class SelfTest {

    public final List<String> failures = new ArrayList<>();
    public final List<String> lines = new ArrayList<>();
    public int checks, passed;
    public final List<String> blindSpots = new ArrayList<>();
    public final List<String> detectorSeparation = new ArrayList<>();

    private void check(String what, boolean ok, String detail) {
        checks++;
        if (ok) { passed++; }
        else failures.add(what + " -- " + detail);
    }

    private void eq(String what, String got, String want) {
        check(what, got.equals(want), "got '" + got + "', want '" + want + "'");
    }

    public boolean run(Path scratch) throws IOException {
        lines.add("LAYER 1  canonicalisation contract reference vectors (memorised by contract)");
        for (String[] v : CanonicalNumber.referenceVectors()) eq("canon " + v[0], v[1], v[2]);
        lines.add("  " + CanonicalNumber.referenceVectors().length + " vectors");

        lines.add("LAYER 2  rounding rule C20, the sixteen measured reference vectors");
        for (String[] v : Rounding.REFERENCE_VECTORS) {
            double in = Double.parseDouble(v[0]);
            int places = Integer.parseInt(v[1]);
            double want = Double.parseDouble(v[2]);
            double got = Rounding.round(in, places);
            boolean ok = (got == want) && (want != 0.0
                    || Double.doubleToRawLongBits(got) == Double.doubleToRawLongBits(signedZeroLike(in, want)));
            check("round(" + v[0] + "," + v[1] + ")", ok, "got " + got + ", want " + v[2]);
        }
        lines.add("  16 vectors");

        lines.add("LAYER 3  the three day constants, computed the way the unit computes them");
        check("10 x 365.25 -> 3652", Rounding.round(10 * 365.25, 0) == 3652.0,
              "got " + Rounding.round(10 * 365.25, 0) + " (the obvious 'ten years' gives 3653)");
        check("11 x 365.25 -> 4018", Rounding.round(11 * 365.25, 0) == 4018.0, "got " + Rounding.round(11 * 365.25, 0));
        check("7 x 365.25 -> 2557", Rounding.round(7 * 365.25, 0) == 2557.0, "got " + Rounding.round(7 * 365.25, 0));
        check("constants match the spec", Engine.ALLOCATION_FALLBACK_DAYS == 3652
                && Engine.CONTRACT_END_FALLBACK_DAYS == 4018 && Engine.FALLBACK_ORIGIN_DAYS == 2557,
                "declared constants differ from the computed ones");

        lines.add("LAYER 4  the SECOND rounding rule: the browser file's fixed-format conversion (C22)");
        eq("script 0.4", ScriptFormat.number(0.4), "0.4");
        eq("script 14500", ScriptFormat.number(14500.0), "14500");
        eq("script 1e-7", ScriptFormat.number(1e-7), "0");
        eq("script -0.0", ScriptFormat.number(-0.0), "-0");
        eq("script NaN", ScriptFormat.number(Double.NaN), "null");
        eq("script Inf", ScriptFormat.number(Double.POSITIVE_INFINITY), "null");
        // The two rules must NOT agree everywhere, or one of them is wrong.
        check("C20 and C22 are different rules",
              !ScriptFormat.number(0.0055).equals(ScriptFormat.number(Rounding.round(0.0055, 3))),
              "0.0055 renders the same under both rules; one of them is not implemented");

        lines.add("LAYER 5  date reader C1, the measured behaviours including FND-06");
        check("20110401.0 -> 2011-04-01", DateValue.readText("20110401.0").epochDay == DateValue.fromIso("2011-04-01"), "trailing text must be ignored");
        check("2013112 -> 2013-11-02", DateValue.readText("2013112").epochDay == DateValue.fromIso("2013-11-02"), "the digit branch is NOT width-checked");
        check("2011/04/01 -> missing", DateValue.readText("2011/04/01").epochDay == DateValue.NA, "no hyphen, so it takes the digit branch and becomes missing");
        check("20131345 -> silent missing", DateValue.readText("20131345").fail == DateValue.Fail.SILENT_MISSING, "no hyphen, so no abort");
        check("abcdefgh -> silent missing", DateValue.readText("abcdefgh").fail == DateValue.Fail.SILENT_MISSING, "no hyphen, so no abort");
        check("2013-13-45 -> ABORT", DateValue.readText("2013-13-45").fail == DateValue.Fail.ABORT, "hyphenated and unreadable must abort");
        check("not-a-date -> ABORT", DateValue.readText("not-a-date").fail == DateValue.Fail.ABORT, "hyphenated and unreadable must abort");
        check("11-04-01 -> year eleven", DateValue.readText("11-04-01").epochDay == DateValue.toEpochDay(11, 4, 1), "a two-digit year is a YEAR");
        for (String m : DateValue.MISSING_MARKERS)
            check("marker '" + m + "' -> missing", DateValue.readText(m).epochDay == DateValue.NA
                    && DateValue.readText(m).fail == DateValue.Fail.NONE, "all seven markers mean missing, silently");
        check("000000 -> missing by failed read, not by marker",
              DateValue.readText("000000").epochDay == DateValue.NA
              && DateValue.readText("000000").fail == DateValue.Fail.SILENT_MISSING,
              "a six-zero text is in neither list and must become missing through the failed read (FND-11)");

        lines.add("LAYER 6  number reader C2, the measured values including FND-01");
        check("36263,14", GermanNumber.readText("36263,14") == 36263.14, "decimal comma");
        check("36.263,14", GermanNumber.readText("36.263,14") == 36263.14, "thousands dot with decimal comma");
        check("1.234.567,89", GermanNumber.readText("1.234.567,89") == 1234567.89, "two thousands dots");
        check("36.263 -> 36.263 (FND-01)", GermanNumber.readText("36.263") == 36.263, "no comma, so the dot is a decimal point");
        check("1,2,3 -> missing", Double.isNaN(GermanNumber.readText("1,2,3")), "silently missing");
        for (String m : GermanNumber.MISSING_MARKERS)
            check("amount marker '" + m + "'", Double.isNaN(GermanNumber.readText(m)), "the five markers mean missing");

        lines.add("LAYER 7  property checks on a miniature book (inversion, not memorised numbers)");
        propertyChecks(scratch);

        lines.add("LAYER 8  detector calibration (R18): every precondition on known-GOOD and known-BAD input");
        detectorCalibration(scratch);

        blindSpots.add("Layers 1-4 are memorised constants: they cannot detect an error that the contract's own vectors and the spec's own vectors share. They are covered structurally by layer 4's disagreement check (the two rounding rules must differ) and by the exact-arithmetic construction, which never consults a table.");
        blindSpots.add("Layer 7's property checks share the engine's reading of the spec: they rule out coding slips, not a misreading of the specification. Only the independent source-side observation can close that, and this agent cannot see it.");
        blindSpots.add("The harness date coercion is modelled from controller directive 01's description of the source language's whole-column conversion. No coerced column in either staged file exercises a FORMAT other than year-month-day with hyphens, so the format-inference branch is covered only for that one format.");
        blindSpots.add("Three of the seven date missing-markers ('00', '0000', '<NA>') do not occur in the staged input, so their handling is exercised only by layer 5, never end to end.");
        blindSpots.add("No identifier in the staged input repeats and none arrives numeric, so FND-03 and FND-04 are unexercised end to end: their preconditions pass vacuously and are reported as such, not as evidence.");
        blindSpots.add("Every threshold here was seen only on synthetic data (R15). None of them may produce a FAIL on real input before it has seen real input; the run report says so in the verdict, and the verdict is capped at PROVISIONAL by R2 regardless.");

        return failures.isEmpty();
    }

    private static double signedZeroLike(double in, double want) {
        if (want != 0.0) return want;
        return (Double.doubleToRawLongBits(in) < 0) ? -0.0 : 0.0;
    }

    // ------------------------------------------------------------ property checks

    private void propertyChecks(Path scratch) throws IOException {
        Path good = writeCsv(scratch, "selftest_good.csv", GOOD_ROWS);
        Runner run = runOver(good, List.of("abschlussdatum", "einloesungsdatum"),
                             DateValue.fromIso("2026-03-31"));
        Book b = run.book;

        // P1. Every published position is inside the clamp's declared bounds.
        boolean posOk = true;
        for (int i = 0; i < b.n; i++)
            for (double x : new double[] { b.xContract[i], b.xFirstPayment[i], b.xAllocation[i], b.xLoanStart[i], b.xNow[i] })
                if (!Double.isNaN(x) && (x < 0 || x > 1)) posOk = false;
        check("property: positions inside 0..1", posOk, "a published position left the axis");

        // P2. The phase precedence is an implication chain, checked independently of C14.
        boolean phaseOk = true;
        for (int i = 0; i < b.n; i++) {
            String want = b.contractEnded[i] ? "done"
                        : b.repaymentActive[i] ? "loan"
                        : b.overGoal[i] ? "oversave" : "save";
            if (!want.equals(b.phase[i])) phaseOk = false;
        }
        check("property: phase follows its precedence", phaseOk, "a phase disagrees with the predicates that decide it");

        // P3. saving_after_allocation is exactly its definition.
        boolean safOk = true;
        for (int i = 0; i < b.n; i++)
            if (b.savingAfterAllocation[i] != (b.allocationInPast[i] && !b.repaymentActive[i] && !b.contractEnded[i])) safOk = false;
        check("property: saving_after_allocation", safOk, "C15 disagrees with its own definition");

        // P4. After C5 and C6 neither the allocation date nor the contract end can be missing.
        boolean datesOk = true;
        for (int i = 0; i < b.n; i++)
            if (b.allocationDate[i] == DateValue.NA || b.contractEndDate[i] == DateValue.NA) datesOk = false;
        check("property: allocation and contract end are never missing after C5/C6", datesOk, "a fallback did not fire");

        // P5. The export mapping is an identity on the published values, not a recomputation.
        Export x = run.export;
        boolean mapOk = true;
        for (int i = 0; i < b.n; i++) {
            if (!same(x.sr[i], b.savingsRatio[i])) mapOk = false;
            if (!same(x.guthaben[i], b.balance[i])) mapOk = false;
            if (!same(x.bausparsumme[i], b.bausparSum[i])) mapOk = false;
            if (!same(x.loanAmount[i], b.bausparLoan[i])) mapOk = false;
            if (!same(x.dabetrag[i], b.loanNotional[i])) mapOk = false;
            if (!same(x.daBsumRatio[i], b.loanToBausparRatio[i])) mapOk = false;
            if (!same(x.goalFrac[i], b.goalFraction[i])) mapOk = false;
            if (x.warn[i] != (b.warnLoanPointless[i] ? 1 : 0)) mapOk = false;
            if (x.bridge[i] != (b.isBridgeLoan[i] ? 1 : 0)) mapOk = false;
            if (x.allocEst[i] != (b.allocationEstimated[i] ? 1 : 0)) mapOk = false;
        }
        check("property: export maps the published values through unchanged", mapOk, "C21 recomputed something it should have carried");

        // P6. The browser document's shape.
        List<String> doc = run.buildJsDocument(DateValue.fromIso("2026-03-31"));
        check("property: document has n+4 lines", doc.size() == b.n + 4, "got " + doc.size() + " for " + b.n + " rows");
        check("property: line 2 carries the row count", doc.get(1).equals("// " + b.n + " contracts, valuation date 2026-03-31"), doc.get(1));
        boolean commaOk = true;
        for (int i = 3; i < 3 + b.n; i++) {
            boolean last = (i == 3 + b.n - 1);
            if (last == doc.get(i).endsWith(",")) commaOk = false;
        }
        check("property: every entry but the last ends with a comma", commaOk, "the join is wrong");
        check("property: document closes", doc.get(doc.size() - 1).equals("};"), doc.get(doc.size() - 1));

        // P7. Digest determinism: the same object digested twice is the same digest.
        CheckpointObject o1 = Objects.customerBook(b);
        CheckpointObject o2 = Objects.customerBook(b);
        check("property: digest is deterministic", o1.objectDigest().equals(o2.objectDigest()), "two digests of one object differ");

        // P8. The canonical order is TOTAL: no two rows compare equal on the declared keys.
        int[] order = o1.order();
        boolean totalOk = true;
        for (int i = 1; i < order.length; i++) {
            if (b.id[order[i - 1]].equals(b.id[order[i]]) && b.rowIndex[order[i - 1]] == b.rowIndex[order[i]]) totalOk = false;
            if (b.rowIndex[order[i - 1]] > b.rowIndex[order[i]] && b.id[order[i - 1]].equals(b.id[order[i]])) totalOk = false;
        }
        check("property: the canonical order is total and ascending on the second key", totalOk, "the declared order does not separate every pair of rows");

        // P9. FND-13's mechanism, checked as a mechanism rather than on a memorised row:
        //     the flag is decided before rounding, so a published 0.900 with the flag unset is possible.
        double ratio = 0.8996;
        boolean flagFromUnrounded = ratio >= Engine.WARN_BALANCE_FRACTION;
        double published = Rounding.round(ratio, Engine.RP_SAVINGS_RATIO);
        check("property: FND-13's disagreement is reachable", !flagFromUnrounded && published == 0.9,
              "0.8996 must publish as 0.900 with the flag NOT set");

        // P10. FND-05's mechanism: the alarm is decided on the ROUNDED ratio.
        check("property: FND-05 0.4996 raises no alarm", !(Rounding.round(0.4996, 3) < 0.5), "0.4996 publishes as 0.500");
        check("property: FND-05 0.4994 raises one", Rounding.round(0.4994, 3) < 0.5, "0.4994 publishes as 0.499");
    }

    private static boolean same(double a, double b) {
        return Double.doubleToRawLongBits(a) == Double.doubleToRawLongBits(b) || (Double.isNaN(a) && Double.isNaN(b));
    }

    // -------------------------------------------------------- detector calibration

    private void detectorCalibration(Path scratch) throws IOException {
        Path good = writeCsv(scratch, "selftest_good.csv", GOOD_ROWS);
        Path bad1 = writeCsv(scratch, "selftest_bad_values.csv", BAD_VALUE_ROWS);
        Path bad2 = writeCsv(scratch, "selftest_bad_factor.csv", BAD_FACTOR_ROWS);

        List<Preconditions.Result> g = precheck(good);
        List<Preconditions.Result> b1 = precheck(bad1);
        List<Preconditions.Result> b2 = precheck(bad2);

        StringBuilder gq = new StringBuilder();
        int gClean = 0;
        for (Preconditions.Result r : g) {
            if (!"PASS".equals(r.status)) gq.append(r.id).append('=').append(r.status).append(' ');
            else gClean++;
        }
        check("R18: no precondition fires on known-GOOD input", gq.length() == 0,
              "these fired on sound input: " + gq);
        detectorSeparation.add("known-GOOD (" + GOOD_ROWS.length + " rows): " + gClean + "/" + g.size()
                + " PASS, fired: " + (gq.length() == 0 ? "none" : gq.toString().trim()));

        detectorSeparation.add("known-BAD values (" + BAD_VALUE_ROWS.length + " rows): fired " + fired(b1));
        detectorSeparation.add("known-BAD thousands factor (" + BAD_FACTOR_ROWS.length + " rows): fired " + fired(b2));

        check("R18: P-05 fires on a percent-point tariff", statusOf(b1, "P-05").equals("FAIL"), "got " + statusOf(b1, "P-05"));
        check("R18: P-06 fires on a negative amount", statusOf(b1, "P-06").equals("FLAGGED"), "got " + statusOf(b1, "P-06"));
        check("R18: P-07 fires on a duplicate identifier", statusOf(b1, "P-07").equals("FLAGGED"), "got " + statusOf(b1, "P-07"));
        check("R18: P-11 fires on a two-comma amount", statusOf(b1, "P-11").equals("FLAGGED"), "got " + statusOf(b1, "P-11"));
        check("R18: P-03 fires on an unreadable date", statusOf(b1, "P-03").equals("FAIL"), "got " + statusOf(b1, "P-03"));
        check("R18: P-04 fires on an 1899 date", statusOf(b1, "P-04").equals("FLAGGED"), "got " + statusOf(b1, "P-04"));
        check("R18: P-10 fires on a shadowing field name", statusOf(b1, "P-10").equals("FLAGGED"), "got " + statusOf(b1, "P-10"));
        check("R18: P-13 fires when the thousands factor is upside down", statusOf(b2, "P-13").equals("FLAGGED"), "got " + statusOf(b2, "P-13"));
        check("R18: P-13 does NOT fire on sound input", statusOf(g, "P-13").equals("PASS"), "got " + statusOf(g, "P-13"));
    }

    private static String fired(List<Preconditions.Result> rs) {
        StringBuilder sb = new StringBuilder();
        for (Preconditions.Result r : rs) if (!"PASS".equals(r.status)) sb.append(r.id).append('=').append(r.status).append(' ');
        return sb.length() == 0 ? "none" : sb.toString().trim();
    }

    private static String statusOf(List<Preconditions.Result> rs, String id) {
        for (Preconditions.Result r : rs) if (r.id.equals(id)) return r.status;
        return "ABSENT";
    }

    private List<Preconditions.Result> precheck(Path csv) throws IOException {
        Runner run = runOver(csv, List.of("abschlussdatum", "einloesungsdatum"), DateValue.fromIso("2026-03-31"));
        Preconditions pc = new Preconditions();
        pc.run(run, DateValue.fromIso("2026-03-31"), "self-test fixture");
        return pc.results;
    }

    private Runner runOver(Path csv, List<String> coercions, long valuation) throws IOException {
        CsvReader.Layout L = CsvReader.detect(csv);
        Runner run = new Runner(csv, L);
        run.profile(coercions);
        run.compute(valuation);
        run.buildJsDocument(valuation);
        return run;
    }

    private static Path writeCsv(Path dir, String name, String[] rows) throws IOException {
        Files.createDirectories(dir);
        Path p = dir.resolve(name);
        StringBuilder sb = new StringBuilder();
        for (String r : rows) sb.append(r).append('\n');
        Files.writeString(p, sb.toString(), StandardCharsets.UTF_8);
        return p;
    }

    // Known-GOOD: every field sound, every branch of the engine reachable, nothing a
    // precondition should object to. R18 requires this fixture to exist before any
    // detector is allowed to FAIL.
    private static final String[] GOOD_ROWS = {
        "BSV,abschlussdatum,einloesungsdatum,erstmalige_zuteilungsanwartschaft,Tilgungsbeginn,Vertragsende,DaBetrag,bausparsumme_teuro,guthaben,tariff_amount,contract_type",
        "700001,2001-03-01,2001-04-01,20110401,20110601,20220601,30000,30,12000,0.4,BS1",
        "700002,2007-05-01,2007-06-01,20200101,20200301,20310301,20000,20,11230,0.4,BS1",
        "700003,2019-01-01,2019-02-01,20290201,,,40000,40,4000,0.4,BS2",
        "700004,2014-01-01,2014-02-01,20280201,,,25000,25,23000,0.35,BS2",
        "700005,2008-01-01,2008-02-01,20180201,,,30000,30,9000,0.5,BSK",
        "700006,2010-09-01,2010-10-01,20211001,,,\"36.263,14\",\"36,263\",\"15.369,66\",\"0,4000\",VL7"
    };

    // Known-BAD (values): one defect per row, each aimed at a named precondition.
    private static final String[] BAD_VALUE_ROWS = {
        "BSV,abschlussdatum,einloesungsdatum,erstmalige_zuteilungsanwartschaft,Tilgungsbeginn,Vertragsende,DaBetrag,bausparsumme_teuro,guthaben,tariff_amount,contract_type,guthaben_alt",
        "700001,2001-03-01,2001-04-01,20110401,20110601,20220601,30000,30,12000,40,BS1,1",     // P-05 percent points
        "700001,2007-05-01,2007-06-01,20200101,,,20000,20,-500,0.4,BS1,1",                     // P-06 negative, P-07 duplicate id
        "700003,2019-01-01,2019-02-01,20131345,,,40000,40,4000,0.4,BS2,1",                     // P-03 unreadable date (no hyphen: no abort)
        "700004,1899-01-01,1899-02-01,20280201,,,25000,25,\"1,2,3\",0.4,BS2,1"                 // P-04 implausible year, P-11 two commas
    };

    // Known-BAD (thousands factor): the Bauspar sum arrives in euro, not thousands.
    private static final String[] BAD_FACTOR_ROWS = {
        "BSV,abschlussdatum,einloesungsdatum,erstmalige_zuteilungsanwartschaft,Tilgungsbeginn,Vertragsende,DaBetrag,bausparsumme_teuro,guthaben,tariff_amount,contract_type",
        "700001,2001-03-01,2001-04-01,20110401,20110601,20220601,30000,30000,12000,0.4,BS1",
        "700002,2007-05-01,2007-06-01,20200101,20200301,20310301,20000,20000,11230,0.4,BS1",
        "700003,2019-01-01,2019-02-01,20290201,,,40000,40000,4000,0.4,BS2"
    };
}
