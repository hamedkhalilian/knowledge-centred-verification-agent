package bauspar;

/**
 * Behaviour step C21 -- the export mapping: the record renamed and narrowed to the 25
 * names of export_field_catalogue, in that order. Held columnarly like the book.
 *
 * <p>Two things here are measured behaviour and are reproduced exactly:
 * <ul>
 *   <li>the four yes-or-no values become the WHOLE NUMBERS 1 and 0;</li>
 *   <li>{@code special} is decided on the PUBLISHED, ALREADY ROUNDED ratio, unlike every
 *       flag in the record -- so 0.4996 publishes as 0.500 and raises no alarm while
 *       0.4994 publishes as 0.499 and raises one (FND-05).</li>
 * </ul>
 * The rounded amounts are mapped through as they are, so {@code loan_amount} need not
 * equal {@code bausparsumme} minus {@code guthaben} to the euro (FND-09).
 */
public final class Export {

    public final int n;
    public final int[] rowIndex;
    public final String[] id, phase, labContract, labFirst, labAlloc, labLoan, contractType, goalSource;
    public final double[] warn, sr, xc, xf, xa, xl, xn,
                          guthaben, bausparsumme, saveTarget, loanAmount, dabetrag,
                          allocEst, daBsumRatio, bridge, goalFrac, special;

    public Export(Book b) {
        n = b.n;
        rowIndex = new int[n];
        id = new String[n]; phase = new String[n];
        labContract = new String[n]; labFirst = new String[n];
        labAlloc = new String[n]; labLoan = new String[n];
        contractType = new String[n]; goalSource = new String[n];
        warn = new double[n]; sr = new double[n];
        xc = new double[n]; xf = new double[n]; xa = new double[n];
        xl = new double[n]; xn = new double[n];
        guthaben = new double[n]; bausparsumme = new double[n]; saveTarget = new double[n];
        loanAmount = new double[n]; dabetrag = new double[n];
        allocEst = new double[n]; daBsumRatio = new double[n]; bridge = new double[n];
        goalFrac = new double[n]; special = new double[n];

        for (int i = 0; i < n; i++) {
            rowIndex[i] = b.rowIndex[i];
            id[i] = b.id[i];
            phase[i] = b.phase[i];
            warn[i] = b.warnLoanPointless[i] ? 1 : 0;
            sr[i] = b.savingsRatio[i];
            xc[i] = b.xContract[i];
            xf[i] = b.xFirstPayment[i];
            xa[i] = b.xAllocation[i];
            xl[i] = b.xLoanStart[i];
            xn[i] = b.xNow[i];
            labContract[i] = b.yearContract[i];
            labFirst[i] = b.yearFirstPayment[i];
            labAlloc[i] = b.yearAllocation[i];
            labLoan[i] = b.yearLoanStart[i];
            guthaben[i] = b.balance[i];
            bausparsumme[i] = b.bausparSum[i];
            saveTarget[i] = b.savingGoal[i];
            loanAmount[i] = b.bausparLoan[i];
            dabetrag[i] = b.loanNotional[i];
            allocEst[i] = b.allocationEstimated[i] ? 1 : 0;
            daBsumRatio[i] = b.loanToBausparRatio[i];
            bridge[i] = b.isBridgeLoan[i] ? 1 : 0;
            goalFrac[i] = b.goalFraction[i];
            double publishedRatio = b.loanToBausparRatio[i];         // ALREADY ROUNDED
            special[i] = (!Double.isNaN(publishedRatio) && !Double.isInfinite(publishedRatio)
                          && publishedRatio < Engine.SPECIAL_ALARM_RATIO_CUTOFF) ? 1 : 0;
        }
    }

    public static final String[] FIELD_NAMES = {
        "id", "phase", "warn", "sr", "xc", "xf", "xa", "xl", "xn",
        "lab_contract", "lab_first", "lab_alloc", "lab_loan",
        "guthaben", "bausparsumme", "save_target", "loan_amount", "dabetrag",
        "alloc_est", "da_bsum_ratio", "bridge", "goal_frac",
        "contract_type", "goal_source", "special"
    };

    /** Behaviour step C23: one contract rendered as a script object literal. */
    public String renderRecord(int i) {
        StringBuilder sb = new StringBuilder(320);
        sb.append('{');
        appendField(sb, 0,  "id",            text(id[i]));
        appendField(sb, 1,  "phase",         text(phase[i]));
        appendField(sb, 2,  "warn",          num(warn[i]));
        appendField(sb, 3,  "sr",            num(sr[i]));
        appendField(sb, 4,  "xc",            num(xc[i]));
        appendField(sb, 5,  "xf",            num(xf[i]));
        appendField(sb, 6,  "xa",            num(xa[i]));
        appendField(sb, 7,  "xl",            num(xl[i]));
        appendField(sb, 8,  "xn",            num(xn[i]));
        appendField(sb, 9,  "lab_contract",  text(labContract[i]));
        appendField(sb, 10, "lab_first",     text(labFirst[i]));
        appendField(sb, 11, "lab_alloc",     text(labAlloc[i]));
        appendField(sb, 12, "lab_loan",      text(labLoan[i]));
        appendField(sb, 13, "guthaben",      num(guthaben[i]));
        appendField(sb, 14, "bausparsumme",  num(bausparsumme[i]));
        appendField(sb, 15, "save_target",   num(saveTarget[i]));
        appendField(sb, 16, "loan_amount",   num(loanAmount[i]));
        appendField(sb, 17, "dabetrag",      num(dabetrag[i]));
        appendField(sb, 18, "alloc_est",     num(allocEst[i]));
        appendField(sb, 19, "da_bsum_ratio", num(daBsumRatio[i]));
        appendField(sb, 20, "bridge",        num(bridge[i]));
        appendField(sb, 21, "goal_frac",     num(goalFrac[i]));
        appendField(sb, 22, "contract_type", text(contractType[i]));
        appendField(sb, 23, "goal_source",   text(goalSource[i]));
        appendField(sb, 24, "special",       num(special[i]));
        sb.append('}');
        return sb.toString();
    }

    private static void appendField(StringBuilder sb, int pos, String name, String value) {
        if (pos > 0) sb.append(',');                      // single commas, no spaces (C23)
        sb.append('"').append(name).append("\":").append(value);
    }

    /** C22 for a numeric export value. */
    private static String num(double v) { return ScriptFormat.number(v); }

    /** C22 for a text export value: missing renders as the bare word null. */
    private static String text(String s) { return s == null ? "null" : ScriptFormat.text(s); }
}
