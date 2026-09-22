package bauspar;

/**
 * Controller directive 01 -- the abort path. A halt is a decision handed back, not a
 * crash: the carrier holds everything COMPARE needs to judge the two sides against
 * each other, and the caller keeps whatever was built before it.
 */
public final class AbortException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public final String abortCode;
    public final int rowIndex;        // 1-based, in the input table AS RECEIVED, before any sort
    public final String column;
    public final String rawValue;
    public int rowsCompleted;         // filled in by the caller that knows how far it got

    public AbortException(String abortCode, int rowIndex, String column, String rawValue,
                          int rowsCompleted, String message) {
        super(message);
        this.abortCode = abortCode;
        this.rowIndex = rowIndex;
        this.column = column;
        this.rawValue = rawValue;
        this.rowsCompleted = rowsCompleted;
    }
}
