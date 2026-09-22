package bauspar;

import java.math.BigInteger;

/**
 * Exact arithmetic on the binary value of a double, using BigInteger only.
 *
 * <p>Two rules in the specification are stated "on the EXACT binary value": the
 * record rounding rule (behaviour step C20) and the browser-file fixed-format
 * conversion (behaviour step C22). Both need the exact value of an IEEE-754
 * double, and neither may use BigDecimal -- that is reserved by the GR-11 gate for
 * the canonical serialiser. A double is exactly {@code mantissa * 2^exponent} with
 * an integral mantissa, so BigInteger is sufficient and exact.
 */
final class Exact {

    private Exact() { }

    /** mantissa (>= 0) such that |x| == mantissa * 2^exponent, exactly. */
    static BigInteger mantissa(double x) {
        long bits = Double.doubleToLongBits(Math.abs(x));
        int be = (int) ((bits >>> 52) & 0x7FFL);
        long frac = bits & 0x000FFFFFFFFFFFFFL;
        return BigInteger.valueOf(be == 0 ? frac : (frac | 0x0010000000000000L));
    }

    /** exponent such that |x| == mantissa * 2^exponent, exactly. */
    static int exponent(double x) {
        long bits = Double.doubleToLongBits(Math.abs(x));
        int be = (int) ((bits >>> 52) & 0x7FFL);
        return be == 0 ? -1074 : be - 1075;
    }

    /** k as a plain decimal with {@code places} digits after the point (k &gt;= 0). */
    static String decimalText(BigInteger k, int places) {
        String s = k.toString();
        if (places == 0) return s;
        if (s.length() <= places) {
            s = "0".repeat(places - s.length() + 1) + s;
        }
        return s.substring(0, s.length() - places) + "." + s.substring(s.length() - places);
    }

    /**
     * Sign of |m - a| - |m - b|, computed exactly. All three are finite doubles.
     * Negative: a is nearer. Positive: b is nearer. Zero: exactly equidistant.
     */
    static int compareDistances(double m, double a, double b) {
        int e = Math.min(exponent(m), Math.min(exponent(a), exponent(b)));
        BigInteger M = mantissa(m).shiftLeft(exponent(m) - e);
        BigInteger A = mantissa(a).shiftLeft(exponent(a) - e);
        BigInteger B = mantissa(b).shiftLeft(exponent(b) - e);
        return M.subtract(A).abs().compareTo(M.subtract(B).abs());
    }
}
