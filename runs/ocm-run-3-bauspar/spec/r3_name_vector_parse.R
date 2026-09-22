#!/usr/bin/env Rscript
# =============================================================================
# OCM run 3 -- unit U01 -- mechanical name-vector parse, for the R3 gate.
#
# WHY THIS EXISTS. The kit's R3 gate (tools/check_detector_vs_spec.py) compares
# every list-valued constant in the neutral spec against a mechanically parsed
# field group, and fails the run if any declared vector is uncompared. Its input
# is r_source_field_groups.csv from the kit's own detector -- and for THIS
# source that file comes out EMPTY, correctly: the unit contains no literal
# column vector of the shape the detector looks for. Lessons finding 10 recorded
# exactly this and the gate now exits 2 ("could not compare") rather than 0.
# Exit 2 is honest, but it leaves the run's decisive vectors uncompared, which
# is the run-2 defect the gate was built to prevent.
#
# This script closes that hole from the source side. It parses the unit with the
# language's own parser -- it never evaluates it -- and emits the seven name
# vectors the neutral spec declares, in the detector's own CSV shape
# (file, group, ordinal, field), so the gate can be pointed at it and compare
# something real.
#
# It is a SOURCE OBSERVATION. It verifies; it configures nothing. Whether the
# controller feeds it to the gate is the controller's decision.
#
# Usage:
#   Rscript r3_name_vector_parse.R --engine source_room/customer_engine_v4.R \
#                                  --out    runs/ocm-run-3-bauspar/spec/r3_name_vectors.csv
# =============================================================================
args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default) {
  i <- match(flag, args)
  if (is.na(i)) return(default)
  if (i == length(args)) stop(flag, " requires a value")
  args[[i + 1L]]
}
ENGINE <- get_arg("--engine", "source_room/customer_engine_v4.R")
OUT    <- get_arg("--out",    "runs/ocm-run-3-bauspar/spec/r3_name_vectors.csv")

exprs <- parse(ENGINE, keep.source = FALSE)

## A formal with no default holds the language's EMPTY SYMBOL. Binding a local
## to it and testing the local afterwards raises "argument is missing" on the
## test itself, so the guard never runs -- unreachable code that reads as a
## working defence (lessons finding 11). The emptiness is therefore tested IN
## PLACE, before anything is bound.
walk <- function(node, visit) {
  if (is.expression(node)) {
    for (i in seq_along(node)) walk(node[[i]], visit)
    return(invisible(NULL))
  }
  visit(node)
  if (is.call(node) || is.pairlist(node))
    for (i in seq_along(node)) {
      if (identical(node[[i]], quote(expr = ))) next
      walk(node[[i]], visit)
    }
  invisible(NULL)
}

## --- the routine bodies we need, found by their definition ------------------
body_of <- function(name) {
  found <- NULL
  for (e in exprs)
    if (is.call(e) && identical(as.character(e[[1]]), "<-") &&
        is.symbol(e[[2]]) && identical(as.character(e[[2]]), name))
      found <- e[[3]]
  if (is.null(found)) stop("no definition of ", name, " found in ", ENGINE)
  found
}

## --- 1. field accesses on the contract row, in order of first appearance ----
contract_fields <- character(0)
walk(exprs, function(n) {
  if (is.call(n) && length(n) == 3L && identical(as.character(n[[1]]), "$") &&
      is.symbol(n[[2]]) && identical(as.character(n[[2]]), "contract"))
    contract_fields <<- c(contract_fields, as.character(n[[3]]))
})
## The eleven are a SET of accesses, not an ordered vector: the unit reads them
## by name and the table's own field order is irrelevant to it. They are emitted
## in byte order so that the comparison against the neutral spec is stable and
## carries no positional claim (GR-07: never a positional assumption).
contract_fields <- sort(unique(contract_fields), method = "radix")

## --- 2. the names of the record and of the export mapping -------------------
last_list_names <- function(fn_expr) {
  b <- fn_expr[[3]]                        # the routine body
  if (is.call(b) && identical(as.character(b[[1]]), "{"))
    b <- b[[length(b)]]                    # its last expression
  if (!(is.call(b) && identical(as.character(b[[1]]), "list")))
    stop("the last expression is not a named collection")
  nm <- names(b)[-1]
  if (any(!nzchar(nm))) stop("the collection has unnamed elements")
  nm
}
record_fields <- last_list_names(body_of("compute_contract"))
export_fields <- last_list_names(body_of("to_export_row"))

## --- 3. texts assigned to a given name, in order ----------------------------
assigned_texts <- function(fn_expr, target) {
  out <- character(0)
  walk(fn_expr, function(n) {
    if (is.call(n) && identical(as.character(n[[1]]), "<-") &&
        is.symbol(n[[2]]) && identical(as.character(n[[2]]), target))
      walk(n[[3]], function(m) if (is.character(m) && length(m) == 1L) out <<- c(out, m))
  })
  unique(out)
}
phase_values       <- assigned_texts(body_of("compute_contract"), "phase")
goal_source_values <- assigned_texts(body_of("compute_contract"), "goal_source")

## --- 4. literal text vectors inside a routine -------------------------------
first_text_vector <- function(fn_expr) {
  out <- NULL
  walk(fn_expr, function(n) {
    if (is.null(out) && is.call(n) && identical(as.character(n[[1]]), "c")) {
      parts <- as.list(n)[-1]
      if (length(parts) && all(vapply(parts, function(p) is.character(p) && length(p) == 1L,
                                      logical(1))))
        out <<- vapply(parts, as.character, character(1))
    }
  })
  if (is.null(out)) stop("no literal text vector found")
  out
}
date_markers   <- first_text_vector(body_of("parse_date_field"))
amount_markers <- first_text_vector(body_of("parse_de_number"))

groups <- list(contract_input_fields  = contract_fields,
               record_fields          = record_fields,
               export_fields          = export_fields,
               phase_values           = sort(phase_values, method = "radix"),
               goal_source_values     = goal_source_values,
               date_missing_markers   = date_markers,
               amount_missing_markers = amount_markers)

## A vector that came out empty means the parse did not look where it thought
## it was looking. Silence must not be indistinguishable from a clean source
## (lessons finding 12).
for (g in names(groups))
  if (!length(groups[[g]])) stop("name vector ", g, " parsed EMPTY; refusing to ",
                                 "emit a file that would let the gate pass on nothing")

rows <- do.call(rbind, lapply(names(groups), function(g)
  data.frame(file = basename(ENGINE), group = g,
             ordinal = seq_along(groups[[g]]), field = groups[[g]],
             stringsAsFactors = FALSE)))
dir.create(dirname(OUT), recursive = TRUE, showWarnings = FALSE)
write.csv(rows, OUT, row.names = FALSE)

for (g in names(groups))
  cat(sprintf("%-24s %2d  %s\n", g, length(groups[[g]]),
              paste(groups[[g]], collapse = ", ")))
cat("\nwrote", OUT, "--", nrow(rows), "rows\n")
cat("NOTE: two of the seven vectors are emitted in byte order rather than in",
    "source order, and both say so here rather than hiding it.",
    "contract_input_fields is a set of accesses with no source order worth",
    "carrying; phase_values is assigned in branch order, which for this unit",
    "happens to equal byte order, so that sort is a no-op. The other five keep",
    "the order the source itself gives them, and for record_fields and",
    "export_fields that order is contractual.\n")
