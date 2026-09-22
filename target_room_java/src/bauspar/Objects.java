package bauspar;

import java.util.List;

/**
 * The three checkpoint objects of the spec's checkpoint_objects, with their columns in
 * DECLARED spec order (the object digest depends on that order, not on alphabetical
 * order) and their declared canonical order.
 *
 * <p>{@code row_index} is not a field of the unit. It is the 1-based position of the
 * contract row in the input table as the unit receives it, header excluded, added by
 * the emitter so the canonical order is TOTAL: run assumption UA-04 says identifiers
 * may repeat in the real table, and with the identifier alone the order would be
 * undefined exactly there. Because it travels as DATA, a side that read the rows in a
 * different order shows up as a divergence instead of being hidden by the sort.
 */
public final class Objects {

    private Objects() { }

    public static CheckpointObject customerBook(Book b) {
        int n = b.n;
        CheckpointObject o = new CheckpointObject("customer_book", "frame");
        o.add(new Col.Int("row_index", b.rowIndex, n));
        o.add(new Col.Str("id", b.id, n));
        o.add(new Col.Str("phase", b.phase, n));
        o.add(new Col.Num("savings_ratio", b.savingsRatio, n));
        o.add(new Col.Num("saving_goal", b.savingGoal, n));
        o.add(new Col.Str("contract_type", b.contractType, n));
        o.add(new Col.Num("goal_fraction", b.goalFraction, n));
        o.add(new Col.Str("goal_source", b.goalSource, n));
        o.add(new Col.Num("saving_reference", b.savingReference, n));
        o.add(new Col.Num("balance", b.balance, n));
        o.add(new Col.Num("bauspar_sum", b.bausparSum, n));
        o.add(new Col.Num("loan_notional", b.loanNotional, n));
        o.add(new Col.Num("bauspar_loan", b.bausparLoan, n));
        o.add(new Col.Num("loan_to_bauspar_ratio", b.loanToBausparRatio, n));
        o.add(new Col.Bool("is_bridge_loan", b.isBridgeLoan, n));
        o.add(new Col.Bool("allocation_estimated", b.allocationEstimated, n));
        o.add(new Col.Bool("allocation_in_past", b.allocationInPast, n));
        o.add(new Col.Bool("repayment_active", b.repaymentActive, n));
        o.add(new Col.Bool("saving_after_allocation", b.savingAfterAllocation, n));
        o.add(new Col.Bool("warn_loan_pointless", b.warnLoanPointless, n));
        o.add(new Col.Date("contract_start_date", b.contractStartDate, n));
        o.add(new Col.Date("first_payment_date", b.firstPaymentDate, n));
        o.add(new Col.Date("allocation_date", b.allocationDate, n));
        o.add(new Col.Date("loan_start_date", b.loanStartDate, n));
        o.add(new Col.Date("contract_end_date", b.contractEndDate, n));
        o.add(new Col.Str("year_contract", b.yearContract, n));
        o.add(new Col.Str("year_first_payment", b.yearFirstPayment, n));
        o.add(new Col.Str("year_allocation", b.yearAllocation, n));
        o.add(new Col.Str("year_loan_start", b.yearLoanStart, n));
        o.add(new Col.Num("x_contract", b.xContract, n));
        o.add(new Col.Num("x_first_payment", b.xFirstPayment, n));
        o.add(new Col.Num("x_allocation", b.xAllocation, n));
        o.add(new Col.Num("x_loan_start", b.xLoanStart, n));
        o.add(new Col.Num("x_now", b.xNow, n));
        o.orderBy("id", "asc").orderBy("row_index", "asc");
        return o;
    }

    public static CheckpointObject exportRows(Export x) {
        int n = x.n;
        CheckpointObject o = new CheckpointObject("customer_export_rows", "frame");
        o.add(new Col.Int("row_index", x.rowIndex, n));
        o.add(new Col.Str("id", x.id, n));
        o.add(new Col.Str("phase", x.phase, n));
        o.add(new Col.Num("warn", x.warn, n));
        o.add(new Col.Num("sr", x.sr, n));
        o.add(new Col.Num("xc", x.xc, n));
        o.add(new Col.Num("xf", x.xf, n));
        o.add(new Col.Num("xa", x.xa, n));
        o.add(new Col.Num("xl", x.xl, n));
        o.add(new Col.Num("xn", x.xn, n));
        o.add(new Col.Str("lab_contract", x.labContract, n));
        o.add(new Col.Str("lab_first", x.labFirst, n));
        o.add(new Col.Str("lab_alloc", x.labAlloc, n));
        o.add(new Col.Str("lab_loan", x.labLoan, n));
        o.add(new Col.Num("guthaben", x.guthaben, n));
        o.add(new Col.Num("bausparsumme", x.bausparsumme, n));
        o.add(new Col.Num("save_target", x.saveTarget, n));
        o.add(new Col.Num("loan_amount", x.loanAmount, n));
        o.add(new Col.Num("dabetrag", x.dabetrag, n));
        o.add(new Col.Num("alloc_est", x.allocEst, n));
        o.add(new Col.Num("da_bsum_ratio", x.daBsumRatio, n));
        o.add(new Col.Num("bridge", x.bridge, n));
        o.add(new Col.Num("goal_frac", x.goalFrac, n));
        o.add(new Col.Str("contract_type", x.contractType, n));
        o.add(new Col.Str("goal_source", x.goalSource, n));
        o.add(new Col.Num("special", x.special, n));
        o.orderBy("id", "asc").orderBy("row_index", "asc");
        return o;
    }

    public static CheckpointObject jsDocument(List<String> lines) {
        int n = lines.size();
        int[] no = new int[n];
        String[] text = new String[n];
        for (int i = 0; i < n; i++) { no[i] = i + 1; text[i] = lines.get(i); }
        CheckpointObject o = new CheckpointObject("customers_js_document", "frame");
        o.add(new Col.Int("line_no", no, n));
        o.add(new Col.Str("line_text", text, n));
        o.orderBy("line_no", "asc");
        return o;
    }
}
