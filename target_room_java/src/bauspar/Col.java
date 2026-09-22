package bauspar;

import java.nio.charset.StandardCharsets;

/** One canonical column of a checkpoint object (canonicalisation contract, section 2). */
public abstract class Col {

    public final String name;
    protected final int n;

    protected Col(String name, int n) { this.name = name; this.n = n; }

    public int size() { return n; }

    /** Canonical text of row i (in the object's ORIGINAL order; sorting is applied by the caller). */
    public abstract String canon(int i);

    /** True when this column holds numeric cells, for the coverage min/max. */
    public boolean numeric() { return false; }

    /** Numeric value of row i; only meaningful when {@link #numeric()}. */
    public double value(int i) { return Double.NaN; }

    /** True when row i renders as NA, for the coverage null_count. */
    public abstract boolean isNA(int i);

    /** Sort key comparison for the canonical order; NA sorts LAST regardless of direction. */
    public abstract int compareRows(int a, int b);

    // ------------------------------------------------------------- implementations

    public static final class Num extends Col {
        private final double[] v;
        public Num(String name, double[] v, int n) { super(name, n); this.v = v; }
        @Override public String canon(int i) { return CanonicalNumber.num(v[i]); }
        @Override public boolean numeric() { return true; }
        @Override public double value(int i) { return v[i]; }
        @Override public boolean isNA(int i) { return Double.isNaN(v[i]); }
        @Override public int compareRows(int a, int b) {
            boolean na = Double.isNaN(v[a]), nb = Double.isNaN(v[b]);
            if (na || nb) return na && nb ? 0 : (na ? 1 : -1);   // NA last
            return Double.compare(v[a], v[b]);
        }
    }

    public static final class Int extends Col {
        private final int[] v;
        public Int(String name, int[] v, int n) { super(name, n); this.v = v; }
        @Override public String canon(int i) { return CanonicalNumber.num(v[i]); }
        @Override public boolean numeric() { return true; }
        @Override public double value(int i) { return v[i]; }
        @Override public boolean isNA(int i) { return false; }
        @Override public int compareRows(int a, int b) { return Integer.compare(v[a], v[b]); }
    }

    public static final class Bool extends Col {
        private final boolean[] v;
        public Bool(String name, boolean[] v, int n) { super(name, n); this.v = v; }
        @Override public String canon(int i) { return CanonicalNumber.bool(v[i]); }
        @Override public boolean isNA(int i) { return false; }
        @Override public int compareRows(int a, int b) { return Boolean.compare(v[a], v[b]); }
    }

    public static final class Date extends Col {
        private final long[] v;
        public Date(String name, long[] v, int n) { super(name, n); this.v = v; }
        @Override public String canon(int i) { return CanonicalNumber.date(v[i]); }
        @Override public boolean isNA(int i) { return v[i] == DateValue.NA; }
        @Override public int compareRows(int a, int b) {
            boolean na = isNA(a), nb = isNA(b);
            if (na || nb) return na && nb ? 0 : (na ? 1 : -1);
            return Long.compare(v[a], v[b]);
        }
    }

    public static final class Str extends Col {
        private final String[] v;
        public Str(String name, String[] v, int n) { super(name, n); this.v = v; }
        @Override public String canon(int i) { return CanonicalNumber.str(v[i]); }
        @Override public boolean isNA(int i) { return v[i] == null; }
        @Override public int compareRows(int a, int b) {
            String x = v[a], y = v[b];
            if (x == null || y == null) return (x == null && y == null) ? 0 : (x == null ? 1 : -1);
            return compareUtf8(x, y);
        }
    }

    /** Strings compare BYTEWISE as UTF-8 (canonicalisation contract, section 2). */
    public static int compareUtf8(String x, String y) {
        byte[] a = x.getBytes(StandardCharsets.UTF_8);
        byte[] b = y.getBytes(StandardCharsets.UTF_8);
        int m = Math.min(a.length, b.length);
        for (int i = 0; i < m; i++) {
            int d = (a[i] & 0xFF) - (b[i] & 0xFF);
            if (d != 0) return d;
        }
        return Integer.compare(a.length, b.length);
    }
}
