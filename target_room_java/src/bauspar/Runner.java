package bauspar;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Reads the contract table and runs the unit over it.
 *
 * <p>Two streaming passes, never a materialised table (GR-09/R11):
 * <ol>
 *   <li>PASS 1 profiles the file and settles the harness coercion. The date conversion
 *       the harness applies runs over a WHOLE COLUMN and infers its format from the
 *       first non-missing element, so that element has to be found before any row is
 *       computed -- and if it is unreadable the run aborts there (controller directive
 *       01, path 2).</li>
 *   <li>PASS 2 computes each contract and writes it into the columnar book.</li>
 * </ol>
 */
public final class Runner {

    public static final String[] REQUIRED_COLUMNS = {
        "BSV", "DaBetrag", "Tilgungsbeginn", "Vertragsende", "abschlussdatum",
        "bausparsumme_teuro", "contract_type", "einloesungsdatum",
        "erstmalige_zuteilungsanwartschaft", "guthaben", "tariff_amount"
    };
    public static final String[] DATE_COLUMNS = {
        "abschlussdatum", "einloesungsdatum", "erstmalige_zuteilungsanwartschaft",
        "Tilgungsbeginn", "Vertragsende"
    };
    public static final String[] AMOUNT_COLUMNS = {
        "DaBetrag", "bausparsumme_teuro", "guthaben", "tariff_amount"
    };

    public final Path table;
    public final CsvReader.Layout layout;
    public final Profile profile = new Profile();
    public final List<String> declinedInputs = new ArrayList<>();   // R16/GR-08: nothing in silence
    public Book book;
    public Export export;
    public List<String> jsLines;
    public long rowsRead, recordsPublished, rowsRefused;

    private Map<String, Integer> colIndex;
    private Set<String> coerced;

    public Runner(Path table, CsvReader.Layout layout) { this.table = table; this.layout = layout; }

    // ------------------------------------------------------------------ pass 1

    public void profile(List<String> declaredCoercions) throws IOException {
        profile.header = layout.headerNames;
        colIndex = new HashMap<>();
        for (int i = 0; i < profile.header.length; i++) colIndex.put(profile.header[i], i);

        Set<String> required = new HashSet<>(List.of(REQUIRED_COLUMNS));
        for (String r : REQUIRED_COLUMNS) if (!colIndex.containsKey(r)) profile.absentRequired.add(r);
        for (String h : profile.header) if (!required.contains(h)) profile.surplusFields.add(h);
        // FND-12: prefix fallback is a hazard of the source's name lookup, not a behaviour to copy.
        for (String r : REQUIRED_COLUMNS)
            for (String h : profile.header)
                if (!h.equals(r) && h.startsWith(r)) profile.prefixCollisions.add(h + " has prefix " + r);

        coerced = new HashSet<>(declaredCoercions);
        for (String d : DATE_COLUMNS) {
            profile.dates.put(d, new Profile.DateField());
            if (coerced.contains(d)) profile.coercedColumns.add(d); else profile.rawDateColumns.add(d);
        }
        for (String a : AMOUNT_COLUMNS) profile.amounts.put(a, new Profile.AmountField());

        Map<String, Integer> idCounts = new HashMap<>();
        // The first non-missing element of each coerced column, and its row, for the coercion.
        Map<String, String> firstNonMissing = new HashMap<>();
        Map<String, Integer> firstNonMissingRow = new HashMap<>();

        try (CsvReader r = new CsvReader(table, layout.delimiter)) {
            String[] rec;
            boolean first = true;
            int rowIndex = 0;
            while ((rec = r.next()) != null) {
                if (first) { first = false; continue; }
                rowIndex++;
                profile.rows++;

                for (String d : DATE_COLUMNS) {
                    String raw = get(rec, d);
                    if (raw == null) continue;
                    String t = raw.trim();
                    Profile.DateField f = profile.dates.get(d);
                    if (DateValue.isMissingMarker(t)) {
                        f.missingMarker++;
                        f.markersSeen.add(t);
                        continue;
                    }
                    if (coerced.contains(d) && !firstNonMissing.containsKey(d)) {
                        firstNonMissing.put(d, t);
                        firstNonMissingRow.put(d, rowIndex);
                    }
                    long v;
                    if (t.indexOf('-') >= 0) {
                        v = DateValue.parseStandardUnambiguous(t);
                        if (v == DateValue.NA) { f.unreadable++; sample(f.unreadableSamples, rowIndex, d, t); continue; }
                        f.hyphenValid++;
                    } else {
                        v = DateValue.parseEightDigits(t);
                        if (v == DateValue.NA) { f.unreadable++; sample(f.unreadableSamples, rowIndex, d, t); continue; }
                        f.eightDigitValid++;
                    }
                    if (v < f.min) f.min = v;
                    if (v > f.max) f.max = v;
                }

                for (String a : AMOUNT_COLUMNS) {
                    String raw = get(rec, a);
                    if (raw == null) continue;
                    String t = raw.trim();
                    Profile.AmountField f = profile.amounts.get(a);
                    if (f.distinctRaw.size() < 64) f.distinctRaw.add(t);
                    int commas = count(t, ',');
                    if (commas >= 2) f.multiComma++;
                    if (commas == 0 && t.indexOf('.') >= 0) {
                        f.dotNoComma++;
                        // FND-01 precondition: at most two digits after the last dot.
                        int last = t.lastIndexOf('.');
                        if (t.length() - last - 1 > 2) { f.fnd01Suspects++; sample(f.suspectSamples, rowIndex, a, t); }
                    }
                    double v = GermanNumber.readText(t);
                    if (Double.isNaN(v)) { f.missing++; continue; }
                    if (f.distinctRead.size() < 64) f.distinctRead.add(CanonicalNumber.num(v));
                    if (v < 0) f.negative++;
                    if (v == 0.0) f.zeros++;
                    if (v > 1.0) f.gtOne++;
                    if (v <= 0.0) f.leZero++;
                    if (v < f.min) f.min = v;
                    if (v > f.max) f.max = v;
                }

                String ct = get(rec, "contract_type");
                if (ct != null && profile.contractTypes.size() < 64) profile.contractTypes.add(ct);

                String id = get(rec, "BSV");
                if (id != null) {
                    profile.idRows++;
                    idCounts.merge(id, 1, Integer::sum);
                    if (id.matches("^[+-]?[0-9]*\\.?[0-9]+[eE][+-]?[0-9]+$")) {
                        profile.exponentIdCount++;
                        if (profile.exponentIds.size() < 10) profile.exponentIds.add(id);
                    }
                }
            }
        }
        profile.idDistinct = idCounts.size();
        for (Map.Entry<String, Integer> e : idCounts.entrySet())
            if (e.getValue() > 1) { profile.idDuplicated++; if (profile.duplicatedIds.size() < 10) profile.duplicatedIds.add(e.getKey()); }

        // Settle the harness coercion, in the declared columns only, never inferred.
        for (String d : profile.coercedColumns) {
            String t = firstNonMissing.get(d);
            if (t == null) { profile.coercionSeparator.put(d, '-'); continue; }   // column all missing
            char sep;
            if (DateValue.parseSeparatedPublic(t, '-') != DateValue.NA) sep = '-';
            else if (DateValue.parseSeparatedPublic(t, '/') != DateValue.NA) sep = '/';
            else {
                throw new AbortException("DATE_PARSE_ABORT", firstNonMissingRow.get(d), d, t, 0,
                    "the harness date conversion of column '" + d + "' infers its format from the first "
                    + "non-missing element, and that element (row " + firstNonMissingRow.get(d)
                    + ", value '" + t + "') is not in a standard unambiguous format");
            }
            profile.coercionSeparator.put(d, sep);
        }
    }

    private static void sample(List<String> out, int row, String col, String value) {
        if (out.size() < 10) out.add("row " + row + " " + col + "='" + value + "'");
    }

    private static int count(String s, char c) {
        int n = 0;
        for (int i = 0; i < s.length(); i++) if (s.charAt(i) == c) n++;
        return n;
    }

    private String get(String[] rec, String name) {
        Integer i = colIndex.get(name);
        if (i == null || i >= rec.length) return null;
        return rec[i];
    }

    // ------------------------------------------------------------------ pass 2

    public void compute(long valuation) throws IOException {
        int cap = (int) Math.max(profile.rows, 1);
        book = new Book(cap);
        int i = 0;
        long progressEvery = Math.max(1, profile.rows / 10);
        try (CsvReader r = new CsvReader(table, layout.delimiter)) {
            String[] rec;
            boolean first = true;
            int rowIndex = 0;
            while ((rec = r.next()) != null) {
                if (first) { first = false; continue; }
                rowIndex++;
                rowsRead++;

                long abschluss = readDate(rec, "abschlussdatum", rowIndex, i);
                long einloesung = readDate(rec, "einloesungsdatum", rowIndex, i);
                long erstmalige = readDate(rec, "erstmalige_zuteilungsanwartschaft", rowIndex, i);
                long tilgung = readDate(rec, "Tilgungsbeginn", rowIndex, i);
                long vertragsende = readDate(rec, "Vertragsende", rowIndex, i);

                double daBetrag = readAmount(rec, "DaBetrag");
                double bausparsumme = readAmount(rec, "bausparsumme_teuro");
                double guthaben = readAmount(rec, "guthaben");
                double tariff = readAmount(rec, "tariff_amount");

                String ct = get(rec, "contract_type");     // C9: unchanged and UNTRIMMED
                String id = get(rec, "BSV");               // C19: text, used unchanged

                Engine.computeInto(book, i, rowIndex, id, abschluss, einloesung, erstmalige,
                        tilgung, vertragsende, daBetrag, bausparsumme, guthaben, tariff, ct, valuation);
                i++;
                recordsPublished++;
                if (profile.rows > 5000 && recordsPublished % progressEvery == 0) {
                    System.out.printf("  progress: %d / %d contracts (%d%%)%n",
                            recordsPublished, profile.rows, (100 * recordsPublished) / profile.rows);
                }
            }
        }
        book.n = i;
        export = new Export(book);
    }

    /**
     * Behaviour step C1 as it reaches the unit. A DECLARED harness-coerced column has
     * already been converted whole-column, so a value that does not match the inferred
     * format is silently missing here; an engine-parsed column takes C1's own branches,
     * and its hyphen branch aborts the whole run.
     */
    private long readDate(String[] rec, String col, int rowIndex, int rowsCompleted) {
        String raw = get(rec, col);
        if (raw == null) return DateValue.NA;
        if (coerced.contains(col)) {
            String t = raw.trim();
            if (DateValue.isMissingMarker(t)) return DateValue.NA;
            Character sep = profile.coercionSeparator.get(col);
            long v = DateValue.parseSeparatedPublic(t, sep == null ? '-' : sep);
            return v;                                   // not matching the column's format -> missing
        }
        DateValue.Read rd = DateValue.readText(raw);
        if (rd.fail == DateValue.Fail.ABORT) {
            throw new AbortException("DATE_PARSE_ABORT", rowIndex, col, raw.trim(), rowsCompleted,
                "character string is not in a standard unambiguous format: column '" + col
                + "' row " + rowIndex + " holds '" + raw.trim() + "', which contains a hyphen and is "
                + "therefore sent to the standard unambiguous parse, which rejects it");
        }
        return rd.epochDay;
    }

    private double readAmount(String[] rec, String col) {
        String raw = get(rec, col);
        if (raw == null) return Double.NaN;             // C8: an absent field is missing, not an error
        return GermanNumber.readText(raw);
    }

    // --------------------------------------------------------- browser document

    /** Behaviour step C24, split into physical lines (the checkpoint object). */
    public List<String> buildJsDocument(long valuation) {
        List<String> lines = new ArrayList<>(book.n + 4);
        lines.add("// customers_data.js  --  generated by customer_engine.R");
        lines.add("// " + book.n + " contracts, valuation date " + DateValue.isoOf(valuation));
        lines.add("window.CUSTOMERS = {");
        for (int i = 0; i < book.n; i++) {
            String entry = ScriptFormat.keyText(book.id[i] == null ? "" : book.id[i])
                         + ":" + export.renderRecord(i);
            lines.add(i < book.n - 1 ? entry + "," : entry);
        }
        lines.add("};");
        jsLines = lines;
        return lines;
    }
}
