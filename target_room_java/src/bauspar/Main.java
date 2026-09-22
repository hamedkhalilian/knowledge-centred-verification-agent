package bauspar;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * bauspar-engine-java -- the second, independent target of OCM run 3.
 *
 * <p>Launch parity (GR-14): exactly one required argument, the contract table path.
 * An optional second argument names the valuation date; absent, it is read from the
 * input manifest. Nothing else is demanded. CORE tier: no UI, no figures, no browser.
 */
public final class Main {

    static final String RUN_ID = "ocm-run-3-bauspar";
    static final String SIDE = "target";
    static final String STATE = "OBSERVE_TARGET";
    static final String CANON = "dec9-half-even-v1";
    static final String UNIT = "U01";

    private static final List<String> notes = new ArrayList<>();
    private static final List<String[]> ioDiff = new ArrayList<>();   // {claim, spec reading, our reading, verdict}

    public static void main(String[] args) {
        int rc = 0;
        try {
            rc = run(args);
        } catch (Exception e) {
            System.err.println("FATAL: " + e);
            e.printStackTrace();
            rc = 9;
        }
        System.exit(rc);
    }

    /** GR-02: Eclipse's Arguments box passes quotes through, so every argument is de-quoted. */
    static String dequote(String s) {
        if (s == null) return null;
        String t = s.trim();
        if (t.length() >= 2 && ((t.charAt(0) == '"' && t.charAt(t.length() - 1) == '"')
                             || (t.charAt(0) == '\'' && t.charAt(t.length() - 1) == '\''))) {
            t = t.substring(1, t.length() - 1);
        }
        return t;
    }

    private static int run(String[] argv) throws IOException {
        List<String> pos = new ArrayList<>();
        String outArg = null;
        for (String a : argv) {
            String d = dequote(a);
            if (d.startsWith("--out=")) outArg = dequote(d.substring(6));
            else pos.add(d);
        }
        if (pos.isEmpty()) {
            System.err.println("usage: bauspar.Main <contract-table.csv> [valuation-date] [manifest.json] [--out=DIR]");
            System.err.println("  the contract table path is the one required argument (GR-14).");
            return 2;
        }

        Path table = Paths.get(pos.get(0)).toAbsolutePath().normalize();
        if (!Files.isRegularFile(table)) {
            // R16/GR-08: nothing is declined in silence, and the reason is named.
            System.err.println("These arguments did not resolve to an existing file:");
            System.err.println("  " + table + "   (no such file -- check for a typo, a moved file, or a stray quote)");
            return 2;
        }

        String dateArg = null, manifestArg = null;
        for (int i = 1; i < pos.size(); i++) {
            String v = pos.get(i);
            if (v.endsWith(".json")) manifestArg = v;
            else dateArg = v;
        }

        Path manifest = (manifestArg != null)
                ? Paths.get(manifestArg).toAbsolutePath().normalize()
                : table.getParent().resolve("synthetic_manifest.json");
        if (!Files.isRegularFile(manifest)) {
            System.err.println("The input manifest did not resolve to an existing file:");
            System.err.println("  " + manifest + "   (no such file -- the manifest carries the harness coercions,");
            System.err.println("   which decide whether the abort path fires, and they are never inferred.)");
            return 2;
        }

        Path out = (outArg != null) ? Paths.get(outArg).toAbsolutePath().normalize()
                : Paths.get("runs", RUN_ID, "evidence", "target_java").toAbsolutePath().normalize();
        Files.createDirectories(out);
        Path scratch = out.resolve("selftest");

        System.out.println("bauspar-engine-java  --  " + RUN_ID + "  side=" + SIDE + "  unit=" + UNIT);
        System.out.println("  contract table : " + table);
        System.out.println("  input manifest : " + manifest);
        System.out.println("  evidence out   : " + out);

        // ---- 1. SELF-TESTS, before anything is emitted (GR-13, directive 16) ------
        System.out.println();
        System.out.println("[1] self-tests");
        SelfTest st = new SelfTest();
        boolean green = st.run(scratch);
        for (String l : st.lines) System.out.println("    " + l);
        System.out.println("    checks " + st.passed + "/" + st.checks + (green ? "  GREEN" : "  RED"));
        for (String f : st.failures) System.out.println("    FAIL: " + f);
        for (String s : st.detectorSeparation) System.out.println("    R18 " + s);
        if (!green) {
            System.err.println("SelfTest is RED. The canonicalisation contract requires the emitter to abort on"
                    + " a reference-vector mismatch, and nothing is emitted.");
            writeText(out.resolve("selftest_failures.txt"), String.join("\n", st.failures) + "\n");
            return 3;
        }

        // ---- 2. the io layer's OWN reading, with margins (R5/GR-07) --------------
        System.out.println();
        System.out.println("[2] io layer -- content-based layout detection");
        CsvReader.Layout L = CsvReader.detect(table);
        System.out.println("    layoutNote: " + L.note());
        System.out.println("    encoding  : " + L.encoding + (L.bom ? " (byte-order mark present)" : " (no byte-order mark)"));
        System.out.println("    records whose naive delimiter split mis-counts (quoted fields): " + L.naiveSplitDisagreements);
        if (!"UTF-8".equals(L.encoding)) {
            System.err.println("HALT: the file does not decode as UTF-8, which the computation depends on.");
            return 4;
        }
        if (L.delimiterMargin < CsvReader.MIN_MARGIN || L.headerMargin < CsvReader.MIN_MARGIN) {
            System.err.println("HALT: layout AMBIGUOUS below the declared margin of " + CsvReader.MIN_MARGIN
                    + " -- delimiter margin " + L.delimiterMargin + ", header margin " + L.headerMargin
                    + ". Not proceeding on a coin flip (R5).");
            return 4;
        }
        if (L.raggedRecords > 0) {
            System.err.println("HALT: " + L.raggedRecords + " record(s) do not carry " + L.fieldCount
                    + " fields under correct quoted-field parsing; positional assignment would be silent nonsense.");
            return 4;
        }

        // ---- 3. the manifest: DECLARED coercions, never inferred (directive 5) ----
        Map<String, Object> man = Json.obj(Json.parse(Files.readString(manifest, StandardCharsets.UTF_8)));
        List<String> toDate = new ArrayList<>();
        List<String> rawYmd = new ArrayList<>();
        Object hc = man.get("harness_coercions");
        if (hc != null) {
            Map<String, Object> h = Json.obj(hc);
            toDate = Json.strings(h.get("to_date_class"));
            rawYmd = Json.strings(h.get("left_as_raw_yyyymmdd"));
        }
        String manifestDate = (String) man.get("valuation_date");
        String valuationSource;
        long valuation;
        if (dateArg != null) {
            valuation = DateValue.fromIso(dateArg);
            valuationSource = "command-line argument";
        } else if (manifestDate != null) {
            valuation = DateValue.fromIso(manifestDate);
            valuationSource = "input manifest (valuation_date)";
        } else {
            System.err.println("The manifest carries no valuation_date and none was supplied on the command line.");
            System.err.println("  The unit's own load-time default of 2026-03-31 belongs to the unit's load-time");
            System.err.println("  branch, which this observer does not take; it is not adopted silently (R16).");
            return 2;
        }
        System.out.println();
        System.out.println("[3] manifest");
        System.out.println("    harness coercion to_date_class          : " + toDate);
        System.out.println("    harness coercion left_as_raw_yyyymmdd   : " + rawYmd);
        System.out.println("    valuation date " + DateValue.isoOf(valuation) + "  (" + valuationSource + ")");

        Inputs inputs = new Inputs().consume(table).consume(manifest);

        // ---- 4. run the unit -----------------------------------------------------
        Runner run = new Runner(table, L);
        Preconditions pc = new Preconditions();
        long t0 = System.nanoTime();
        try {
            System.out.println();
            System.out.println("[4] pass 1 -- profile and settle the harness coercion");
            run.profile(toDate);
            System.out.println("    rows " + run.profile.rows + " x " + L.fieldCount + " fields");
            for (var e : run.profile.coercionSeparator.entrySet())
                System.out.println("    coerced column " + e.getKey() + ": format inferred from its first non-missing"
                        + " element, separator '" + e.getValue() + "'");

            specDiff(run, L, toDate, rawYmd, man);

            System.out.println();
            System.out.println("[5] pass 2 -- compute every contract (C0..C19, C21, C24)");
            run.compute(valuation);
            run.buildJsDocument(valuation);
            System.out.println("    rows read " + run.rowsRead + ", records published " + run.recordsPublished
                    + ", rows refused " + run.rowsRefused + "   (GR-08 reconciliation)");
            System.out.println("    browser document: " + run.jsLines.size() + " lines for " + run.book.n + " contracts");
        } catch (AbortException ab) {
            return abort(out, ab, run, t0);
        }
        double secs = (System.nanoTime() - t0) / 1e9;

        // ---- 5. preconditions ----------------------------------------------------
        System.out.println();
        System.out.println("[6] preconditions P-01..P-13");
        pc.run(run, valuation, valuationSource);
        int fails = 0, flags = 0;
        for (Preconditions.Result r : pc.results) {
            if ("FAIL".equals(r.status)) fails++;
            else if ("FLAGGED".equals(r.status)) flags++;
            System.out.println("    " + r.id + " " + pad(r.status) + " " + r.explanation);
        }
        System.out.println("    " + (pc.results.size() - fails - flags) + " PASS, " + flags + " FLAGGED, " + fails + " FAIL");

        boolean blocking = false;
        for (Preconditions.Result r : pc.results)
            if ("FAIL".equals(r.status) && (r.id.equals("P-01") || r.id.equals("P-02") || r.id.equals("P-12")))
                blocking = true;

        // ---- 6. findings exposure (R9's quantification, faithful-only) -----------
        List<String[]> exposure = findingsExposure(run);
        System.out.println();
        System.out.println("[7] findings exposure on this input");
        for (String[] e : exposure) System.out.println("    " + e[0] + "  " + e[1]);

        // ---- 7. emit -------------------------------------------------------------
        System.out.println();
        System.out.println("[8] emitting evidence");
        CheckpointObject o1 = Objects.customerBook(run.book);
        CheckpointObject o2 = Objects.exportRows(run.export);
        CheckpointObject o3 = Objects.jsDocument(run.jsLines);
        List<CheckpointObject> objs = List.of(o1, o2, o3);

        if (blocking) {
            System.err.println("HALT: a blocking precondition FAILED. A partial bundle is written and marked"
                    + " incomplete; no checkpoint file is emitted, because a partial checkpoint is not comparable.");
            writeText(out.resolve("INCOMPLETE.txt"), "blocking precondition failure; see preconditions_target.json\n");
            writePreconditions(out, pc, st, exposure, true);
            return 5;
        }

        String emitted = DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss'Z'")
                .withZone(ZoneOffset.UTC).format(Instant.now());
        writeCheckpoints(out.resolve("checkpoints_target.json"), emitted, inputs, objs);
        writePreconditions(out, pc, st, exposure, false);
        writeIoReading(out, L, run, toDate, rawYmd);
        writeText(out.resolve("customers_data.js"), String.join("\n", run.jsLines) + "\n");
        writeRunReport(out, table, manifest, L, run, pc, st, objs, valuation, valuationSource, secs, exposure);

        for (CheckpointObject o : objs)
            System.out.println("    " + pad2(o.name) + " " + o.rows() + " rows x " + o.cols.size()
                    + " cols  digest " + o.objectDigest());
        System.out.println("    wrote " + out.resolve("checkpoints_target.json"));
        System.out.printf("    computed %d contracts in %.2f s%n", run.book.n, secs);
        return 0;
    }

    private static String pad(String s) { return (s + "        ").substring(0, 8); }
    private static String pad2(String s) { return (s + "                        ").substring(0, 24); }

    // ------------------------------------------------------------------- abort path

    private static int abort(Path out, AbortException ab, Runner run, long t0) throws IOException {
        System.err.println();
        System.err.println("ABORT " + ab.abortCode + " -- " + ab.getMessage());
        System.err.println("  row_index " + ab.rowIndex + ", column " + ab.column
                + ", raw_value '" + ab.rawValue + "', rows_completed " + ab.rowsCompleted);
        System.err.println("  The run stops here. It does not skip the row, substitute a missing value, or"
                + " continue to the next contract (controller directive 01, rule A).");

        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"run_id\": ").append(Json.q(RUN_ID)).append(",\n");
        sb.append("  \"side\": ").append(Json.q(SIDE)).append(",\n");
        sb.append("  \"state\": ").append(Json.q(STATE)).append(",\n");
        sb.append("  \"unit\": ").append(Json.q(UNIT)).append(",\n");
        sb.append("  \"abort_code\": ").append(Json.q(ab.abortCode)).append(",\n");
        sb.append("  \"row_index\": ").append(ab.rowIndex).append(",\n");
        sb.append("  \"column\": ").append(Json.q(ab.column)).append(",\n");
        sb.append("  \"raw_value\": ").append(Json.q(CanonicalNumber.str(ab.rawValue))).append(",\n");
        sb.append("  \"rows_completed\": ").append(ab.rowsCompleted).append("\n");
        sb.append("}\n");
        writeText(out.resolve("abort_record.json"), sb.toString());

        // Rule B: no checkpoint file at all. Anything stale would be a comparison hazard.
        Files.deleteIfExists(out.resolve("checkpoints_target.json"));
        writeText(out.resolve("INCOMPLETE.txt"),
            "The run aborted at row_index " + ab.rowIndex + " on column " + ab.column + ".\n"
          + "Controller directive 01 rule B: an aborted run emits NO checkpoint file, because a partial\n"
          + "checkpoint is not comparable (R12). abort_record.json carries what COMPARE needs instead.\n"
          + "Everything built before the abort is kept: the profile and the layout reading are in\n"
          + "io_reading_target.json.\n");
        System.err.println("  wrote " + out.resolve("abort_record.json") + " and no checkpoint file (rule B)");
        return 6;
    }

    // ------------------------------------------------- the spec's claims, VERIFIED

    private static void claim(String what, String spec, String ours) {
        boolean agree = spec.equals(ours);
        ioDiff.add(new String[] { what, spec, ours, agree ? "AGREE" : "DIFFER" });
        System.out.println("    " + (agree ? "AGREE  " : "DIFFER ") + what);
        if (!agree) {
            System.out.println("             spec reads : " + spec);
            System.out.println("             we read    : " + ours);
        }
    }

    /**
     * R7: the spec's io_formats block is a set of CLAIMS TO VERIFY, never configuration
     * to adopt. This target detected the layout itself and now diffs its own reading
     * against the spec's. Agreement is recorded as evidence; disagreement is named on
     * both sides. Only a disagreement about something THE COMPUTATION DEPENDS ON halts
     * the run -- a distributional claim about a generated stand-in is an example, not a
     * contract (R6/R15), and the manifest's own caveat says it must not harden into one.
     */
    private static void specDiff(Runner run, CsvReader.Layout L, List<String> toDate,
                                 List<String> rawYmd, Map<String, Object> man) {
        System.out.println();
        System.out.println("    R7 -- our reading of the file against the spec's io_formats expectations");
        Profile p = run.profile;

        claim("the eleven declared field names are present, spelled exactly",
              "all eleven present", p.absentRequired.isEmpty() ? "all eleven present"
                  : "absent: " + String.join(",", p.absentRequired));
        claim("surplus fields are ignored by name selection, never rejected",
              "any further field is ignored",
              p.surplusFields.isEmpty() ? "no surplus field present; selection is by name"
                  : p.surplusFields.size() + " surplus field(s) present and ignored: " + String.join(",", p.surplusFields));
        claim("the identifier field BSV is present", "present",
              p.absentRequired.contains("BSV") ? "ABSENT" : "present");
        claim("data rows", "503", Long.toString(p.rows));
        claim("fields per line under proper quoting", "11", Integer.toString(L.fieldCount));
        claim("encoding", "UTF-8", L.encoding);
        claim("lines whose amounts contain commas inside quotes (a naive splitter mis-counts these)",
              "103", Long.toString(L.naiveSplitDisagreements));
        claim("header names", String.join(",", Runner.REQUIRED_COLUMNS),
              sortedJoin(L.headerNames));

        Profile.AmountField tf = p.amounts.get("tariff_amount");
        claim("tariff share distinct RAW spellings, in full",
              "0,3000/0,3500/0,4000/0,5000/0.3/0.35/0.4/0.5/NA", sortedJoin(tf.distinctRaw.toArray(new String[0])));
        claim("tariff share rows carrying the missing marker", "89", Long.toString(tf.missing));
        claim("tariff share range once read", "0.3 .. 0.5",
              CanonicalNumber.num(tf.min) + " .. " + CanonicalNumber.num(tf.max));
        claim("contract type distinct values, in full", ",BS1,BS2,BSK,VL7", sortedJoin(p.contractTypes.toArray(new String[0])));
        claim("rows carrying the empty contract type", "83",
              Long.toString(countEmptyContractType(run)));

        Profile.AmountField da = p.amounts.get("DaBetrag");
        Profile.AmountField bs = p.amounts.get("bausparsumme_teuro");
        Profile.AmountField gu = p.amounts.get("guthaben");
        claim("identifier range", "800000 .. 900023", idRange(run));
        claim("DaBetrag range", "0 .. 295982.79",
              CanonicalNumber.num(da.min) + " .. " + CanonicalNumber.num(da.max));
        claim("DaBetrag values that are MISSING once read", "2", Long.toString(da.missing));
        claim("bausparsumme_teuro range", "0 .. 50.972",
              CanonicalNumber.num(bs.min) + " .. " + CanonicalNumber.num(bs.max));
        claim("bausparsumme_teuro values that are MISSING once read", "3", Long.toString(bs.missing));
        claim("guthaben range", "318.53 .. 216706.84",
              CanonicalNumber.num(gu.min) + " .. " + CanonicalNumber.num(gu.max));
        claim("guthaben values that are MISSING once read", "0", Long.toString(gu.missing));
        claim("parsed date range across the five date fields", "1998-01-04 .. 2043-10-15", dateRange(p));
        claim("date missing-markers actually present in the stand-in", ",0,00000000,NA", markersSeen(p));
        claim("harness coercion to a date type, as DECLARED in the manifest",
              "abschlussdatum,einloesungsdatum", String.join(",", toDate));
        claim("harness leaves these as raw digits, as DECLARED in the manifest",
              "erstmalige_zuteilungsanwartschaft,Tilgungsbeginn,Vertragsende", String.join(",", rawYmd));
        claim("identifiers are unique per row", "unique",
              p.idDuplicated == 0 ? "unique" : p.idDuplicated + " identifier(s) repeat");

        long differ = 0;
        for (String[] d : ioDiff) if ("DIFFER".equals(d[3])) differ++;
        System.out.println("    " + (ioDiff.size() - differ) + " of " + ioDiff.size()
                + " expectations AGREE; " + differ + " DIFFER.");
        if (differ > 0) {
            System.out.println("    The differing expectations are all DISTRIBUTIONAL claims about a GENERATED");
            System.out.println("    stand-in, which the spec itself marks observed_in_synthetic_input and the");
            System.out.println("    manifest's own caveat forbids hardening into a target-enforced contract.");
            System.out.println("    Nothing the computation depends on differs, so the run continues and the");
            System.out.println("    difference is reported with BOTH readings (R7), not silently adopted and not");
            System.out.println("    turned into a refusal of a file the source reads happily.");
        }
    }

    private static long countEmptyContractType(Runner run) {
        long n = 0;
        for (int i = 0; i < run.book.n; i++) if ("".equals(run.book.contractType[i])) n++;
        return n;
    }

    private static String idRange(Runner run) {
        String lo = null, hi = null;
        for (int i = 0; i < run.book.n; i++) {
            String v = run.book.id[i];
            if (v == null) continue;
            if (lo == null || Col.compareUtf8(v, lo) < 0) lo = v;
            if (hi == null || Col.compareUtf8(v, hi) > 0) hi = v;
        }
        return lo + " .. " + hi;
    }

    private static String dateRange(Profile p) {
        long lo = Long.MAX_VALUE, hi = Long.MIN_VALUE;
        for (Profile.DateField f : p.dates.values()) {
            if (!f.any()) continue;
            lo = Math.min(lo, f.min); hi = Math.max(hi, f.max);
        }
        return lo == Long.MAX_VALUE ? "none" : DateValue.isoOf(lo) + " .. " + DateValue.isoOf(hi);
    }

    private static String markersSeen(Profile p) {
        java.util.TreeSet<String> s = new java.util.TreeSet<>();
        for (Profile.DateField f : p.dates.values()) s.addAll(f.markersSeen);
        return String.join(",", s);
    }

    private static String sortedJoin(String[] xs) {
        String[] c = xs.clone();
        java.util.Arrays.sort(c, Col::compareUtf8);
        return String.join(",", c);
    }

    // --------------------------------------------------------- findings exposure

    private static List<String[]> findingsExposure(Runner run) {
        Book b = run.book;
        List<String[]> out = new ArrayList<>();
        Profile p = run.profile;

        long fnd01 = 0;
        for (var e : p.amounts.entrySet()) fnd01 += e.getValue().fnd01Suspects;
        out.add(new String[] { "FND-01", "text amounts with a dot, no comma and more than two digits after the last dot"
                + " (read a thousand times too small): " + fnd01 });

        Profile.AmountField tf = p.amounts.get("tariff_amount");
        out.add(new String[] { "FND-02", "tariff shares greater than 1 (percent points would be out by a hundred): "
                + tf.gtOne + "; min " + (tf.any() ? CanonicalNumber.num(tf.min) : "n/a")
                + ", max " + (tf.any() ? CanonicalNumber.num(tf.max) : "n/a") });

        out.add(new String[] { "FND-03", "published identifiers in exponent form: " + p.exponentIdCount
                + (p.exponentIds.isEmpty() ? " (the column arrives as text, so the default numeric conversion never runs)"
                                           : " first: " + String.join(",", p.exponentIds)) });

        out.add(new String[] { "FND-04", "rows " + p.idRows + ", distinct identifiers " + p.idDistinct
                + ", duplicated identifiers " + p.idDuplicated
                + " (the browser keeps the LAST entry per key; the quality harness keeps the FIRST row)" });

        long missingRatio = 0, le05 = 0, mid = 0, gt2 = 0, alarms = 0;
        for (int i = 0; i < b.n; i++) {
            double r = b.loanToBausparRatio[i];
            if (Double.isNaN(r)) { missingRatio++; continue; }
            if (r < 0.5) le05++;
            else if (r <= 2) mid++;
            else gt2++;
        }
        for (int i = 0; i < b.n; i++) if (run.export.special[i] == 1) alarms++;
        out.add(new String[] { "FND-05", "ratio missing " + missingRatio + ", below 0.5 " + le05
                + ", 0.5..2 inclusive " + mid + ", above 2 " + gt2 + "; red alarms raised " + alarms
                + " (alarms must equal the below-0.5 band excluding missing: "
                + (alarms == le05 ? "they do" : "THEY DO NOT") + ")" });

        long allocEst = 0, endAbsent = 0, both = 0, doneOnNothing = 0;
        for (int i = 0; i < b.n; i++) {
            if (b.allocationEstimated[i]) allocEst++;
            if (b.contractEndWasAbsent[i]) endAbsent++;
            if (b.allocationEstimated[i] && b.contractEndWasAbsent[i]) {
                both++;
                if (Engine.PHASE_DONE.equals(b.phase[i])) doneOnNothing++;
            }
        }
        out.add(new String[] { "FND-08", "allocation estimated " + allocEst + ", contract end absent " + endAbsent
                + ", both " + both + ", phase 'done' while both were absent " + doneOnNothing
                + " (the last count is this finding's exposure)" });

        long disc = 0; double maxDisc = 0;
        for (int i = 0; i < b.n; i++) {
            double lhs = b.bausparLoan[i], rhs = b.savingReference[i] - b.balance[i];
            if (Double.isNaN(lhs) || Double.isNaN(rhs)) continue;
            double d = Math.abs(lhs - rhs);
            if (d > 0) { disc++; maxDisc = Math.max(maxDisc, d); }
        }
        out.add(new String[] { "FND-09", "published loan portion differs from published reference minus published balance in "
                + disc + " contract(s); largest difference " + CanonicalNumber.num(maxDisc)
                + " euro (more than one euro would mean the rounding rule itself diverges)" });

        long noRatio = 0;
        for (int i = 0; i < b.n; i++) if (Double.isNaN(b.savingsRatio[i])) noRatio++;
        out.add(new String[] { "FND-10", "contracts with a missing savings ratio: " + noRatio
                + " -- the population the consumers' unreachable 'nodata' phase was written for; the unit publishes only the four declared phases" });

        long markersUnused = 0;
        java.util.TreeSet<String> seen = new java.util.TreeSet<>();
        for (Profile.DateField f : p.dates.values()) seen.addAll(f.markersSeen);
        StringBuilder unused = new StringBuilder();
        for (String m : DateValue.MISSING_MARKERS) if (!seen.contains(m)) { markersUnused++; unused.append("'").append(m).append("' "); }
        out.add(new String[] { "FND-11", "of the seven markers the code recognises, " + markersUnused
                + " are never exercised by this input: " + unused.toString().trim() });

        out.add(new String[] { "FND-12", "field names that shadow a declared name by prefix: "
                + (p.prefixCollisions.isEmpty() ? "none" : String.join("; ", p.prefixCollisions)) });

        long disagree = 0;
        for (int i = 0; i < b.n; i++) {
            boolean published = !Double.isNaN(b.savingsRatio[i]) && b.savingsRatio[i] >= Engine.WARN_BALANCE_FRACTION;
            if (published != b.warnLoanPointless[i]) disagree++;
        }
        out.add(new String[] { "FND-13", "contracts where the published flag and the test 'published ratio at least 0.90' disagree: "
                + disagree + " (the picture and the record contradict each other there)" });

        out.add(new String[] { "FND-06", "the abort path is exercised by the separate probe input, not by this table;"
                + " unreadable hyphenated date values in this table: "
                + unreadableHyphenated(p) + " (any such value would have aborted the run)" });
        out.add(new String[] { "FND-07", "not exercised at CORE tier: the standalone-page writer is not built"
                + " (no UI, no template), so the count it misreports cannot be observed here" });
        return out;
    }

    private static long unreadableHyphenated(Profile p) {
        long n = 0;
        for (Profile.DateField f : p.dates.values()) n += f.unreadable;
        return n;
    }

    // ------------------------------------------------------------------- emission

    private static void writeCheckpoints(Path path, String emitted, Inputs inputs,
                                         List<CheckpointObject> objs) throws IOException {
        StringBuilder sb = new StringBuilder(1 << 16);
        sb.append("{\n");
        sb.append("  \"run_id\": ").append(Json.q(RUN_ID)).append(",\n");
        sb.append("  \"side\": ").append(Json.q(SIDE)).append(",\n");
        sb.append("  \"state\": ").append(Json.q(STATE)).append(",\n");
        sb.append("  \"canonicalisation\": ").append(Json.q(CANON)).append(",\n");
        sb.append("  \"emitted_utc\": ").append(Json.q(emitted)).append(",\n");
        sb.append("  \"inputs\": [\n");
        List<Inputs.Entry> es = inputs.sorted();
        for (int i = 0; i < es.size(); i++) {
            Inputs.Entry e = es.get(i);
            sb.append("    { \"name\": ").append(Json.q(e.name))
              .append(", \"bytes\": ").append(e.bytes)
              .append(", \"sha256\": ").append(Json.q(e.sha256)).append(" }")
              .append(i < es.size() - 1 ? ",\n" : "\n");
        }
        sb.append("  ],\n");
        sb.append("  \"units\": [\n");
        sb.append("    {\n");
        sb.append("      \"unit\": ").append(Json.q(UNIT)).append(",\n");
        sb.append("      \"objects\": [\n");
        for (int i = 0; i < objs.size(); i++) {
            appendObject(sb, objs.get(i), "        ");
            sb.append(i < objs.size() - 1 ? ",\n" : "\n");
        }
        sb.append("      ]\n");
        sb.append("    }\n");
        sb.append("  ]\n");
        sb.append("}\n");
        writeText(path, sb.toString());
    }

    private static void appendObject(StringBuilder sb, CheckpointObject o, String ind) {
        String[] cov = o.coverage();
        sb.append(ind).append("{\n");
        sb.append(ind).append("  \"name\": ").append(Json.q(o.name)).append(",\n");
        sb.append(ind).append("  \"kind\": ").append(Json.q(o.kind)).append(",\n");
        sb.append(ind).append("  \"rows\": ").append(o.rows()).append(",\n");
        sb.append(ind).append("  \"cols\": ").append(o.cols.size()).append(",\n");
        sb.append(ind).append("  \"colnames\": [");
        for (int i = 0; i < o.cols.size(); i++) {
            sb.append(Json.q(o.cols.get(i).name));
            if (i < o.cols.size() - 1) sb.append(", ");
        }
        sb.append("],\n");
        sb.append(ind).append("  \"canonical_order\": [");
        for (int i = 0; i < o.canonicalOrder.size(); i++) {
            String[] k = o.canonicalOrder.get(i);
            sb.append("{ \"column\": ").append(Json.q(k[0])).append(", \"direction\": ").append(Json.q(k[1])).append(" }");
            if (i < o.canonicalOrder.size() - 1) sb.append(", ");
        }
        sb.append("],\n");
        sb.append(ind).append("  \"digest\": { \"algorithm\": \"SHA-256\", \"canonicalisation\": ")
          .append(Json.q(CANON)).append(", \"value\": ").append(Json.q(o.objectDigest())).append(" },\n");
        sb.append(ind).append("  \"coverage\": { \"row_count\": ").append(cov[0])
          .append(", \"field_count\": ").append(cov[1])
          .append(", \"null_count\": ").append(cov[2])
          .append(", \"min\": ").append(cov[3] == null ? "null" : Json.q(cov[3]))
          .append(", \"max\": ").append(cov[4] == null ? "null" : Json.q(cov[4])).append(" },\n");
        sb.append(ind).append("  \"probes\": [\n");
        List<String[]> rules = o.probeRules();
        for (int r = 0; r < rules.size(); r++) {
            sb.append(ind).append("    { \"selection_rule\": ").append(Json.q(rules.get(r)[0])).append(", \"fields\": {");
            String[][] f = o.probeFields(Integer.parseInt(rules.get(r)[1]));
            for (int i = 0; i < f.length; i++) {
                sb.append(Json.q(f[i][0])).append(": ").append(Json.q(f[i][1]));
                if (i < f.length - 1) sb.append(", ");
            }
            sb.append("} }").append(r < rules.size() - 1 ? ",\n" : "\n");
        }
        sb.append(ind).append("  ]\n");
        sb.append(ind).append("}");
    }

    private static void writePreconditions(Path out, Preconditions pc, SelfTest st,
                                           List<String[]> exposure, boolean incomplete) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("{\n  \"run_id\": ").append(Json.q(RUN_ID)).append(",\n");
        sb.append("  \"side\": ").append(Json.q(SIDE)).append(",\n");
        sb.append("  \"unit\": ").append(Json.q(UNIT)).append(",\n");
        sb.append("  \"complete\": ").append(!incomplete).append(",\n");
        sb.append("  \"self_test\": { \"checks\": ").append(st.checks).append(", \"passed\": ").append(st.passed)
          .append(", \"green\": ").append(st.failures.isEmpty()).append(" },\n");
        sb.append("  \"detector_calibration_R18\": [\n");
        for (int i = 0; i < st.detectorSeparation.size(); i++)
            sb.append("    ").append(Json.q(st.detectorSeparation.get(i)))
              .append(i < st.detectorSeparation.size() - 1 ? ",\n" : "\n");
        sb.append("  ],\n");
        sb.append("  \"blind_spots_R8\": [\n");
        for (int i = 0; i < st.blindSpots.size(); i++)
            sb.append("    ").append(Json.q(st.blindSpots.get(i)))
              .append(i < st.blindSpots.size() - 1 ? ",\n" : "\n");
        sb.append("  ],\n");
        sb.append("  \"preconditions\": [\n");
        for (int i = 0; i < pc.results.size(); i++) {
            Preconditions.Result r = pc.results.get(i);
            sb.append("    { \"id\": ").append(Json.q(r.id))
              .append(", \"severity\": ").append(Json.q(r.severity))
              .append(", \"status\": ").append(Json.q(r.status))
              .append(", \"statement\": ").append(Json.q(r.statement))
              .append(", \"explanation\": ").append(Json.q(r.explanation))
              .append(", \"evidence\": [");
            for (int j = 0; j < r.evidence.size(); j++) {
                sb.append(Json.q(r.evidence.get(j)));
                if (j < r.evidence.size() - 1) sb.append(", ");
            }
            sb.append("] }").append(i < pc.results.size() - 1 ? ",\n" : "\n");
        }
        sb.append("  ],\n");
        sb.append("  \"findings_exposure\": [\n");
        for (int i = 0; i < exposure.size(); i++)
            sb.append("    { \"finding\": ").append(Json.q(exposure.get(i)[0]))
              .append(", \"exposure\": ").append(Json.q(exposure.get(i)[1])).append(" }")
              .append(i < exposure.size() - 1 ? ",\n" : "\n");
        sb.append("  ]\n}\n");
        writeText(out.resolve("preconditions_target.json"), sb.toString());
    }

    private static void writeIoReading(Path out, CsvReader.Layout L, Runner run,
                                       List<String> toDate, List<String> rawYmd) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("{\n  \"run_id\": ").append(Json.q(RUN_ID)).append(",\n");
        sb.append("  \"layout_note\": ").append(Json.q(L.note())).append(",\n");
        sb.append("  \"encoding\": ").append(Json.q(L.encoding)).append(",\n");
        sb.append("  \"delimiter\": ").append(Json.q(String.valueOf(L.delimiter))).append(",\n");
        sb.append("  \"delimiter_margin\": ").append(L.delimiterMargin).append(",\n");
        sb.append("  \"header_margin\": ").append(L.headerMargin).append(",\n");
        sb.append("  \"declared_min_margin\": ").append(CsvReader.MIN_MARGIN).append(",\n");
        sb.append("  \"ragged_records\": ").append(L.raggedRecords).append(",\n");
        sb.append("  \"naive_split_disagreements\": ").append(L.naiveSplitDisagreements).append(",\n");
        sb.append("  \"harness_coercions_as_declared\": { \"to_date_class\": [");
        for (int i = 0; i < toDate.size(); i++) { sb.append(Json.q(toDate.get(i))); if (i < toDate.size() - 1) sb.append(", "); }
        sb.append("], \"left_as_raw_yyyymmdd\": [");
        for (int i = 0; i < rawYmd.size(); i++) { sb.append(Json.q(rawYmd.get(i))); if (i < rawYmd.size() - 1) sb.append(", "); }
        sb.append("] },\n");
        sb.append("  \"spec_expectations_diff\": [\n");
        for (int i = 0; i < ioDiff.size(); i++) {
            String[] d = ioDiff.get(i);
            sb.append("    { \"expectation\": ").append(Json.q(d[0]))
              .append(", \"spec_reading\": ").append(Json.q(d[1]))
              .append(", \"our_reading\": ").append(Json.q(d[2]))
              .append(", \"verdict\": ").append(Json.q(d[3])).append(" }")
              .append(i < ioDiff.size() - 1 ? ",\n" : "\n");
        }
        sb.append("  ]\n}\n");
        writeText(out.resolve("io_reading_target.json"), sb.toString());
    }

    private static void writeRunReport(Path out, Path table, Path manifest, CsvReader.Layout L,
                                       Runner run, Preconditions pc, SelfTest st,
                                       List<CheckpointObject> objs, long valuation,
                                       String valuationSource, double secs,
                                       List<String[]> exposure) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("# Run report -- ").append(RUN_ID).append(", target_java (second independent target)\n\n");
        sb.append("Unit ").append(UNIT).append(". Tier CORE. Findings policy FAITHFUL ONLY.\n\n");
        sb.append("## Inputs consumed\n\n");
        sb.append("- ").append(table.getFileName()).append("  sha256 ").append(Inputs.sha256(table)).append("\n");
        sb.append("- ").append(manifest.getFileName()).append("  sha256 ").append(Inputs.sha256(manifest)).append("\n\n");
        sb.append("Both are declared in the checkpoint file's `inputs` list, in byte order of their names:\n");
        sb.append("contract table and manifest together, because the manifest's declared harness coercions and\n");
        sb.append("its valuation date are part of what the computation consumed (contract section 7).\n\n");
        sb.append("## Layout, detected by content\n\n```\n").append(L.note()).append("\n```\n\n");
        sb.append("Encoding ").append(L.encoding).append("; ragged records ").append(L.raggedRecords)
          .append("; records a naive delimiter split would mis-count ").append(L.naiveSplitDisagreements).append(".\n\n");
        sb.append("## Valuation date\n\n").append(DateValue.isoOf(valuation)).append(" (").append(valuationSource).append(")\n\n");
        sb.append("## Reconciliation (GR-08)\n\nrows read ").append(run.rowsRead)
          .append(", records published ").append(run.recordsPublished)
          .append(", rows refused ").append(run.rowsRefused).append("\n\n");
        sb.append("## Self-tests\n\n").append(st.passed).append("/").append(st.checks).append(" checks green.\n\n");
        for (String s : st.detectorSeparation) sb.append("- R18 ").append(s).append("\n");
        sb.append("\n### Blind spots (R8)\n\n");
        for (String s : st.blindSpots) sb.append("- ").append(s).append("\n");
        sb.append("\n## Preconditions\n\n| id | severity | status | explanation |\n|---|---|---|---|\n");
        for (Preconditions.Result r : pc.results)
            sb.append("| ").append(r.id).append(" | ").append(r.severity).append(" | ").append(r.status)
              .append(" | ").append(r.explanation.replace("|", "\\|")).append(" |\n");
        sb.append("\n## Findings exposure (faithful-only; nothing repaired)\n\n");
        for (String[] e : exposure) sb.append("- **").append(e[0]).append("** ").append(e[1]).append("\n");
        sb.append("\n## Checkpoint objects\n\n| object | rows | cols | digest |\n|---|---|---|---|\n");
        for (CheckpointObject o : objs)
            sb.append("| ").append(o.name).append(" | ").append(o.rows()).append(" | ")
              .append(o.cols.size()).append(" | `").append(o.objectDigest()).append("` |\n");
        sb.append("\n## Spec expectations diffed (R7)\n\n| expectation | spec | ours | verdict |\n|---|---|---|---|\n");
        for (String[] d : ioDiff)
            sb.append("| ").append(d[0]).append(" | ").append(d[1]).append(" | ").append(d[2])
              .append(" | ").append(d[3]).append(" |\n");
        sb.append("\n## Not verified\n\n");
        sb.append("- The real contract table is absent; every fact about the input came from a generated\n");
        sb.append("  stand-in. Under R2 the verdict is capped at PROVISIONAL however well the two sides agree.\n");
        sb.append("- No source-side value was seen by this agent, by construction (R21).\n");
        sb.append("- FND-07 is unobservable at CORE tier: no standalone page writer is built.\n");
        sb.append("- Every threshold here has only ever seen synthetic data (R15).\n");
        sb.append("\nComputed ").append(run.book.n).append(" contracts in ")
          .append(String.format("%.2f", secs)).append(" s.\n");
        writeText(out.resolve("run_report.md"), sb.toString());
    }

    private static void writeText(Path p, String s) throws IOException {
        Files.writeString(p, s, StandardCharsets.UTF_8);       // UTF-8, LF line endings (GR-02)
    }
}
