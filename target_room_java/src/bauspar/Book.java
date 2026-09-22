package bauspar;

/**
 * The published customer record (constant record_field_catalogue), held COLUMNARLY in
 * primitive arrays -- GR-09/R11: no boxed collection of parsed row objects, so the
 * shape that works on 503 staged rows also works on the 45,881 of production.
 *
 * <p>Every numeric column here holds the PUBLISHED, already-rounded value of behaviour
 * step C19. Decisions were taken on the unrounded values before these were stored.
 */
public final class Book {

    public int n;

    public int[] rowIndex;
    public String[] id;
    public String[] phase;
    public double[] savingsRatio;
    public double[] savingGoal;
    public String[] contractType;
    public double[] goalFraction;
    public String[] goalSource;
    public double[] savingReference;
    public double[] balance;
    public double[] bausparSum;
    public double[] loanNotional;
    public double[] bausparLoan;
    public double[] loanToBausparRatio;
    public boolean[] isBridgeLoan;
    public boolean[] allocationEstimated;
    public boolean[] allocationInPast;
    public boolean[] repaymentActive;
    public boolean[] savingAfterAllocation;
    public boolean[] warnLoanPointless;
    public long[] contractStartDate;
    public long[] firstPaymentDate;
    public long[] allocationDate;
    public long[] loanStartDate;
    public long[] contractEndDate;
    public String[] yearContract;
    public String[] yearFirstPayment;
    public String[] yearAllocation;
    public String[] yearLoanStart;
    public double[] xContract;
    public double[] xFirstPayment;
    public double[] xAllocation;
    public double[] xLoanStart;
    public double[] xNow;

    /** Unrounded values kept only for the preconditions and the findings' exposure counts. */
    public double[] rawSavingsRatio;
    public boolean[] contractEnded;
    public boolean[] overGoal;
    public boolean[] contractEndWasAbsent;
    public double[] savingProgress;

    public Book(int capacity) {
        rowIndex = new int[capacity];
        id = new String[capacity];
        phase = new String[capacity];
        savingsRatio = new double[capacity];
        savingGoal = new double[capacity];
        contractType = new String[capacity];
        goalFraction = new double[capacity];
        goalSource = new String[capacity];
        savingReference = new double[capacity];
        balance = new double[capacity];
        bausparSum = new double[capacity];
        loanNotional = new double[capacity];
        bausparLoan = new double[capacity];
        loanToBausparRatio = new double[capacity];
        isBridgeLoan = new boolean[capacity];
        allocationEstimated = new boolean[capacity];
        allocationInPast = new boolean[capacity];
        repaymentActive = new boolean[capacity];
        savingAfterAllocation = new boolean[capacity];
        warnLoanPointless = new boolean[capacity];
        contractStartDate = new long[capacity];
        firstPaymentDate = new long[capacity];
        allocationDate = new long[capacity];
        loanStartDate = new long[capacity];
        contractEndDate = new long[capacity];
        yearContract = new String[capacity];
        yearFirstPayment = new String[capacity];
        yearAllocation = new String[capacity];
        yearLoanStart = new String[capacity];
        xContract = new double[capacity];
        xFirstPayment = new double[capacity];
        xAllocation = new double[capacity];
        xLoanStart = new double[capacity];
        xNow = new double[capacity];
        rawSavingsRatio = new double[capacity];
        contractEnded = new boolean[capacity];
        overGoal = new boolean[capacity];
        contractEndWasAbsent = new boolean[capacity];
        savingProgress = new double[capacity];
    }
}
