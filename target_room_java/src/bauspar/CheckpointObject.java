package bauspar;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;

/**
 * One checkpoint object under canonicalisation {@code dec9-half-even-v1}:
 * canonical sort, column digests in DECLARED spec order, object digest, the three
 * probes of section 5 and the five coverage fields of section 6 (all five always
 * present -- an absent field and a tracked zero are different claims, R12).
 */
public final class CheckpointObject {

    public final String name;
    public final String kind;
    public final List<Col> cols = new ArrayList<>();
    public final List<String[]> canonicalOrder = new ArrayList<>();   // {column, direction}
    private int[] order;                                              // canonical row permutation

    public CheckpointObject(String name, String kind) { this.name = name; this.kind = kind; }

    public CheckpointObject add(Col c) { cols.add(c); return this; }

    public CheckpointObject orderBy(String column, String direction) {
        canonicalOrder.add(new String[] { column, direction });
        return this;
    }

    public int rows() { return cols.isEmpty() ? 0 : cols.get(0).size(); }

    /** Stable sort by the declared canonical order; NA sorts last regardless of direction. */
    public void sort() {
        int n = rows();
        order = new int[n];
        for (int i = 0; i < n; i++) order[i] = i;
        final Col[] keys = new Col[canonicalOrder.size()];
        final int[] dir = new int[canonicalOrder.size()];
        for (int k = 0; k < keys.length; k++) {
            String cn = canonicalOrder.get(k)[0];
            Col found = null;
            for (Col c : cols) if (c.name.equals(cn)) { found = c; break; }
            if (found == null) throw new IllegalStateException(
                    "canonical_order names column '" + cn + "' which " + name + " does not carry");
            keys[k] = found;
            dir[k] = "desc".equals(canonicalOrder.get(k)[1]) ? -1 : 1;
        }
        mergeSort(order, new int[n], 0, n, (a, b) -> {
            for (int k = 0; k < keys.length; k++) {
                boolean na = keys[k].isNA(a), nb = keys[k].isNA(b);
                if (na || nb) {                          // NA last, whatever the direction
                    if (na && nb) continue;
                    return na ? 1 : -1;
                }
                int c = keys[k].compareRows(a, b) * dir[k];
                if (c != 0) return c;
            }
            return 0;
        });
    }

    private interface RowCmp { int cmp(int a, int b); }

    private static void mergeSort(int[] a, int[] tmp, int lo, int hi, RowCmp c) {
        if (hi - lo < 2) return;
        int mid = (lo + hi) >>> 1;
        mergeSort(a, tmp, lo, mid, c);
        mergeSort(a, tmp, mid, hi, c);
        int i = lo, j = mid, k = lo;
        while (i < mid && j < hi) tmp[k++] = (c.cmp(a[j], a[i]) < 0) ? a[j++] : a[i++];   // stable
        while (i < mid) tmp[k++] = a[i++];
        while (j < hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, lo, a, lo, hi - lo);
    }

    public int[] order() { if (order == null) sort(); return order; }

    // --------------------------------------------------------------- digesting

    private static MessageDigest sha256() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }

    private static void upd(MessageDigest md, String s) { md.update(s.getBytes(StandardCharsets.UTF_8)); }

    public static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) sb.append(Character.forDigit((x >> 4) & 0xF, 16)).append(Character.forDigit(x & 0xF, 16));
        return sb.toString();
    }

    public String columnDigest(Col c) {
        int[] o = order();
        MessageDigest md = sha256();
        upd(md, "col");
        upd(md, "\n"); upd(md, c.name);
        upd(md, "\n"); upd(md, Integer.toString(o.length));
        for (int idx : o) { upd(md, "\n"); upd(md, c.canon(idx)); }
        return hex(md.digest());
    }

    public String objectDigest() {
        MessageDigest md = sha256();
        upd(md, "obj");
        upd(md, "\n"); upd(md, kind);
        upd(md, "\n"); upd(md, Integer.toString(rows()));
        upd(md, "\n"); upd(md, Integer.toString(cols.size()));
        for (Col c : cols) {                       // DECLARED spec order, not alphabetical
            upd(md, "\n"); upd(md, c.name); upd(md, "="); upd(md, columnDigest(c));
        }
        return hex(md.digest());
    }

    // --------------------------------------------------------------- coverage

    public String[] coverage() {
        int[] o = order();
        int nulls = 0;
        double min = Double.POSITIVE_INFINITY, max = Double.NEGATIVE_INFINITY;
        boolean anyNumeric = false;
        for (Col c : cols) {
            for (int idx : o) {
                if (c.isNA(idx)) nulls++;
                if (c.numeric()) {
                    double v = c.value(idx);
                    if (!Double.isNaN(v)) { anyNumeric = true; if (v < min) min = v; if (v > max) max = v; }
                }
            }
        }
        return new String[] {
            Integer.toString(o.length),
            Integer.toString(cols.size()),
            Integer.toString(nulls),
            anyNumeric ? CanonicalNumber.num(min) : null,
            anyNumeric ? CanonicalNumber.num(max) : null
        };
    }

    // ----------------------------------------------------------------- probes

    /** The three probes of section 5, against the CANONICALLY SORTED rows. */
    public List<String[]> probeRules() {
        int n = rows();
        List<String[]> out = new ArrayList<>();
        out.add(new String[] { "index:1", Integer.toString(1) });
        out.add(new String[] { "index:ceil(n/2)", Integer.toString((n + 1) / 2) });
        out.add(new String[] { "index:n", Integer.toString(n) });
        return out;
    }

    /** Canonical fields of the 1-based canonical row {@code pos}. */
    public String[][] probeFields(int pos) {
        int[] o = order();
        int idx = o[pos - 1];
        String[][] out = new String[cols.size()][2];
        for (int i = 0; i < cols.size(); i++) {
            out[i][0] = cols.get(i).name;
            out[i][1] = cols.get(i).canon(idx);
        }
        return out;
    }
}
