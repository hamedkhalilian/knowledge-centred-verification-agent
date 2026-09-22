package bauspar;

import java.time.DateTimeException;
import java.time.LocalDate;

/**
 * Behaviour step C1 -- the date reading rule, reproduced including finding FND-06.
 *
 * <p>Dates are carried as epoch days (R11: dates as epoch day numbers), with
 * {@link CanonicalNumber#DATE_NA} for missing.
 */
public final class DateValue {

    private DateValue() { }

    public static final long NA = CanonicalNumber.DATE_NA;

    /** Constant date_missing_markers -- the SEVEN texts the code recognises (FND-11). */
    public static final String[] MISSING_MARKERS = { "", "0", "00", "0000", "00000000", "NA", "<NA>" };

    public static boolean isMissingMarker(String trimmed) {
        for (String m : MISSING_MARKERS) if (m.equals(trimmed)) return true;
        return false;
    }

    /** Outcome of a text read that did not produce a date. */
    public enum Fail { NONE, SILENT_MISSING, ABORT }

    /** A read result: the date (or NA) plus how it failed, so the caller can apply C1's asymmetry. */
    public static final class Read {
        public final long epochDay;
        public final Fail fail;
        Read(long epochDay, Fail fail) { this.epochDay = epochDay; this.fail = fail; }
    }

    public static final Read MISSING = new Read(NA, Fail.NONE);

    /**
     * C1 applied to raw text. Returns a Read; an ABORT result is raised by the caller,
     * which knows the row index and the column name (R14: the explanation is derived
     * at the point of the finding).
     */
    public static Read readText(String raw) {
        if (raw == null) return MISSING;
        String t = raw.trim();
        if (isMissingMarker(t)) return MISSING;
        if (t.indexOf('-') >= 0) {
            long d = parseStandardUnambiguous(t);
            // "a value that cannot be read that way RAISES AN ERROR that stops the whole run"
            return d == NA ? new Read(NA, Fail.ABORT) : new Read(d, Fail.NONE);
        }
        long d = parseEightDigits(t);
        // "a value that cannot be read that way becomes missing without any message"
        return d == NA ? new Read(NA, Fail.SILENT_MISSING) : new Read(d, Fail.NONE);
    }

    /**
     * The "standard unambiguous format": year-month-day with hyphen or slash separators.
     * Trailing text after a complete match is ignored, as the measured behaviour requires.
     * A two-digit year is a YEAR, not a century (measured: 11-04-01 reads as year eleven).
     */
    public static long parseStandardUnambiguous(String t) {
        long d = parseSeparated(t, '-');
        if (d != NA) return d;
        return parseSeparated(t, '/');
    }

    /** Exposed for the harness coercion, which applies ONE inferred format to a whole column. */
    public static long parseSeparatedPublic(String t, char sep) { return parseSeparated(t, sep); }

    private static long parseSeparated(String t, char sep) {
        int[] p = { 0 };
        int y = digits(t, p, 4);
        if (y < 0) return NA;
        if (p[0] >= t.length() || t.charAt(p[0]) != sep) return NA;
        p[0]++;
        int m = digits(t, p, 2);
        if (m < 0) return NA;
        if (p[0] >= t.length() || t.charAt(p[0]) != sep) return NA;
        p[0]++;
        int dd = digits(t, p, 2);
        if (dd < 0) return NA;
        return toEpochDay(y, m, dd);       // trailing text ignored
    }

    /**
     * The eight-digit branch. NOT width-checked, exactly as measured: the reader takes
     * up to four digits as the year, up to two as the month and up to two as the day,
     * and ignores whatever follows. So 20110401.0 reads as 2011-04-01 and 2013112 reads
     * as 2013-11-02 rather than being rejected (FND-06).
     */
    public static long parseEightDigits(String t) {
        int[] p = { 0 };
        int y = digits(t, p, 4);
        if (y < 0) return NA;
        int m = digits(t, p, 2);
        if (m < 0) return NA;
        int d = digits(t, p, 2);
        if (d < 0) return NA;
        return toEpochDay(y, m, d);
    }

    /** Reads 1..max decimal digits greedily; -1 when none are available. */
    private static int digits(String t, int[] pos, int max) {
        int i = pos[0], n = 0, v = 0;
        while (i < t.length() && n < max) {
            char c = t.charAt(i);
            if (c < '0' || c > '9') break;
            v = v * 10 + (c - '0');
            i++; n++;
        }
        if (n == 0) return -1;
        pos[0] = i;
        return v;
    }

    public static long toEpochDay(int y, int m, int d) {
        try {
            return LocalDate.of(y, m, d).toEpochDay();
        } catch (DateTimeException e) {
            return NA;
        }
    }

    public static long fromIso(String iso) {
        return LocalDate.parse(iso).toEpochDay();
    }

    public static String isoOf(long epochDay) {
        return LocalDate.ofEpochDay(epochDay).toString();
    }

    /** Four-digit calendar year label, or the empty text when the date is missing (C18). */
    public static String yearLabel(long epochDay) {
        if (epochDay == NA) return "";
        int y = LocalDate.ofEpochDay(epochDay).getYear();
        return (y >= 0 && y <= 9999) ? String.format("%04d", y) : Integer.toString(y);
    }

    /** Whole-day count from a to b; NaN when either is missing. */
    public static double daysBetween(long a, long b) {
        if (a == NA || b == NA) return Double.NaN;
        return (double) (b - a);
    }
}
