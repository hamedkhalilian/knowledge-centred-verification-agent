package bauspar;

import java.math.BigInteger;

/**
 * Behaviour step C22 -- the SECOND rounding rule, the one that governs the browser
 * data file. Plain fixed notation with exactly six digits after the decimal point,
 * rounding HALF TO EVEN on the exact binary value (the ordinary C fixed-format
 * conversion), after which trailing zeros and then a trailing decimal point are
 * removed.
 *
 * <p>This is NOT the rule of C20, and the spec's own notes say an implementation that
 * uses one rule for both will diverge. Java's String.format("%.6f") rounds HALF_UP,
 * so it cannot be used.
 */
final class ScriptFormat {

    private ScriptFormat() { }

    private static final int PLACES = 6;
    private static final BigInteger P6 = BigInteger.TEN.pow(PLACES);

    /** A numeric value rendered for the browser data file. Non-finite -> null literal. */
    static String number(double v) {
        if (Double.isNaN(v) || Double.isInfinite(v)) return "null";
        boolean neg = (Double.doubleToRawLongBits(v) < 0L);   // -0.0 renders as -0
        double m = Math.abs(v);

        BigInteger q;
        if (m == 0.0) {
            q = BigInteger.ZERO;
        } else {
            BigInteger num = Exact.mantissa(m).multiply(P6);   // m*10^6 == num * 2^exp
            int exp = Exact.exponent(m);
            if (exp >= 0) {
                q = num.shiftLeft(exp);
            } else {
                int sh = -exp;
                q = num.shiftRight(sh);
                BigInteger rem = num.subtract(q.shiftLeft(sh));       // 0 <= rem < 2^sh
                int c = rem.shiftLeft(1).compareTo(BigInteger.ONE.shiftLeft(sh));
                if (c > 0 || (c == 0 && q.testBit(0))) q = q.add(BigInteger.ONE);
            }
        }

        String digits = q.toString();
        if (digits.length() <= PLACES) digits = "0".repeat(PLACES - digits.length() + 1) + digits;
        String ip = digits.substring(0, digits.length() - PLACES);
        String fp = digits.substring(digits.length() - PLACES);

        int end = fp.length();
        while (end > 0 && fp.charAt(end - 1) == '0') end--;
        fp = fp.substring(0, end);

        StringBuilder sb = new StringBuilder(24);
        if (neg) sb.append('-');
        sb.append(ip);
        if (!fp.isEmpty()) sb.append('.').append(fp);
        return sb.toString();
    }

    /** A text value rendered for the browser data file: backslash doubled, quote escaped. */
    static String text(String s) {
        StringBuilder sb = new StringBuilder(s.length() + 8);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\') sb.append("\\\\");
            else if (c == '"') sb.append("\\\"");
            else sb.append(c);
        }
        sb.append('"');
        return sb.toString();
    }

    /**
     * Behaviour step C24: the entry KEY escaping, which differs from C22 --
     * a double quote is escaped, a BACKSLASH IS NOT. Reproduced as measured.
     */
    static String keyText(String id) {
        StringBuilder sb = new StringBuilder(id.length() + 4);
        sb.append('"');
        for (int i = 0; i < id.length(); i++) {
            char c = id.charAt(i);
            if (c == '"') sb.append("\\\"");
            else sb.append(c);
        }
        sb.append('"');
        return sb.toString();
    }
}
