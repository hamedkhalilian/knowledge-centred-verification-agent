package bauspar;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * A streaming delimited-text reader that parses quoted fields properly.
 *
 * <p>GR-09/R11: the file is streamed, never held. The staged stand-in is 503 rows;
 * production is 45,881. Nothing here materialises the table.
 *
 * <p>The spec records (observed_in_synthetic_input) that a reader which splits the
 * line on the delimiter instead of parsing quoted fields sees 14 or 15 fields on the
 * rows whose amounts are written in German decimal-comma style, and mis-assigns every
 * field after the first amount, silently. That is carried across as a hazard to
 * VERIFY (R7), and {@link Layout} measures it rather than assuming it.
 */
public final class CsvReader implements AutoCloseable {

    private final Reader in;
    private final char delim;
    private int pending = -2;          // -2 = nothing pushed back
    private boolean eof;
    private long records;

    public CsvReader(Path p, char delim) throws IOException {
        this.delim = delim;
        InputStream raw = Files.newInputStream(p);
        var dec = StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT);
        this.in = new BufferedReader(new InputStreamReader(raw, dec), 1 << 16);
    }

    private int read() throws IOException {
        if (pending != -2) { int c = pending; pending = -2; return c; }
        return in.read();
    }

    private void push(int c) { pending = c; }

    /** The next record, or null at end of input. Never returns an empty trailing record. */
    public String[] next() throws IOException {
        if (eof) return null;
        List<String> fields = new ArrayList<>(16);
        StringBuilder f = new StringBuilder(32);
        boolean any = false;
        boolean quoted = false;
        while (true) {
            int c = read();
            if (c == -1) {
                eof = true;
                if (!any && f.length() == 0 && fields.isEmpty()) return null;
                fields.add(f.toString());
                records++;
                return fields.toArray(new String[0]);
            }
            any = true;
            char ch = (char) c;
            if (quoted) {
                if (ch == '"') {
                    int n = read();
                    if (n == '"') { f.append('"'); }
                    else { quoted = false; if (n != -1) push(n); }
                } else {
                    f.append(ch);
                }
                continue;
            }
            if (ch == '"' && f.length() == 0) { quoted = true; continue; }
            if (ch == delim) { fields.add(f.toString()); f.setLength(0); continue; }
            if (ch == '\r') {
                int n = read();
                if (n != '\n' && n != -1) push(n);
                fields.add(f.toString());
                records++;
                return fields.toArray(new String[0]);
            }
            if (ch == '\n') {
                fields.add(f.toString());
                records++;
                return fields.toArray(new String[0]);
            }
            f.append(ch);
        }
    }

    public long records() { return records; }

    @Override public void close() throws IOException { in.close(); }

    // ------------------------------------------------------------------ layout

    /** A content-based layout reading with its margins (R5/GR-07). */
    public static final class Layout {
        public String encoding;
        public char delimiter;
        public int delimiterScore;
        public int delimiterRunnerUpScore;
        public char delimiterRunnerUp;
        public int delimiterMargin;
        public int headerRow;                 // 1-based; 0 means "no header found"
        public int headerScore;
        public int headerRunnerUpScore;
        public int headerMargin;
        public String[] headerNames = new String[0];
        public int fieldCount;
        public long dataRecords;
        public long raggedRecords;            // records whose field count != header field count
        public long naiveSplitDisagreements;  // records where splitting on the delimiter mis-counts
        public boolean bom;
        public final List<String> notes = new ArrayList<>();

        public String note() {
            return "delimiter '" + delimiter + "' [score " + delimiterScore + " vs '"
                 + delimiterRunnerUp + "' " + delimiterRunnerUpScore + ", margin " + delimiterMargin
                 + "]; header on row " + headerRow + " [score " + headerScore + " vs "
                 + headerRunnerUpScore + ", margin " + headerMargin + "]; " + fieldCount
                 + " fields; " + dataRecords + " data records";
        }
    }

    /** The declared minimum margin below which a layout reading is AMBIGUOUS (R5). */
    public static final int MIN_MARGIN = 3;

    private static final char[] DELIM_CANDIDATES = { ',', ';', '\t', '|' };

    public static Layout detect(Path p) throws IOException {
        Layout L = new Layout();

        byte[] head = readHead(p, 4);
        L.bom = head.length >= 3 && (head[0] & 0xFF) == 0xEF && (head[1] & 0xFF) == 0xBB && (head[2] & 0xFF) == 0xBF;

        // Encoding is PROBED, not asked (R17): decode the whole file strictly as UTF-8.
        try {
            StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(java.nio.ByteBuffer.wrap(Files.readAllBytes(p)));
            L.encoding = "UTF-8";
        } catch (CharacterCodingException e) {
            L.encoding = "NOT-UTF-8";
            L.notes.add("bytes do not decode as UTF-8: " + e.getMessage());
        }

        // Delimiter by content: how consistent is the field count under each candidate?
        int best = -1, bestScore = -1, secondScore = -1, second = -1;
        for (int i = 0; i < DELIM_CANDIDATES.length; i++) {
            int score = delimiterScore(p, DELIM_CANDIDATES[i]);
            if (score > bestScore) { secondScore = bestScore; second = best; bestScore = score; best = i; }
            else if (score > secondScore) { secondScore = score; second = i; }
        }
        L.delimiter = DELIM_CANDIDATES[best];
        L.delimiterScore = bestScore;
        L.delimiterRunnerUp = second >= 0 ? DELIM_CANDIDATES[second] : '?';
        L.delimiterRunnerUpScore = Math.max(secondScore, 0);
        L.delimiterMargin = L.delimiterScore - L.delimiterRunnerUpScore;

        // Header by content: label-likeness of the first record against the second.
        String[] r0 = null, r1 = null;
        try (CsvReader r = new CsvReader(p, L.delimiter)) {
            r0 = r.next();
            r1 = r.next();
        }
        if (r0 != null) {
            L.headerScore = headerScore(r0);
            L.headerRunnerUpScore = r1 == null ? 0 : headerScore(r1);
            L.headerMargin = L.headerScore - L.headerRunnerUpScore;
            L.headerRow = L.headerMargin >= MIN_MARGIN ? 1 : 0;
            L.headerNames = stripBom(r0);
            L.fieldCount = r0.length;
        }

        // Record shape and the naive-split hazard, measured.
        try (CsvReader r = new CsvReader(p, L.delimiter)) {
            String[] rec;
            boolean first = true;
            while ((rec = r.next()) != null) {
                if (first) { first = false; continue; }   // header
                L.dataRecords++;
                if (rec.length != L.fieldCount) L.raggedRecords++;
            }
        }
        L.naiveSplitDisagreements = naiveSplitDisagreements(p, L.delimiter, L.fieldCount);
        return L;
    }

    private static String[] stripBom(String[] r) {
        if (r.length > 0 && !r[0].isEmpty() && r[0].charAt(0) == '﻿') r[0] = r[0].substring(1);
        return r;
    }

    private static byte[] readHead(Path p, int n) throws IOException {
        try (InputStream s = Files.newInputStream(p)) {
            byte[] b = new byte[n];
            int got = s.readNBytes(b, 0, n);
            byte[] out = new byte[got];
            System.arraycopy(b, 0, out, 0, got);
            return out;
        }
    }

    private static int delimiterScore(Path p, char d) throws IOException {
        int consistent = 0, want = -1, seen = 0;
        try (CsvReader r = new CsvReader(p, d)) {
            String[] rec;
            while ((rec = r.next()) != null && seen < 200) {
                if (want < 0) want = rec.length;
                if (rec.length == want) consistent++;
                seen++;
            }
        }
        if (want <= 1) return 0;                  // the delimiter never occurs
        return consistent * (want - 1);
    }

    private static long naiveSplitDisagreements(Path p, char d, int fieldCount) throws IOException {
        long n = 0;
        try (BufferedReader br = Files.newBufferedReader(p, StandardCharsets.UTF_8)) {
            String line;
            boolean first = true;
            while ((line = br.readLine()) != null) {
                if (first) { first = false; continue; }
                if (line.isEmpty()) continue;
                int count = 1;
                for (int i = 0; i < line.length(); i++) if (line.charAt(i) == d) count++;
                if (count != fieldCount) n++;
            }
        }
        return n;
    }

    /** Label-likeness: non-blank fields that are neither numbers nor dates, plus distinctness. */
    private static int headerScore(String[] rec) {
        int labelish = 0;
        for (String f : rec) {
            String t = f.trim();
            if (t.isEmpty()) continue;
            if (!Double.isNaN(GermanNumber.readText(t))) continue;             // reads as a number
            if (DateValue.readText(t).epochDay != DateValue.NA) continue;      // reads as a date
            if (DateValue.parseStandardUnambiguous(t) != DateValue.NA) continue;
            labelish++;
        }
        boolean distinct = true;
        for (int i = 0; i < rec.length && distinct; i++)
            for (int j = i + 1; j < rec.length; j++)
                if (rec[i].equals(rec[j])) { distinct = false; break; }
        return labelish + (distinct ? rec.length : 0);
    }
}
