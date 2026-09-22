package bauspar;

/**
 * The per-contract calculation, behaviour steps C0 through C19, and the whole-book
 * shape of step C25. FAITHFUL ONLY: every finding the spec records as the source's
 * behaviour is reproduced here, unrepaired and unswitched.
 */
public final class Engine {

    // ---- constants, exactly as the spec declares them -------------------------
    public static final int  FALLBACK_ORIGIN_DAYS      = 2557;   // 7  x 365.25 -> 2556.75 -> 2557
    public static final int  ALLOCATION_FALLBACK_DAYS  = 3652;   // 10 x 365.25 -> 3652.5  -> 3652 (EVEN neighbour)
    public static final int  CONTRACT_END_FALLBACK_DAYS = 4018;  // 11 x 365.25 -> 4017.75 -> 4018
    public static final double BAUSPAR_SUM_UNIT_FACTOR = 1000;
    public static final double SAVING_GOAL_FRACTION_DEFAULT = 0.4;
    public static final double BRIDGE_RATIO_CUTOFF     = 2;
    public static final double WARN_BALANCE_FRACTION   = 0.9;
    public static final double SPECIAL_ALARM_RATIO_CUTOFF = 0.5;
    public static final double AXIS_CONTRACT           = 0.02;
    public static final double AXIS_FIRST_PAYMENT      = 0.06;
    public static final double AXIS_ALLOCATION         = 0.4;
    public static final double OVERSAVE_POSITION_BUMP  = 0.06;
    public static final double OVERSAVE_POSITION_CAP   = 0.46;
    public static final double FORTSETZER_WEDGE        = 0.18;
    public static final double LOAN_REGION_WIDTH       = 0.6;
    public static final double SAVING_REGION_WIDTH     = 0.34;
    public static final String GOAL_SOURCE_TARIFF      = "tariff";
    public static final String GOAL_SOURCE_FALLBACK    = "fallback_no_tariff";
    public static final String PHASE_DONE = "done", PHASE_LOAN = "loan",
                               PHASE_OVERSAVE = "oversave", PHASE_SAVE = "save";

    /** The fourteen rounded fields and their places (constant rounding_places). */
    public static final int RP_SAVINGS_RATIO = 3, RP_SAVING_GOAL = 0, RP_GOAL_FRACTION = 4,
            RP_SAVING_REFERENCE = 0, RP_BALANCE = 0, RP_BAUSPAR_SUM = 0, RP_LOAN_NOTIONAL = 0,
            RP_BAUSPAR_LOAN = 0, RP_RATIO = 3, RP_X = 4;

    private Engine() { }

    /** C16's clamp: the smaller of the value and the upper bound, then the larger of that and the lower. */
    static double clamp(double v, double lo, double hi) {
        return Math.max(Math.min(v, hi), lo);
    }

    private static boolean finite(double d) { return !Double.isNaN(d) && !Double.isInfinite(d); }

    /**
     * One contract row. {@code dates} carries the five date fields already read
     * (harness-coerced columns arrive as dates; unit-parsed columns were read by C1 and
     * may already have aborted the run). {@code amounts} carries the four amount texts
     * or pre-read numbers. Writes directly into the columnar book at slot {@code i}.
     */
    public static void computeInto(Book b, int i, int rowIndex, String id,
                                   long abschlussdatum, long einloesungsdatum, long erstmaligeZA,
                                   long tilgungsbeginn, long vertragsende,
                                   double daBetrag, double bausparsummeTeuro, double guthaben,
                                   double tariffAmount, String contractType,
                                   long valuation) {

        // ---- C4  TIMELINE ORIGIN ------------------------------------------------
        long contractStart = abschlussdatum;
        if (contractStart == DateValue.NA) contractStart = einloesungsdatum;
        if (contractStart == DateValue.NA) contractStart = valuation - FALLBACK_ORIGIN_DAYS;

        // ---- C5  ALLOCATION DATE ------------------------------------------------
        boolean allocationEstimated = (erstmaligeZA == DateValue.NA);
        long allocation;
        if (allocationEstimated) {
            long base = (einloesungsdatum != DateValue.NA) ? einloesungsdatum : contractStart;
            allocation = base + ALLOCATION_FALLBACK_DAYS;
        } else {
            allocation = erstmaligeZA;
        }

        // ---- C6  CONTRACT END ---------------------------------------------------
        boolean contractEndWasAbsent = (vertragsende == DateValue.NA);
        long contractEnd = contractEndWasAbsent ? allocation + CONTRACT_END_FALLBACK_DAYS : vertragsende;

        // ---- C7  AMOUNTS --------------------------------------------------------
        double loanNotional = daBetrag;
        double bausparSum   = bausparsummeTeuro * BAUSPAR_SUM_UNIT_FACTOR;
        double balance      = guthaben;

        // ---- C8  TARIFF SHARE ---------------------------------------------------
        double goalFraction;
        String goalSource;
        if (finite(tariffAmount) && tariffAmount > 0) {
            goalFraction = tariffAmount;           // a FRACTION of one (FND-02): used as it stands
            goalSource = GOAL_SOURCE_TARIFF;
        } else {
            goalFraction = SAVING_GOAL_FRACTION_DEFAULT;
            goalSource = GOAL_SOURCE_FALLBACK;
        }

        // ---- C10 BRIDGE TEST ----------------------------------------------------
        double ratio = (finite(bausparSum) && bausparSum > 0) ? (loanNotional / bausparSum) : Double.NaN;
        boolean isBridgeLoan = finite(ratio) && ratio > BRIDGE_RATIO_CUTOFF;   // STRICTLY greater

        // ---- C11 SAVING REFERENCE ----------------------------------------------
        double savingReference = (isBridgeLoan && finite(bausparSum) && bausparSum > 0)
                ? bausparSum : loanNotional;

        // ---- C12 DERIVED AMOUNTS ------------------------------------------------
        double savingGoal = goalFraction * savingReference;
        double savingsRatio = (finite(savingReference) && savingReference > 0)
                ? (balance / savingReference) : Double.NaN;
        double bausparLoan = savingReference - balance;
        boolean warnLoanPointless = finite(savingsRatio) && savingsRatio >= WARN_BALANCE_FRACTION;

        // ---- C13 TIMELINE PREDICATES -------------------------------------------
        boolean allocationInPast = (allocation != DateValue.NA) && (valuation > allocation);   // STRICTLY after
        boolean repaymentActive  = (tilgungsbeginn != DateValue.NA) && (valuation >= tilgungsbeginn);
        boolean contractEnded    = (contractEnd != DateValue.NA) && (valuation >= contractEnd);
        boolean overGoal         = finite(savingsRatio) && savingsRatio >= goalFraction;

        // ---- C14 PHASE ----------------------------------------------------------
        String phase = contractEnded ? PHASE_DONE
                     : repaymentActive ? PHASE_LOAN
                     : overGoal ? PHASE_OVERSAVE : PHASE_SAVE;

        // ---- C15 ----------------------------------------------------------------
        boolean savingAfterAllocation = allocationInPast && !repaymentActive && !contractEnded;

        // ---- C16 SCHEMATIC POSITIONS -------------------------------------------
        double xContract = AXIS_CONTRACT;
        double xFirstPayment = AXIS_FIRST_PAYMENT;
        double xAllocation = AXIS_ALLOCATION;
        double savingProgress = finite(savingsRatio)
                ? clamp(savingsRatio / goalFraction, 0.0, 1.0) : 0.0;

        // ---- C17 CURRENT POSITION ----------------------------------------------
        double xLoanStart, xNow;
        if (PHASE_LOAN.equals(phase) || PHASE_DONE.equals(phase)) {
            xLoanStart = AXIS_ALLOCATION;
            long ref = (tilgungsbeginn != DateValue.NA) ? tilgungsbeginn : allocation;
            double window  = DateValue.daysBetween(ref, contractEnd);
            double elapsed = DateValue.daysBetween(ref, valuation);
            double progress = (finite(window) && window > 0) ? clamp(elapsed / window, 0.0, 1.0) : 0.0;
            xNow = AXIS_ALLOCATION + progress * LOAN_REGION_WIDTH;
        } else if (savingAfterAllocation) {
            xLoanStart = Double.NaN;
            double window = DateValue.daysBetween(einloesungsdatum, allocation);
            double extra  = DateValue.daysBetween(allocation, valuation);
            double frac = (finite(window) && window > 0) ? clamp(extra / window, 0.0, 1.0) : 0.0;
            xNow = AXIS_ALLOCATION + frac * FORTSETZER_WEDGE;
        } else {
            xLoanStart = Double.NaN;
            xNow = AXIS_FIRST_PAYMENT + savingProgress * SAVING_REGION_WIDTH;
            if (PHASE_OVERSAVE.equals(phase)) {
                xNow = Math.min(xNow + OVERSAVE_POSITION_BUMP, OVERSAVE_POSITION_CAP);
            }
        }

        // ---- C18 YEAR LABELS ----------------------------------------------------
        String yearContract     = DateValue.yearLabel(contractStart);
        String yearFirstPayment = DateValue.yearLabel(einloesungsdatum);
        String yearAllocation   = DateValue.yearLabel(allocation);
        String yearLoanStart    = DateValue.yearLabel(tilgungsbeginn);
        if (allocationEstimated && !yearAllocation.isEmpty()) yearAllocation = "~" + yearAllocation;

        // ---- C19 RECORD (the ONLY place rounding happens) -----------------------
        b.rowIndex[i] = rowIndex;
        b.id[i] = id;
        b.phase[i] = phase;
        b.savingsRatio[i]       = Rounding.round(savingsRatio, RP_SAVINGS_RATIO);
        b.savingGoal[i]         = Rounding.round(savingGoal, RP_SAVING_GOAL);
        b.contractType[i]       = contractType;
        b.goalFraction[i]       = Rounding.round(goalFraction, RP_GOAL_FRACTION);
        b.goalSource[i]         = goalSource;
        b.savingReference[i]    = Rounding.round(savingReference, RP_SAVING_REFERENCE);
        b.balance[i]            = Rounding.round(balance, RP_BALANCE);
        b.bausparSum[i]         = Rounding.round(bausparSum, RP_BAUSPAR_SUM);
        b.loanNotional[i]       = Rounding.round(loanNotional, RP_LOAN_NOTIONAL);
        b.bausparLoan[i]        = Rounding.round(bausparLoan, RP_BAUSPAR_LOAN);
        b.loanToBausparRatio[i] = Rounding.round(ratio, RP_RATIO);
        b.isBridgeLoan[i] = isBridgeLoan;
        b.allocationEstimated[i] = allocationEstimated;
        b.allocationInPast[i] = allocationInPast;
        b.repaymentActive[i] = repaymentActive;
        b.savingAfterAllocation[i] = savingAfterAllocation;
        b.warnLoanPointless[i] = warnLoanPointless;
        b.contractStartDate[i] = contractStart;
        b.firstPaymentDate[i]  = einloesungsdatum;
        b.allocationDate[i]    = allocation;
        b.loanStartDate[i]     = tilgungsbeginn;
        b.contractEndDate[i]   = contractEnd;
        b.yearContract[i] = yearContract;
        b.yearFirstPayment[i] = yearFirstPayment;
        b.yearAllocation[i] = yearAllocation;
        b.yearLoanStart[i] = yearLoanStart;
        b.xContract[i]     = Rounding.round(xContract, RP_X);
        b.xFirstPayment[i] = Rounding.round(xFirstPayment, RP_X);
        b.xAllocation[i]   = Rounding.round(xAllocation, RP_X);
        b.xLoanStart[i]    = Rounding.round(xLoanStart, RP_X);
        b.xNow[i]          = Rounding.round(xNow, RP_X);

        b.rawSavingsRatio[i] = savingsRatio;
        b.contractEnded[i] = contractEnded;
        b.overGoal[i] = overGoal;
        b.contractEndWasAbsent[i] = contractEndWasAbsent;
        b.savingProgress[i] = savingProgress;
    }
}
