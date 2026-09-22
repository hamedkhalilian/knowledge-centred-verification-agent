package bauspar;

import java.math.BigInteger;

/**
 * Behaviour step C20 -- the rounding rule that governs every rounded field of the
 * published record. It is NOT Math.round, and it is NOT multiply-round-divide.
 *
 * <p>To round a finite value to d decimal places: work on the magnitude and put the
 * sign back at the end (so a negative value that rounds to zero yields NEGATIVE
 * ZERO); let k be the largest integer not greater than magnitude times ten-to-the-d,
 * evaluated EXACTLY on the binary value held; form the two candidates as the binary
 * values nearest the decimals k/10^d and (k+1)/10^d; compare the EXACT distances
 * from the magnitude to each candidate and take the nearer; on an exact tie take the
 * candidate whose numerator is even. Missing or non-finite is returned unchanged.
 *
 * <p>The separating cases are in the spec's round_reference_vectors: 0.0055 at 3
 * places gives 0.005 here and 0.006 under multiply-round-divide. All sixteen are
 * re-checked at startup (SelfTest); the build may not emit a rounded field until
 * they pass.
 */
final class Rounding {

    private Rounding() { }

    private static final BigInteger[] POW10 = new BigInteger[19];
    static {
        for (int i = 0; i < POW10.length; i++) POW10[i] = BigInteger.TEN.pow(i);
    }

    static double round(double v, int places) {
        if (Double.isNaN(v) || Double.isInfinite(v)) return v;
        boolean neg = (Double.doubleToRawLongBits(v) < 0L);   // captures -0.0 too
        double m = Math.abs(v);
        if (m == 0.0) return v;

        // k = floor(m * 10^places), exactly.  m = mant * 2^exp.
        BigInteger num = Exact.mantissa(m).multiply(POW10[places]);
        int exp = Exact.exponent(m);
        BigInteger k = (exp >= 0) ? num.shiftLeft(exp) : num.shiftRight(-exp);

        double c1 = Double.parseDouble(Exact.decimalText(k, places));
        double c2 = Double.parseDouble(Exact.decimalText(k.add(BigInteger.ONE), places));

        int cmp = Exact.compareDistances(m, c1, c2);
        double r;
        if (cmp < 0)      r = c1;
        else if (cmp > 0) r = c2;
        else              r = k.testBit(0) ? c2 : c1;   // tie -> even numerator

        return neg ? -r : r;
    }

    /**
     * The sixteen measured reference vectors of the constant round_reference_vectors,
     * carried verbatim. Each entry is {value, places, expected}.
     */
    static final String[][] REFERENCE_VECTORS = {
        { "0.1235",      "3", "0.124"     },
        { "0.0055",      "3", "0.005"     },
        { "0.0095",      "3", "0.01"      },
        { "0.0085",      "3", "0.009"     },
        { "0.0005",      "3", "0"         },
        { "0.0625",      "3", "0.062"     },
        { "0.1875",      "3", "0.188"     },
        { "0.4445",      "3", "0.444"     },
        { "-0.0055",     "3", "-0.005"    },
        { "0.12345",     "4", "0.1235"    },
        { "0.5",         "0", "0"         },
        { "1.5",         "0", "2"         },
        { "2.5",         "0", "2"         },
        { "14500.5",     "0", "14500"     },
        { "14501.5",     "0", "14502"     },
        { "123456789.5", "0", "123456790" },
    };
}
