#!/usr/bin/env Rscript
# =============================================================================
# OCM run 3 -- OBSERVE_SOURCE harness (R20a: the source is EXECUTED).
#
# Reads the synthetic input table, applies ONLY the coercions the synthetic
# manifest declares, sources the unmodified engine, runs compute_contract over
# every row at the declared valuation date, and emits checkpoints_source.json
# under dec9-half-even-v1.
#
# The engine file is NOT modified. Anything this harness does to make it run is
# a harness patch and is recorded in the checkpoint file as one.
#
# Two mechanics here were verified empirically rather than taken from
# documentation, per lessons finding 5:
#
#   1. sprintf("%.8e", x) matches the contract's reference vectors on glibc,
#      INCLUDING the half-even tie at 2^-13 -- except negative zero, which R
#      renders "-0.00000000e+00" where the contract requires
#      "0.00000000e+00". Special-cased below, and the self-test would halt if
#      that ever stopped being true.
#
#   2. system2("sha256sum", input = txt) returns the WRONG digest: it appends a
#      trailing newline, so 41 bytes hash as 42. Digests here go through
#      writeBin to a file, which was checked against an independent SHA-256 of
#      the same bytes. A wrong-but-consistent digest on one side is worse than
#      a crash: it disagrees with the other side everywhere and looks like a
#      real divergence.
#
# STATUS: run PRE-SPEC, as a controller feasibility probe. Its default output
# is probe_source_execution.json, NOT checkpoints_source.json, because two
# things it fixes are the neutral spec's to declare, not the harness's:
# the checkpoint object's field set, and the canonical row order. Calling this
# the run's OBSERVE_SOURCE evidence before SPECIFY has declared either would be
# claiming a state the run has not reached. The definitive emission re-runs
# after the spec exists, and its digest is only then comparable.
#
# What the probe does establish, which nothing else could: the source EXECUTES
# at all on a stand-in, and produces 33 fields over 503 rows deterministically.
# Given the real input table is absent (F1), that was an open question.
#
# Usage:
#   Rscript observe_source.R --engine <path> --inputs <csv> \
#       --manifest <json> --out <probe_source_execution.json>
# =============================================================================

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = NULL) {
  i <- match(flag, args)
  if (is.na(i)) return(default)
  if (i == length(args)) stop(flag, " requires a value")
  args[[i + 1L]]
}
ENGINE   <- get_arg("--engine",   "source_room/customer_engine_v4.R")
INPUTS   <- get_arg("--inputs",   "source_room/inputs/merged_data_synthetic.csv")
MANIFEST <- get_arg("--manifest", "source_room/inputs/synthetic_manifest.json")
OUT      <- get_arg("--out",      "runs/ocm-run-3-bauspar/evidence/probe_source_execution.json")
RUN_ID   <- get_arg("--run-id",   "ocm-run-3-bauspar")
UNIT     <- get_arg("--unit",     "U01")

# ---- canonicalisation: dec9-half-even-v1 ------------------------------------
EPOCH <- as.Date("1970-01-01")

canon_double <- function(x) {
  if (is.na(x))        return("NA")
  if (is.nan(x))       return("NA")
  if (is.infinite(x))  return(if (x > 0) "INF" else "-INF")
  if (x == 0)          return("0.00000000e+00")   # covers -0 (contract §1)
  sprintf("%.8e", x)
}

canon_logical <- function(x) if (is.na(x)) "NA" else if (x) "true" else "false"

canon_date <- function(x) {
  if (is.na(x)) return("NA")
  as.character(as.integer(as.numeric(as.Date(x) - EPOCH)))
}

canon_string <- function(x) {
  if (is.na(x)) return("NA")
  x <- gsub("\\", "\\\\", as.character(x), fixed = TRUE)
  x <- gsub("\n", "\\n", x, fixed = TRUE)
  gsub("\r", "\\r", x, fixed = TRUE)
}

canon_value <- function(x) {
  if (inherits(x, "Date"))  return(canon_date(x))
  if (is.logical(x))        return(canon_logical(x))
  if (is.numeric(x))        return(canon_double(as.numeric(x)))
  canon_string(x)
}

canon_column <- function(v) vapply(seq_along(v), function(i) canon_value(v[[i]]), character(1))

# ---- self-test (contract §1: emitters MUST self-test at startup) ------------
self_test <- function() {
  cases <- list(
    list(1,            "1.00000000e+00"),
    list(-0.0,         "0.00000000e+00"),
    list(2^-13,        "1.22070312e-04"),
    list(1/3,          "3.33333333e-01"),
    list(123456789.5,  "1.23456790e+08"),
    list(-2.5e-10,     "-2.50000000e-10"),
    list(NaN,          "NA"),
    list(NA_real_,     "NA"),
    list(Inf,          "INF"),
    list(-Inf,         "-INF")
  )
  bad <- character(0)
  for (c_ in cases) {
    got <- canon_double(c_[[1]])
    if (!identical(got, c_[[2]]))
      bad <- c(bad, sprintf("  %s -> got %s, want %s", format(c_[[1]]), got, c_[[2]]))
  }
  if (length(bad))
    stop("canonicalisation self-test FAILED; refusing to emit:\n", paste(bad, collapse = "\n"))
  cat("canonicalisation self-test: 10/10 reference vectors OK\n")
}

# ---- SHA-256 over exact bytes (verified route) ------------------------------
sha256_bytes <- function(txt) {
  f <- tempfile()
  con <- file(f, "wb")
  writeBin(charToRaw(txt), con)
  close(con)
  out <- system2("sha256sum", args = shQuote(f), stdout = TRUE)
  unlink(f)
  sub("\\s.*$", "", out[[1]])
}

sha256_file <- function(path) sub("\\s.*$", "", system2("sha256sum", args = shQuote(path), stdout = TRUE)[[1]])

column_digest <- function(name, values) {
  sha256_bytes(paste(c("col", name, length(values), values), collapse = "\n"))
}

object_digest <- function(kind, rows, cols, colnames_, coldigests) {
  head <- c("obj", kind, rows, cols)
  body <- paste0(colnames_, "=", coldigests)
  sha256_bytes(paste(c(head, body), collapse = "\n"))
}

digest_obj <- function(value) list(algorithm = "SHA-256",
                                   canonicalisation = "dec9-half-even-v1",
                                   value = value)

# ---- minimal JSON writer (base R only) --------------------------------------
json_escape <- function(s) {
  s <- gsub("\\", "\\\\", s, fixed = TRUE)
  s <- gsub("\"", "\\\"", s, fixed = TRUE)
  s <- gsub("\n", "\\n", s, fixed = TRUE)
  gsub("\r", "\\r", s, fixed = TRUE)
}
to_json <- function(x, indent = 0) {
  pad <- strrep(" ", indent); pad2 <- strrep(" ", indent + 2)
  if (is.null(x)) return("null")
  if (is.list(x)) {
    nms <- names(x)
    if (!is.null(nms) && all(nzchar(nms))) {
      if (!length(x)) return("{}")
      parts <- vapply(seq_along(x), function(i)
        paste0(pad2, "\"", json_escape(nms[[i]]), "\": ", to_json(x[[i]], indent + 2)), character(1))
      return(paste0("{\n", paste(parts, collapse = ",\n"), "\n", pad, "}"))
    }
    if (!length(x)) return("[]")
    parts <- vapply(x, function(e) paste0(pad2, to_json(e, indent + 2)), character(1))
    return(paste0("[\n", paste(parts, collapse = ",\n"), "\n", pad, "]"))
  }
  if (length(x) != 1L) return(to_json(as.list(x), indent))
  if (is.logical(x))   return(if (is.na(x)) "null" else if (x) "true" else "false")
  if (is.numeric(x))   return(if (is.na(x)) "null" else format(x, scientific = FALSE, trim = TRUE))
  paste0("\"", json_escape(as.character(x)), "\"")
}

# ---- load the declared harness coercions ------------------------------------
# Deliberately a fixed, declared list read out of the manifest by a tiny regex
# rather than a JSON parser (base R has none). If the manifest shape changes,
# this must fail loudly rather than silently coerce nothing.
manifest_txt <- paste(readLines(MANIFEST, warn = FALSE), collapse = "\n")
extract_list <- function(key) {
  m <- regmatches(manifest_txt, regexpr(paste0("\"", key, "\"\\s*:\\s*\\[[^]]*\\]"), manifest_txt))
  if (!length(m)) stop("manifest does not declare '", key, "'; refusing to guess coercions")
  vals <- regmatches(m, gregexpr("\"[^\"]+\"", m))[[1]]
  setdiff(gsub("\"", "", vals), key)
}
TO_DATE <- extract_list("to_date_class")
cat("declared date-class coercions:", paste(TO_DATE, collapse = ", "), "\n")

val_m <- regmatches(manifest_txt, regexpr("\"valuation_date\"\\s*:\\s*\"[0-9-]+\"", manifest_txt))
if (!length(val_m)) stop("manifest does not declare valuation_date")
VALUATION_DATE <- as.Date(gsub(".*\"([0-9-]+)\"$", "\\1", val_m))
cat("valuation date:", format(VALUATION_DATE), "\n")

# ---- read inputs, apply ONLY the declared coercions -------------------------
md <- utils::read.csv(INPUTS, stringsAsFactors = FALSE, colClasses = "character",
                      check.names = FALSE, na.strings = character(0))
for (col in TO_DATE) {
  if (!col %in% names(md)) stop("declared coercion column missing from input: ", col)
  raw <- md[[col]]
  parsed <- as.Date(rep(NA_real_, length(raw)), origin = "1970-01-01")
  ok <- nzchar(raw) & !(raw %in% c("0", "00", "0000", "00000000", "NA", "<NA>"))
  parsed[ok] <- as.Date(raw[ok])
  md[[col]] <- parsed
}
cat("rows read:", nrow(md), " columns:", ncol(md), "\n")

# ---- execute the source, unmodified -----------------------------------------
self_test()
source(ENGINE, local = FALSE)
if (!exists("compute_contract")) stop("engine did not define compute_contract()")

records <- lapply(seq_len(nrow(md)), function(i)
  compute_contract(md[i, , drop = FALSE], VALUATION_DATE))
cat("records computed:", length(records), "\n")

# ---- assemble the checkpoint frame ------------------------------------------
FIELDS <- names(records[[1]])
frame <- list()
for (f in FIELDS) {
  vals <- lapply(records, function(r) { v <- r[[f]]; if (is.null(v) || !length(v)) NA else v[[1]] })
  first_real <- Filter(function(v) !is.null(v) && !all(is.na(v)), vals)
  proto <- if (length(first_real)) first_real[[1]] else NA
  if (inherits(proto, "Date")) {
    frame[[f]] <- as.Date(vapply(vals, function(v) if (is.na(v)) NA_real_ else as.numeric(v), numeric(1)),
                          origin = "1970-01-01")
  } else if (is.logical(proto)) {
    frame[[f]] <- vapply(vals, function(v) as.logical(v)[[1]], logical(1))
  } else if (is.numeric(proto)) {
    frame[[f]] <- vapply(vals, function(v) as.numeric(v)[[1]], numeric(1))
  } else {
    frame[[f]] <- vapply(vals, function(v) if (is.na(v)) NA_character_ else as.character(v)[[1]], character(1))
  }
}

# Canonical order: id ascending, bytewise. id is the contract number and is
# unique in this table, so this is a TOTAL order -- no ties, nothing left to
# tie-break, which is what the contract requires.
CANON_ORDER <- list(list(column = "id", direction = "asc"))
ord <- order(frame[["id"]], method = "radix")
if (anyDuplicated(frame[["id"]]))
  stop("canonical order is not total: duplicate id values in the checkpoint frame")
for (f in FIELDS) frame[[f]] <- frame[[f]][ord]

canon_cols <- lapply(FIELDS, function(f) canon_column(frame[[f]]))
names(canon_cols) <- FIELDS
coldigests <- vapply(FIELDS, function(f) column_digest(f, canon_cols[[f]]), character(1))

n_rows <- length(frame[[FIELDS[[1]]]])
obj_digest <- object_digest("frame", n_rows, length(FIELDS), FIELDS, coldigests)

# ---- probes (contract §5) ---------------------------------------------------
probe_rows <- list(c("index:1", 1L),
                   c(sprintf("index:ceil(n/2)"), as.integer(ceiling(n_rows / 2))),
                   c("index:n", n_rows))
probes <- lapply(probe_rows, function(pr) {
  i <- as.integer(pr[[2]])
  fields <- lapply(FIELDS, function(f) canon_cols[[f]][[i]])
  names(fields) <- FIELDS
  list(selection_rule = pr[[1]], fields = fields)
})

# ---- coverage (contract §6) -------------------------------------------------
numeric_fields <- FIELDS[vapply(FIELDS, function(f) is.numeric(frame[[f]]) && !inherits(frame[[f]], "Date"), logical(1))]
all_numeric <- unlist(lapply(numeric_fields, function(f) frame[[f]]), use.names = FALSE)
finite_numeric <- all_numeric[is.finite(all_numeric)]
null_count <- sum(vapply(FIELDS, function(f) sum(canon_cols[[f]] == "NA"), integer(1)))
coverage <- list(
  row_count   = n_rows,
  field_count = length(FIELDS),
  null_count  = as.integer(null_count),
  min = if (length(finite_numeric)) canon_double(min(finite_numeric)) else NULL,
  max = if (length(finite_numeric)) canon_double(max(finite_numeric)) else NULL
)

# ---- inputs binding (contract §7) -------------------------------------------
inputs <- list(list(name = basename(INPUTS),
                    bytes = as.integer(file.info(INPUTS)$size),
                    sha256 = sha256_file(INPUTS)))

checkpoint <- list(
  run_id = RUN_ID,
  side = "source",
  state = "OBSERVE_SOURCE",
  canonicalisation = "dec9-half-even-v1",
  emitted_utc = format(as.POSIXct(0, origin = "1970-01-01", tz = "UTC") +
                       as.numeric(Sys.time()), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
  harness_patches = list(list(
    file = basename(ENGINE),
    what = "none: the engine file is sourced unmodified",
    why  = paste("The harness supplies merged_data_with_tariff_amount as a synthetic",
                 "table and calls compute_contract() directly. No line of the engine",
                 "was edited, so no behaviour is attributable to the harness.")
  )),
  inputs = inputs,
  units = list(list(unit = UNIT, objects = list(list(
    name = "customer_book",
    kind = "frame",
    rows = n_rows,
    cols = length(FIELDS),
    colnames = as.list(FIELDS),
    canonical_order = CANON_ORDER,
    digest = digest_obj(obj_digest),
    coverage = coverage,
    probes = probes
  ))))
)

dir.create(dirname(OUT), recursive = TRUE, showWarnings = FALSE)
writeLines(to_json(checkpoint), OUT)
cat("\nwrote", OUT, "\n")
cat("object digest:", obj_digest, "\n")
cat("rows:", n_rows, " fields:", length(FIELDS), " nulls:", null_count, "\n")
