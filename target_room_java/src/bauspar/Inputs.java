package bauspar;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;

/**
 * Canonicalisation contract section 7 -- every checkpoint file records, for each input
 * file CONSUMED, its name, byte count and SHA-256. Two checkpoint files are comparable
 * only if their input lists agree byte for byte, so BOTH files this run consumes are
 * declared: the contract table and the manifest that supplies the harness coercions and
 * the valuation date. Entries are emitted in byte order of their names.
 */
public final class Inputs {

    public static final class Entry {
        public final String name; public final long bytes; public final String sha256;
        Entry(String name, long bytes, String sha256) { this.name = name; this.bytes = bytes; this.sha256 = sha256; }
    }

    private final List<Entry> entries = new ArrayList<>();

    public Inputs consume(Path p) throws IOException {
        entries.add(new Entry(p.getFileName().toString(), Files.size(p), sha256(p)));
        return this;
    }

    public List<Entry> sorted() {
        List<Entry> out = new ArrayList<>(entries);
        out.sort((a, b) -> Col.compareUtf8(a.name, b.name));
        return out;
    }

    public static String sha256(Path p) throws IOException {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] buf = new byte[1 << 16];
            try (InputStream in = Files.newInputStream(p)) {
                int r;
                while ((r = in.read(buf)) > 0) md.update(buf, 0, r);
            }
            return CheckpointObject.hex(md.digest());
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
