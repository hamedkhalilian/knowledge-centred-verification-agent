#!/usr/bin/env Rscript
# =============================================================================
# OCM run 3 -- unit U01 -- SOURCE-SIDE CHECKPOINT EMITTER  (R20a)
#
# Sources the unit unmodified, computes every contract row of the staged input
# at the declared valuation date, and emits the three checkpoint objects the
# neutral spec declares, serialised under canonicalisation dec9-half-even-v1.
#
# This file is SOURCE-SIDE and is written in the source language by design; the
# barrier scanner does not apply to it. Nothing here crosses to the target.
#
# Four mechanics below were established by running them, not by reading about
# them (R13: prefer the execution):
#
#  1. The contract's reference vectors are self-tested at startup and the
#     emitter refuses to emit if any fails. Nine of the ten match the platform's
#     own fixed-exponent conversion exactly, including the half-even tie at
#     2^-13; NEGATIVE ZERO does not -- the platform gives "-0.00000000e+00"
#     where the contract requires "0.00000000e+00" -- so zero is special-cased.
#
#  2. Digesting a text through a pipe to the system hash tool appends a trailing
#     line feed, so 41 bytes hash as 42 and every digest is wrong but
#     self-consistent: it disagrees with the other side everywhere and looks
#     like a real divergence. The bytes are therefore written with writeBin and
#     the FILE is hashed.
#
#  3. This harness never creates a value named merged_data or
#     merged_data_with_tariff_amount. If it did, merely sourcing the unit would
#     write customers_data.js into the working directory -- and that is the
#     name of the quarantined answer key. The browser data file is produced
#     here on purpose, by an explicit call, into a temporary path.
#
#  4. The unit's own rounding is not the multiply-round-divide rule. The
#     sixteen reference vectors the neutral spec publishes are re-checked here
#     against the platform, so a drift between spec and source is caught at
#     startup rather than at comparison time.
#
# Inputs consumed: TWO files, and both are declared in the checkpoint's inputs
# list per contract section 7 -- the contract table, and the stand-in manifest
# that declares the date-class coercions and the valuation date. The second one
# is easy to miss precisely because it is configuration rather than data, and
# missing it makes the checkpoint file incomparable rather than merely terse.
#
# Determinism: two consecutive runs are byte-identical apart from emitted_utc.
# Pass --emitted-utc to fix that field and the two runs become fully identical.
#
# Usage:
#   Rscript emit_checkpoints.R \
#     --engine   source_room/customer_engine_v4.R \
#     --inputs   source_room/inputs/merged_data_synthetic.csv \
#     --manifest source_room/inputs/synthetic_manifest.json \
#     --out      runs/ocm-run-3-bauspar/evidence/checkpoints_source.json
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
OUT      <- get_arg("--out",      "runs/ocm-run-3-bauspar/evidence/checkpoints_source.json")
RUN_ID   <- get_arg("--run-id",   "ocm-run-3-bauspar")
UNIT     <- get_arg("--unit",     "U01")
STAMP    <- get_arg("--emitted-utc", NULL)

## ---------------------------------------------------------------------------
## 1. Canonicalisation dec9-half-even-v1
## ---------------------------------------------------------------------------
EPOCH <- as.Date("1970-01-01")

canon_double <- function(x) {
  if (is.na(x))       return("NA")            # covers NaN as well
  if (is.infinite(x)) return(if (x > 0) "INF" else "-INF")
  if (x == 0)         return("0.00000000e+00")  # contract section 1: also -0
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
  if (inherits(x, "Date")) return(canon_date(x))
  if (is.logical(x))       return(canon_logical(x))
  if (is.numeric(x))       return(canon_double(as.numeric(x)))
  canon_string(x)
}
canon_column <- function(v) vapply(seq_along(v), function(i) canon_value(v[[i]]), character(1))

## ---------------------------------------------------------------------------
## 2. Startup self-tests -- the emitter refuses to emit if either fails
## ---------------------------------------------------------------------------
self_test_canonicalisation <- function() {
  cases <- list(
    list(1,           "1.00000000e+00"), list(-0.0,        "0.00000000e+00"),
    list(2^-13,       "1.22070312e-04"), list(1/3,         "3.33333333e-01"),
    list(123456789.5, "1.23456790e+08"), list(-2.5e-10,    "-2.50000000e-10"),
    list(NaN,         "NA"),             list(NA_real_,    "NA"),
    list(Inf,         "INF"),            list(-Inf,        "-INF"))
  bad <- character(0)
  for (k in cases) {
    got <- canon_double(k[[1]])
    if (!identical(got, k[[2]]))
      bad <- c(bad, sprintf("  %s -> got %s, want %s", format(k[[1]]), got, k[[2]]))
  }
  if (length(bad))
    stop("canonicalisation self-test FAILED; refusing to emit:\n", paste(bad, collapse = "\n"))
  cat("self-test A: canonicalisation reference vectors 10/10 OK\n")
}

## The sixteen rounding vectors published in the neutral spec, re-measured here.
self_test_rounding <- function() {
  v <- list(
    list(0.1235, 3, 0.124),   list(0.0055, 3, 0.005),   list(0.0095, 3, 0.01),
    list(0.0085, 3, 0.009),   list(0.0005, 3, 0),       list(0.0625, 3, 0.062),
    list(0.1875, 3, 0.188),   list(0.4445, 3, 0.444),   list(-0.0055, 3, -0.005),
    list(0.12345, 4, 0.1235), list(0.5, 0, 0),          list(1.5, 0, 2),
    list(2.5, 0, 2),          list(14500.5, 0, 14500),  list(14501.5, 0, 14502),
    list(123456789.5, 0, 123456790))
  bad <- character(0)
  for (k in v) {
    got <- round(k[[1]], k[[2]])
    if (!isTRUE(all.equal(got, k[[3]], tolerance = 0)))
      bad <- c(bad, sprintf("  round(%.17g, %d) -> %.17g, spec says %.17g",
                            k[[1]], k[[2]], got, k[[3]]))
  }
  if (length(bad))
    stop("rounding self-test FAILED; the neutral spec and this platform disagree:\n",
         paste(bad, collapse = "\n"))
  cat("self-test B: rounding reference vectors 16/16 OK\n")
}

## Behaviour claims the neutral spec makes about the unit's own renderers.
## Runs after the unit is loaded; a failure means the SPEC is wrong.
self_test_unit_claims <- function() {
  chk <- list(
    list("value rendering 0.4",      js_value(0.4),            "0.4"),
    list("value rendering 14500",    js_value(14500),          "14500"),
    list("value rendering tiny",     js_value(1e-7),           "0"),
    list("value rendering missing",  js_value(NA),             "null"),
    list("value rendering text",     js_value("BS1"),          "\"BS1\""),
    list("thousands dot alone",      parse_de_number("36.263"), 36.263),
    list("thousands dot and comma",  parse_de_number("36.263,14"), 36263.14),
    list("short digit date",         format(parse_date_field("2013112")), "2013-11-02"),
    list("slash date is missing",    is.na(parse_date_field("2011/04/01")), TRUE),
    list("zero marker is missing",   is.na(parse_date_field("00000000")), TRUE))
  bad <- character(0)
  for (k in chk)
    if (!isTRUE(all.equal(k[[2]], k[[3]])))
      bad <- c(bad, sprintf("  %s -> %s, spec says %s", k[[1]],
                            paste(format(k[[2]]), collapse = ","),
                            paste(format(k[[3]]), collapse = ",")))
  if (length(bad))
    stop("unit-claim self-test FAILED; the neutral spec misdescribes the unit:\n",
         paste(bad, collapse = "\n"))
  cat("self-test C: unit behaviour claims 10/10 OK\n")
}

## ---------------------------------------------------------------------------
## 3. Digests -- over exact bytes, via a file (see header note 2)
## ---------------------------------------------------------------------------
sha256_bytes <- function(txt) {
  f <- tempfile(); con <- file(f, "wb")
  writeBin(charToRaw(txt), con); close(con)
  out <- system2("sha256sum", args = shQuote(f), stdout = TRUE)
  unlink(f)
  sub("\\s.*$", "", out[[1]])
}
sha256_file <- function(path)
  sub("\\s.*$", "", system2("sha256sum", args = shQuote(path), stdout = TRUE)[[1]])
column_digest <- function(name, values)
  sha256_bytes(paste(c("col", name, length(values), values), collapse = "\n"))
object_digest <- function(kind, rows, cols, colnames_, coldigests)
  sha256_bytes(paste(c("obj", kind, rows, cols, paste0(colnames_, "=", coldigests)),
                     collapse = "\n"))
digest_obj <- function(v) list(algorithm = "SHA-256",
                               canonicalisation = "dec9-half-even-v1", value = v)

## ---------------------------------------------------------------------------
## 4. Minimal JSON writer (base only)
## ---------------------------------------------------------------------------
json_escape <- function(s) {
  s <- gsub("\\", "\\\\", s, fixed = TRUE); s <- gsub("\"", "\\\"", s, fixed = TRUE)
  s <- gsub("\n", "\\n", s, fixed = TRUE);  gsub("\r", "\\r", s, fixed = TRUE)
}
to_json <- function(x, indent = 0) {
  pad <- strrep(" ", indent); pad2 <- strrep(" ", indent + 2)
  if (is.null(x)) return("null")
  if (is.list(x)) {
    nms <- names(x)
    if (!is.null(nms) && all(nzchar(nms))) {
      if (!length(x)) return("{}")
      parts <- vapply(seq_along(x), function(i)
        paste0(pad2, "\"", json_escape(nms[[i]]), "\": ", to_json(x[[i]], indent + 2)),
        character(1))
      return(paste0("{\n", paste(parts, collapse = ",\n"), "\n", pad, "}"))
    }
    if (!length(x)) return("[]")
    parts <- vapply(x, function(e) paste0(pad2, to_json(e, indent + 2)), character(1))
    return(paste0("[\n", paste(parts, collapse = ",\n"), "\n", pad, "]"))
  }
  if (length(x) != 1L) return(to_json(as.list(x), indent))
  if (is.logical(x)) return(if (is.na(x)) "null" else if (x) "true" else "false")
  if (is.numeric(x)) return(if (is.na(x)) "null" else format(x, scientific = FALSE, trim = TRUE))
  paste0("\"", json_escape(as.character(x)), "\"")
}

## ---------------------------------------------------------------------------
## 5. Declared harness coercions, read out of the stand-in's manifest
## ---------------------------------------------------------------------------
manifest_txt <- paste(readLines(MANIFEST, warn = FALSE), collapse = "\n")
extract_list <- function(key) {
  m <- regmatches(manifest_txt, regexpr(paste0("\"", key, "\"\\s*:\\s*\\[[^]]*\\]"), manifest_txt))
  if (!length(m)) stop("manifest does not declare '", key, "'; refusing to guess coercions")
  setdiff(gsub("\"", "", regmatches(m, gregexpr("\"[^\"]+\"", m))[[1]]), key)
}
TO_DATE <- extract_list("to_date_class")
val_m <- regmatches(manifest_txt, regexpr("\"valuation_date\"\\s*:\\s*\"[0-9-]+\"", manifest_txt))
if (!length(val_m)) stop("manifest does not declare valuation_date")
VALUATION_DATE <- as.Date(gsub(".*\"([0-9-]+)\"$", "\\1", val_m))

## ---------------------------------------------------------------------------
## 6. Run
## ---------------------------------------------------------------------------
self_test_canonicalisation()
self_test_rounding()
cat("declared date-class coercions:", paste(TO_DATE, collapse = ", "), "\n")
cat("valuation date:", format(VALUATION_DATE), "\n")

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

## No value named merged_data* exists here: see header note 3.
source(ENGINE, local = FALSE)
for (nm in c("compute_contract", "to_export_row", "js_value", "write_customers_js",
             "parse_de_number", "parse_date_field"))
  if (!exists(nm)) stop("the unit did not define ", nm)
self_test_unit_claims()

n_rows  <- nrow(md)
records <- lapply(seq_len(n_rows), function(i)
  compute_contract(md[i, , drop = FALSE], VALUATION_DATE))
cat("records computed:", length(records), "\n")

RECORD_FIELDS <- names(records[[1]])
if (!all(vapply(records, function(r) identical(names(r), RECORD_FIELDS), logical(1))))
  stop("the record field vector is not identical on every row; the spec's catalogue is unsafe")
exports       <- lapply(records, to_export_row)
EXPORT_FIELDS <- names(exports[[1]])

flatten <- function(items, fields) {
  out <- list()
  for (f in fields) {
    vals  <- lapply(items, function(r) { v <- r[[f]]; if (is.null(v) || !length(v)) NA else v[[1]] })
    real  <- Filter(function(v) !is.null(v) && !all(is.na(v)), vals)
    proto <- if (length(real)) real[[1]] else NA
    out[[f]] <- if (inherits(proto, "Date"))
      as.Date(vapply(vals, function(v) if (is.na(v)) NA_real_ else as.numeric(v), numeric(1)),
              origin = "1970-01-01")
    else if (is.logical(proto)) vapply(vals, function(v) as.logical(v)[[1]], logical(1))
    else if (is.numeric(proto)) vapply(vals, function(v) as.numeric(v)[[1]], numeric(1))
    else vapply(vals, function(v) if (is.na(v)) NA_character_ else as.character(v)[[1]],
                character(1))
  }
  out
}

book   <- c(list(row_index = as.numeric(seq_len(n_rows))), flatten(records, RECORD_FIELDS))
export <- c(list(row_index = as.numeric(seq_len(n_rows))), flatten(exports, EXPORT_FIELDS))

## The browser data file, produced by the unit's own writer into a temporary
## path, then read back as its physical lines.
js_path <- tempfile(fileext = ".js")
on.exit(unlink(js_path), add = TRUE)
## The unit's progress indicator writes several thousand characters to the
## console. It is captured here so the controller's log stays readable; the
## capture changes nothing that is written to the file, and the writer's own
## completion line is printed below.
writer_console <- capture.output(
  invisible(write_customers_js(md, valuation_date = VALUATION_DATE, path = js_path)))
cat("browser-data writer said:",
    tail(Filter(nzchar, trimws(writer_console)), 2)[[1]], "\n")
js_lines <- readLines(js_path, warn = FALSE)
if (length(js_lines) != n_rows + 4L)
  stop("browser data file has ", length(js_lines), " lines; expected ", n_rows + 4L)
jsdoc <- list(line_no = as.numeric(seq_along(js_lines)), line_text = js_lines)

## ---------------------------------------------------------------------------
## 7. Serialise one object per the contract
## ---------------------------------------------------------------------------
emit_object <- function(name, frame, fields, order_cols) {
  keys <- lapply(order_cols, function(o) {
    v <- frame[[o[["column"]]]]
    if (inherits(v, "Date")) as.numeric(v) else v
  })
  ord <- do.call(order, c(keys, list(method = "radix", na.last = TRUE)))
  for (f in fields) frame[[f]] <- frame[[f]][ord]
  last <- order_cols[[length(order_cols)]][["column"]]
  if (anyDuplicated(do.call(paste, c(lapply(order_cols, function(o) frame[[o[["column"]]]]),
                                     list(sep = "\r")))))
    stop("canonical order for ", name, " is not total: duplicate key tuples")
  canon <- lapply(fields, function(f) canon_column(frame[[f]]))
  names(canon) <- fields
  coldig <- vapply(fields, function(f) column_digest(f, canon[[f]]), character(1))
  nr <- length(frame[[fields[[1]]]])
  probe_at <- c(1L, as.integer(ceiling(nr / 2)), nr)
  rules    <- c("index:1", "index:ceil(n/2)", "index:n")
  probes <- lapply(seq_along(probe_at), function(j) {
    i <- probe_at[[j]]
    fl <- lapply(fields, function(f) canon[[f]][[i]]); names(fl) <- fields
    list(selection_rule = rules[[j]], fields = fl)
  })
  numf <- fields[vapply(fields, function(f)
    is.numeric(frame[[f]]) && !inherits(frame[[f]], "Date"), logical(1))]
  allnum <- unlist(lapply(numf, function(f) frame[[f]]), use.names = FALSE)
  fin <- allnum[is.finite(allnum)]
  nulls <- sum(vapply(fields, function(f) sum(canon[[f]] == "NA"), integer(1)))
  list(name = name, kind = "frame", rows = nr, cols = length(fields),
       colnames = as.list(fields),
       canonical_order = lapply(order_cols, function(o)
         list(column = o[["column"]], direction = o[["direction"]])),
       digest = digest_obj(object_digest("frame", nr, length(fields), fields, coldig)),
       coverage = list(row_count = nr, field_count = length(fields),
                       null_count = as.integer(nulls),
                       min = if (length(fin)) canon_double(min(fin)) else NULL,
                       max = if (length(fin)) canon_double(max(fin)) else NULL),
       probes = probes)
}

ord_id_row <- list(list(column = "id", direction = "asc"),
                   list(column = "row_index", direction = "asc"))
ord_line   <- list(list(column = "line_no", direction = "asc"))

objects <- list(
  emit_object("customer_book",        book,   c("row_index", RECORD_FIELDS), ord_id_row),
  emit_object("customer_export_rows", export, c("row_index", EXPORT_FIELDS), ord_id_row),
  emit_object("customers_js_document", jsdoc, c("line_no", "line_text"),     ord_line))

## Contract section 7: one entry for EACH input file consumed. This harness
## consumes TWO. The contract table is the obvious one; the stand-in manifest is
## the other, and it is not incidental -- the declared date-class coercions and
## the valuation date both come out of it, and both change every emitted value.
## A reader given only the table could not tell where the valuation date came
## from, which is the silent omission R16 forbids, and a checkpoint file that
## under-reports what it consumed is not comparable under section 7.
##
## Entries are emitted in BYTE ORDER OF THEIR NAMES. The contract requires the
## two sides' lists to agree; it does not say whether they are compared as
## sequences or as sets. Sorting removes the question at the source instead of
## leaving it to the comparison: two emitters then cannot differ merely by the
## order in which they happened to open their files.
CONSUMED    <- c(INPUTS, MANIFEST)
CONSUMED    <- CONSUMED[order(basename(CONSUMED), method = "radix")]
inputs_list <- lapply(CONSUMED, function(p)
  list(name   = basename(p),
       bytes  = as.integer(file.info(p)$size),
       sha256 = sha256_file(p)))

checkpoint <- list(
  run_id = RUN_ID, side = "source", state = "OBSERVE_SOURCE",
  canonicalisation = "dec9-half-even-v1",
  emitted_utc = if (is.null(STAMP))
    format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC") else STAMP,
  harness_patches = list(
    list(file = basename(ENGINE),
         what = "none: the unit is sourced unmodified",
         why  = "No line of the unit was edited, so no observed behaviour is attributable to this harness."),
    list(file = basename(INPUTS),
         what = "two fields coerced to a date type before the unit sees them",
         why  = paste("The stand-in is delivered as text. The manifest declares",
                      paste(TO_DATE, collapse = " and "),
                      "as date-typed and leaves the other three date fields as raw digits, so both",
                      "branches of the unit's date reader are exercised. The same declaration",
                      "governs both sides; neither side infers it.")),
    list(file = basename(ENGINE),
         what = "no value named merged_data or merged_data_with_tariff_amount is created",
         why  = paste("Creating either would make the act of loading the unit write",
                      "customers_data.js into the working directory, which is the name of the",
                      "run's quarantined answer key. The browser data file is instead produced by",
                      "an explicit call into a temporary path and read back as lines.")),
    list(file = basename(ENGINE),
         what = "the progress indicator's console output is captured",
         why  = paste("The unit's console progress indicator emits several thousand characters.",
                      "They are captured so the run log stays readable. Nothing written to the",
                      "browser data file, and nothing in any checkpoint object, is affected.")),
    list(file = "checkpoint objects",
         what = "row_index and line_no added as ordering keys",
         why  = paste("Neither is a field of the unit. They make the declared canonical order",
                      "total even if contract identifiers repeat, which the run's assumption",
                      "UA-04 says they may. Both sides emit them; the neutral spec declares them."))),
  inputs = inputs_list,
  units = list(list(unit = UNIT, objects = objects)))

dir.create(dirname(OUT), recursive = TRUE, showWarnings = FALSE)
writeLines(to_json(checkpoint), OUT)

cat("\nwrote", OUT, "\n")
for (o in objects)
  cat(sprintf("  %-22s rows %5d  cols %3d  nulls %6d  digest %s\n",
              o$name, o$rows, o$cols, o$coverage$null_count, o$digest$value))
for (k in inputs_list)
  cat(sprintf("  input consumed: %-28s %6d bytes  %s\n", k$name, k$bytes, k$sha256))
cat("invoked analyses beyond the unit's own execution: none declared for this run",
    "(contracts/run_params.json carries an empty set).\n")
