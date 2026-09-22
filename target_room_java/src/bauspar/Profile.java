package bauspar;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

/**
 * The input profile (R2/R3): types, nulls, RANGES, categories, duplicates and
 * row x field counts, taken from the actual file by a reader that performs none of
 * the normalisations the engine performs (protocol section 9).
 *
 * <p>Key vectors are captured IN FULL, never as a count (R3).
 */
public final class Profile {

    public long rows;
    public String[] header = new String[0];
    public final List<String> surplusFields = new ArrayList<>();
    public final List<String> absentRequired = new ArrayList<>();
    public final List<String> prefixCollisions = new ArrayList<>();

    /** Per date field: marker / eight-digit valid / hyphen valid / unreadable, and range. */
    public static final class DateField {
        public long missingMarker, eightDigitValid, hyphenValid, unreadable;
        public long min = Long.MAX_VALUE, max = Long.MIN_VALUE;
        public final List<String> unreadableSamples = new ArrayList<>();
        public final LinkedHashSet<String> markersSeen = new LinkedHashSet<>();
        public long total() { return missingMarker + eightDigitValid + hyphenValid + unreadable; }
        public boolean any() { return min != Long.MAX_VALUE; }
    }

    /** Per amount field: missing / negative / zero counts, range, and the FND-01 suspects. */
    public static final class AmountField {
        public long missing, negative, zeros, multiComma, dotNoComma, fnd01Suspects, gtOne, leZero;
        public double min = Double.POSITIVE_INFINITY, max = Double.NEGATIVE_INFINITY;
        public final List<String> suspectSamples = new ArrayList<>();
        public final LinkedHashSet<String> distinctRaw = new LinkedHashSet<>();
        public final LinkedHashSet<String> distinctRead = new LinkedHashSet<>();
        public boolean any() { return min != Double.POSITIVE_INFINITY; }
    }

    public final Map<String, DateField> dates = new LinkedHashMap<>();
    public final Map<String, AmountField> amounts = new LinkedHashMap<>();
    public final LinkedHashSet<String> contractTypes = new LinkedHashSet<>();
    public long idRows, idDistinct, idDuplicated;
    public final List<String> duplicatedIds = new ArrayList<>();
    public final List<String> exponentIds = new ArrayList<>();
    public long exponentIdCount;

    /** Harness coercion, as DECLARED in the manifest -- never inferred (directive 5). */
    public final Map<String, Character> coercionSeparator = new LinkedHashMap<>();
    public final List<String> coercedColumns = new ArrayList<>();
    public final List<String> rawDateColumns = new ArrayList<>();
}
