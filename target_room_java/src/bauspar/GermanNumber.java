package bauspar;

/**
 * Behaviour step C2 -- the number reading rule, reproduced including finding FND-01.
 *
 * <p>If the text contains a comma, EVERY dot is deleted first (they are thousands
 * separators) and the comma becomes the decimal point. If the text contains no comma
 * it is read as written, so a dot in it is a decimal point -- which is why 36.263
 * reads as 36.263 and not as 36263. That is FND-01 and it is reproduced, not repaired.
 */
public final class GermanNumber {

    private GermanNumber() { }

    /** Constant amount_missing_markers -- they apply only to TEXT; a numeric zero is a zero. */
    public static final String[] MISSING_MARKERS = { "", "NA", "<NA>", "n/a", "-" };

    public static boolean isMissingMarker(String trimmed) {
        for (String m : MISSING_MARKERS) if (m.equals(trimmed)) return true;
        return false;
    }

    public static double readText(String raw) {
        if (raw == null) return Double.NaN;
        String t = raw.trim();
        if (isMissingMarker(t)) return Double.NaN;
        if (t.indexOf(',') >= 0) {
            StringBuilder sb = new StringBuilder(t.length());
            for (int i = 0; i < t.length(); i++) {
                char c = t.charAt(i);
                if (c == '.') continue;          // thousands separator
                sb.append(c == ',' ? '.' : c);   // decimal comma
            }
            t = sb.toString();
        }
        return strictNumeric(t);
    }

    /**
     * Whole-string numeric conversion; anything that is not a plain decimal or
     * scientific literal becomes missing, SILENTLY (C2's last clause). Java's
     * Double.parseDouble would additionally accept "1d", "0x1p3", "Infinity" and
     * leading/trailing whitespace, so the shape is checked first.
     */
    private static double strictNumeric(String t) {
        int i = 0, n = t.length();
        if (n == 0) return Double.NaN;
        if (t.charAt(i) == '+' || t.charAt(i) == '-') i++;
        int intDigits = 0, fracDigits = 0;
        while (i < n && isDigit(t.charAt(i))) { i++; intDigits++; }
        if (i < n && t.charAt(i) == '.') {
            i++;
            while (i < n && isDigit(t.charAt(i))) { i++; fracDigits++; }
        }
        if (intDigits + fracDigits == 0) return Double.NaN;
        if (i < n && (t.charAt(i) == 'e' || t.charAt(i) == 'E')) {
            i++;
            if (i < n && (t.charAt(i) == '+' || t.charAt(i) == '-')) i++;
            int expDigits = 0;
            while (i < n && isDigit(t.charAt(i))) { i++; expDigits++; }
            if (expDigits == 0) return Double.NaN;
        }
        if (i != n) return Double.NaN;
        return Double.parseDouble(t);
    }

    private static boolean isDigit(char c) { return c >= '0' && c <= '9'; }
}
