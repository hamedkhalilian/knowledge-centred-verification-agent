package bauspar;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * Canonicalisation contract {@code dec9-half-even-v1}, section 1 (scalar rendering).
 *
 * <p>GR-11 gate: {@code BigDecimal} is allow-listed in THIS COMPILATION UNIT ONLY.
 * It is a serialisation device, never a computation device: every value that reaches
 * this class has already been computed in IEEE-754 {@code double}, exactly as the
 * source computes it. {@code build.sh} scans the tree and fails the build on any
 * other occurrence.
 *
 * <p>The contract requires rounding with respect to the EXACT decimal expansion of the
 * IEEE-754 binary value. {@code new BigDecimal(double)} -- the exact constructor -- is
 * the only Java route to that expansion. {@code BigDecimal.valueOf(double)} goes via
 * {@code Double.toString} (the shortest round-tripping decimal) and would round a
 * different number; {@code String.format} rounds HALF_UP. Both are wrong here.
 */
public final class CanonicalNumber {

    private CanonicalNumber() { }

    /** 9 significant digits, round half-even, on the exact binary expansion. */
    private static final MathContext MC9 = new MathContext(9, RoundingMode.HALF_EVEN);

    public static final String NA = "NA";
    public static final String ZERO = "0.00000000e+00";

    /** Sentinel for a missing date (the contract's date class renders it {@code NA}). */
    public static final long DATE_NA = Long.MIN_VALUE;

    /** finite double -> [-]d.dddddddde+XX ; zero and negative zero -> the POSITIVE form. */
    public static String num(double v) {
        if (Double.isNaN(v)) return NA;
        if (Double.isInfinite(v)) return v > 0 ? "INF" : "-INF";
        if (v == 0.0) return ZERO;                    // covers -0.0: contract says positive form
        boolean neg = v < 0.0;
        BigDecimal bd = new BigDecimal(Math.abs(v)).round(MC9);
        String digits = bd.unscaledValue().toString();
        int exp = digits.length() - bd.scale() - 1;   // normalised decimal exponent
        if (digits.length() < 9) {
            digits = digits + "0".repeat(9 - digits.length());
        } else if (digits.length() > 9) {
            // unreachable after round(MC9); kept so a future change cannot fail silently.
            throw new IllegalStateException("canonical: " + digits.length() + " digits after MC9");
        }
        StringBuilder sb = new StringBuilder(18);
        if (neg) sb.append('-');
        sb.append(digits.charAt(0)).append('.').append(digits, 1, 9).append('e');
        sb.append(exp < 0 ? '-' : '+');
        String e = Integer.toString(Math.abs(exp));
        if (e.length() < 2) sb.append('0');
        sb.append(e);
        return sb.toString();
    }

    /** logical -> true / false / NA. */
    public static String bool(Boolean b) {
        return b == null ? NA : (b ? "true" : "false");
    }

    /** date -> epoch days since 1970-01-01 as decimal integer text; NA if missing. */
    public static String date(long epochDay) {
        return epochDay == DATE_NA ? NA : Long.toString(epochDay);
    }

    /** string/factor label -> UTF-8 text with exactly three escapes; missing -> NA. */
    public static String str(String s) {
        if (s == null) return NA;
        StringBuilder sb = new StringBuilder(s.length() + 8);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                default -> sb.append(c);
            }
        }
        return sb.toString();
    }

    /** The contract's reference vectors. Self-tested at startup; see SelfTest. */
    public static String[][] referenceVectors() {
        return new String[][] {
            { "1",            num(1.0),                     "1.00000000e+00" },
            { "-0.0",         num(-0.0),                    "0.00000000e+00" },
            { "2^-13",        num(Math.scalb(1.0, -13)),    "1.22070312e-04" },
            { "1/3",          num(1.0 / 3.0),               "3.33333333e-01" },
            { "123456789.5",  num(123456789.5),             "1.23456790e+08" },
            { "-2.5e-10",     num(-2.5e-10),                "-2.50000000e-10" },
            { "NaN",          num(Double.NaN),              "NA" },
            { "NA(date)",     date(DATE_NA),                "NA" },
            { "+Inf",         num(Double.POSITIVE_INFINITY),"INF" },
            { "-Inf",         num(Double.NEGATIVE_INFINITY),"-INF" },
            { "logical NA",   bool(null),                   "NA" },
            { "logical true", bool(Boolean.TRUE),           "true" },
            { "logical false",bool(Boolean.FALSE),          "false" },
            { "string NA",    str(null),                    "NA" },
            { "string esc",   str("a\\b\nc\rd"),            "a\\\\b\\nc\\rd" },
            { "epoch 0",      date(0L),                     "0" },
        };
    }
}
