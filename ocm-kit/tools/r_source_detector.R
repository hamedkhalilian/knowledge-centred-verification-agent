#!/usr/bin/env Rscript
# =============================================================================
# OCM R Source Detector v1.0
# Static, non-executing source-side detector for R migration projects.
#
# Purpose
# -------
# Describe what the supplied R source EXPECTS from its inputs before Java runs.
# The detector parses R source but never sources/evaluates the migration scripts.
# It emits source observations only. They MUST NOT silently configure the target.
#
# Usage
# -----
#   Rscript ocm_r_source_detector.R --r-dir <dir> --out-dir <dir>
#   Rscript ocm_r_source_detector.R file1.R file2.R ... --out-dir <dir>
#
#   --probes <csv>  per-run anchor and phrase probes (default
#                   contracts/source_probes.csv). Optional; when absent the
#                   detector records RSD-NO-PROBES so that "no anchor findings"
#                   is never mistaken for "the source has no anchors".
#
# Outputs
# -------
#   r_source_contract.json
#   r_source_contract.md
#   r_source_file_io.csv
#   r_source_positional_layout.csv
#   r_source_column_usage.csv
#   r_source_field_groups.csv
#   r_source_function_defaults.csv
#   r_source_hardcoded_indices.csv
#   r_source_findings.csv
#
# OCM rule
# --------
#   evidence_role = SOURCE_OBSERVATION_ONLY
#   target_use     = COMPARE_OR_REVIEW_ONLY
#   target MUST independently detect/validate real input layout.
# =============================================================================

`%||%` <- function(a, b) if (is.null(a) || length(a) == 0L) b else a

# ---- argument parsing --------------------------------------------------------
.args <- commandArgs(trailingOnly = TRUE)
.r_dir <- NULL
.out_dir <- file.path(getwd(), "r_source_detector_output")
.files_explicit <- character(0)
.probes_path <- file.path("contracts", "source_probes.csv")

i <- 1L
while (i <= length(.args)) {
  a <- .args[[i]]
  if (identical(a, "--r-dir")) {
    i <- i + 1L; if (i > length(.args)) stop("--r-dir requires a path")
    .r_dir <- .args[[i]]
  } else if (identical(a, "--out-dir")) {
    i <- i + 1L; if (i > length(.args)) stop("--out-dir requires a path")
    .out_dir <- .args[[i]]
  } else if (identical(a, "--probes")) {
    i <- i + 1L; if (i > length(.args)) stop("--probes requires a path")
    .probes_path <- .args[[i]]
  } else if (grepl("^--", a)) {
    stop("Unknown option: ", a)
  } else {
    .files_explicit <- c(.files_explicit, a)
  }
  i <- i + 1L
}

if (!is.null(.r_dir)) {
  if (!dir.exists(.r_dir)) stop("R directory does not exist: ", .r_dir)
  .r_files <- list.files(.r_dir, pattern = "\\.[Rr]$", full.names = TRUE)
} else {
  .r_files <- .files_explicit
}
.r_files <- normalizePath(.r_files[file.exists(.r_files)], winslash = "/", mustWork = FALSE)
.r_files <- sort(unique(.r_files))
if (length(.r_files) == 0L) stop("No R files supplied. Use --r-dir or list files explicitly.")
dir.create(.out_dir, recursive = TRUE, showWarnings = FALSE)
.out_dir <- normalizePath(.out_dir, winslash = "/", mustWork = FALSE)

# ---- safe helpers ------------------------------------------------------------
.safe_deparse <- function(x) paste(deparse(x, width.cutoff = 500L), collapse = " ")
.call_name <- function(x) {
  if (!is.call(x)) return(NA_character_)
  h <- x[[1L]]
  if (is.symbol(h)) return(as.character(h))
  .safe_deparse(h)
}
.assign_name <- function(x) {
  if (!is.call(x)) return(NA_character_)
  op <- .call_name(x)
  if (!(op %in% c("<-", "=", "<<-")) || length(x) < 3L) return(NA_character_)
  lhs <- x[[2L]]
  if (is.symbol(lhs)) return(as.character(lhs))
  NA_character_
}
.line_of <- function(x) {
  sr <- attr(x, "srcref")
  if (is.null(sr)) return(NA_integer_)
  suppressWarnings(as.integer(sr[[1L]]))
}

# Restricted literal evaluator. It never invokes arbitrary source functions.
.literal_eval <- function(x) {
  if (is.null(x)) return(NULL)
  if (is.atomic(x) && !is.symbol(x)) return(x)
  if (is.symbol(x)) return(NULL)
  if (!is.call(x)) return(NULL)
  fn <- .call_name(x)
  args <- as.list(x)[-1L]
  vals <- lapply(args, .literal_eval)
  if (fn == "c") {
    if (any(vapply(vals, is.null, logical(1)))) return(NULL)
    return(unlist(vals, recursive = FALSE, use.names = FALSE))
  }
  if (fn == ":" && length(vals) == 2L && all(vapply(vals, function(v) length(v) == 1L && is.numeric(v), logical(1)))) {
    return(vals[[1L]]:vals[[2L]])
  }
  if (fn == "seq" || fn == "seq_len" || fn == "seq_along") {
    # Only accept fully literal forms.
    if (any(vapply(vals, is.null, logical(1)))) return(NULL)
    out <- tryCatch(do.call(get(fn, baseenv()), vals), error = function(e) NULL)
    return(out)
  }
  if (fn == "sprintf") {
    if (any(vapply(vals, is.null, logical(1)))) return(NULL)
    return(tryCatch(do.call(sprintf, vals), error = function(e) NULL))
  }
  if (fn == "paste0") {
    if (any(vapply(vals, is.null, logical(1)))) return(NULL)
    return(tryCatch(do.call(paste0, vals), error = function(e) NULL))
  }
  if (fn == "paste") {
    if (any(vapply(vals, is.null, logical(1)))) return(NULL)
    return(tryCatch(do.call(paste, vals), error = function(e) NULL))
  }
  NULL
}

# Return named actual arguments from a call.
.call_args <- function(cl) {
  if (!is.call(cl)) return(list())
  a <- as.list(cl)[-1L]
  n <- names(a)
  if (is.null(n)) n <- rep("", length(a))
  names(a) <- n
  a
}
.arg_value_text <- function(args, name, position = NULL) {
  v <- NULL
  if (name %in% names(args)) v <- args[[name]]
  if (is.null(v) && !is.null(position) && length(args) >= position) v <- args[[position]]
  if (is.null(v)) return(NA_character_)
  lit <- .literal_eval(v)
  if (!is.null(lit) && length(lit) == 1L) return(as.character(lit))
  .safe_deparse(v)
}

# Recursive AST walk.
.walk <- function(x, fun, file, parent = NULL) {
  fun(x, file, parent)
  if (is.call(x) || is.pairlist(x) || is.expression(x)) {
    xs <- as.list(x)
    for (j in seq_along(xs)) .walk(xs[[j]], fun, file, x)
  }
  invisible(NULL)
}

# ---- result stores -----------------------------------------------------------
file_io <- list()
positional <- list()
column_usage <- list()
field_groups <- list()
function_defaults <- list()
hardcoded_indices <- list()
findings <- list()
literal_vectors <- list()      # name -> values + evidence
colname_bindings <- list()     # object -> vector name

.add <- function(store_name, row) {
  cur <- get(store_name, envir = .GlobalEnv)
  cur[[length(cur) + 1L]] <- row
  assign(store_name, cur, envir = .GlobalEnv)
}

# ---- first pass: parse + collect assignments/literals ------------------------
parsed <- list()
parse_errors <- list()
for (f in .r_files) {
  ex <- tryCatch(parse(f, keep.source = TRUE), error = function(e) e)
  if (inherits(ex, "error")) {
    parse_errors[[f]] <- conditionMessage(ex)
    .add("findings", data.frame(
      severity = "ERROR", code = "RSD-PARSE", file = basename(f), line = NA_integer_,
      message = paste("R parse failed:", conditionMessage(ex)), stringsAsFactors = FALSE))
    next
  }
  parsed[[f]] <- ex

  cb <- function(x, file, parent) {
    nm <- .assign_name(x)
    if (!is.na(nm)) {
      rhs <- x[[3L]]
      val <- .literal_eval(rhs)
      if (!is.null(val) && (is.character(val) || is.numeric(val) || is.logical(val))) {
        literal_vectors[[nm]] <<- list(values = val, file = basename(file), line = .line_of(x), expr = .safe_deparse(rhs))
      }
    }
    # colnames(obj) <- vectorName OR names(obj) <- vectorName
    if (is.call(x) && .call_name(x) %in% c("<-", "=", "<<-")) {
      lhs <- x[[2L]]; rhs <- x[[3L]]
      if (is.call(lhs) && .call_name(lhs) %in% c("colnames", "names") && length(lhs) >= 2L && is.symbol(lhs[[2L]])) {
        obj <- as.character(lhs[[2L]])
        if (is.symbol(rhs)) colname_bindings[[obj]] <<- list(vector = as.character(rhs), file = basename(file), line = .line_of(x))
        else {
          vv <- .literal_eval(rhs)
          if (is.character(vv)) {
            synthetic <- paste0(".__inline_names_", length(literal_vectors) + 1L)
            literal_vectors[[synthetic]] <<- list(values = vv, file = basename(file), line = .line_of(x), expr = .safe_deparse(rhs))
            colname_bindings[[obj]] <<- list(vector = synthetic, file = basename(file), line = .line_of(x))
          }
        }
      }
    }
  }
  for (e in ex) .walk(e, cb, f)
}

# Materialise positional layouts from explicit source name vectors.
for (obj in names(colname_bindings)) {
  b <- colname_bindings[[obj]]
  vec <- literal_vectors[[b$vector]]
  if (is.null(vec) || !is.character(vec$values)) next
  vals <- vec$values
  for (k in seq_along(vals)) {
    .add("positional", data.frame(
      object = obj, field = vals[[k]], source_position = k,
      vector_name = b$vector, file = vec$file, line = vec$line,
      evidence_role = "SOURCE_OBSERVATION_ONLY", stringsAsFactors = FALSE))
  }
}

# ---- second pass: input reads, field accesses, function defaults, indices ----
.readers <- c("read_excel", "excel_sheets", "read.csv", "read_csv", "readRDS", "read.table", "readLines", "scan")

for (f in names(parsed)) {
  ex <- parsed[[f]]
  cb <- function(x, file, parent) {
    if (!is.call(x)) return(invisible(NULL))
    fn <- .call_name(x)
    line <- .line_of(x)

    # input readers: infer assignment target from immediate parent if possible
    if (fn %in% .readers) {
      target <- if (!is.null(parent)) .assign_name(parent) else NA_character_
      a <- .call_args(x)
      .add("file_io", data.frame(
        file = basename(file), line = line, target = target,
        reader = fn,
        source_expr = .arg_value_text(a, "file", 1L),
        sheet = .arg_value_text(a, "sheet", NULL),
        sep = .arg_value_text(a, "sep", NULL),
        dec = .arg_value_text(a, "dec", NULL),
        header = .arg_value_text(a, "header", NULL),
        evidence_role = "SOURCE_OBSERVATION_ONLY",
        stringsAsFactors = FALSE))
    }

    # object$field
    if (fn == "$" && length(x) >= 3L && is.symbol(x[[2L]]) && is.symbol(x[[3L]])) {
      .add("column_usage", data.frame(
        file = basename(file), line = line,
        object = as.character(x[[2L]]), field = as.character(x[[3L]]),
        access = "$", context = .safe_deparse(parent %||% x),
        stringsAsFactors = FALSE))
    }

    # x[["field"]] or x[[5]]
    if (fn == "[[" && length(x) >= 3L && is.symbol(x[[2L]])) {
      idx <- .literal_eval(x[[3L]])
      if (!is.null(idx) && length(idx) == 1L) {
        .add("column_usage", data.frame(
          file = basename(file), line = line,
          object = as.character(x[[2L]]), field = as.character(idx),
          access = "[[", context = .safe_deparse(parent %||% x),
          stringsAsFactors = FALSE))
      }
    }

    # Hard-coded numeric/character index in x[rows, cols] or x[index]
    if (fn == "[" && length(x) >= 3L && is.symbol(x[[2L]])) {
      idx_args <- as.list(x)[-c(1L, 2L)]
      for (q in seq_along(idx_args)) {
        idx <- .literal_eval(idx_args[[q]])
        if (!is.null(idx) && length(idx) > 0L && (is.numeric(idx) || is.character(idx))) {
          .add("hardcoded_indices", data.frame(
            file = basename(file), line = line, object = as.character(x[[2L]]),
            dimension = q, index = paste(idx, collapse = ","),
            expression = .safe_deparse(x), stringsAsFactors = FALSE))
        }
      }
    }

    # Function definitions: capture string/numeric defaults that look like column names/config.
    if (fn == "function" && length(x) >= 3L) {
      form <- x[[2L]]
      nms <- names(form)
      if (!is.null(nms)) {
        for (nm in nms) {
          # A formal with no default holds R's empty symbol. Binding it to a
          # local and then touching the local raises "argument is missing",
          # so the emptiness must be tested IN PLACE, before any binding --
          # the earlier `dv <- form[[nm]]; if (is.symbol(dv) ...)` guard was
          # unreachable and halted the detector on any function with a
          # non-defaulted parameter. Adjudicated + fixed with a reproduction.
          if (identical(form[[nm]], quote(expr = ))) next
          dv <- form[[nm]]
          lit <- .literal_eval(dv)
          if (!is.null(lit) && length(lit) == 1L && (is.character(lit) || is.numeric(lit) || is.logical(lit))) {
            .add("function_defaults", data.frame(
              file = basename(file), line = line,
              parameter = nm, default_value = as.character(lit),
              function_expr = substr(.safe_deparse(x), 1L, 240L),
              stringsAsFactors = FALSE))
          }
        }
      }
    }
    invisible(NULL)
  }
  for (e in ex) .walk(e, cb, f)
}

# ---- field groups from literal vectors --------------------------------------
for (nm in names(literal_vectors)) {
  v <- literal_vectors[[nm]]
  if (!is.character(v$values)) next
  if (grepl("(_cols|_columns|col_names|date_cols|numeric_cols)$", nm) || grepl("cols|columns|names", nm)) {
    for (z in seq_along(v$values)) {
      .add("field_groups", data.frame(
        group = nm, ordinal = z, field = v$values[[z]], file = v$file, line = v$line,
        stringsAsFactors = FALSE))
    }
  }
}

# ---- declared per-run source probes -----------------------------------------
# These were hard-coded to one previous run's object names ("kobra_data"), its
# field anchors and its decision-rule phrases. A "source-agnostic" detector
# that names one run's fields reports nothing on any other source while still
# exiting 0 -- silence that reads as a clean bill of health. They are now
# declared per run in a probes CSV, and their absence is reported as a finding
# rather than passing unnoticed.
#
# Probe CSV columns: kind,code,object,field,pattern,message
#   kind=anchor : report the positional index of <field> within <object>
#   kind=text   : report <message> when every pattern sharing <code> matches
.probe_rows <- NULL
if (nzchar(.probes_path) && file.exists(.probes_path)) {
  .probe_rows <- utils::read.csv(.probes_path, stringsAsFactors = FALSE,
                                 colClasses = "character")
}
if (is.null(.probe_rows) || nrow(.probe_rows) == 0L) {
  .add("findings", data.frame(
    severity = "INFO", code = "RSD-NO-PROBES", file = NA_character_, line = NA_integer_,
    message = paste0("No per-run source probes declared (looked in '", .probes_path,
                     "'). Anchor and phrase findings were NOT produced; their ",
                     "absence here is not evidence that the source lacks them."),
    stringsAsFactors = FALSE))
} else {
  .pos_df <- if (length(positional)) do.call(rbind, positional) else data.frame()
  .anchors <- .probe_rows[.probe_rows$kind == "anchor", , drop = FALSE]
  if (nrow(.anchors)) {
    if (!nrow(.pos_df)) {
      .add("findings", data.frame(
        severity = "INFO", code = "RSD-ANCHOR-NO-LAYOUT", file = NA_character_, line = NA_integer_,
        message = "Anchor probes were declared but the source exposes no positional field layout to check them against.",
        stringsAsFactors = FALSE))
    } else {
      for (obj in unique(.anchors$object)) {
        kp <- .pos_df[.pos_df$object == obj, , drop = FALSE]
        if (!nrow(kp)) {
          .add("findings", data.frame(
            severity = "INFO", code = "RSD-ANCHOR-ABSENT", file = NA_character_, line = NA_integer_,
            message = sprintf("Anchor probe declared object '%s'; the source assigns no positional fields to it.", obj),
            stringsAsFactors = FALSE))
          next
        }
        .add("findings", data.frame(
          severity = "INFO", code = "RSD-LAYOUT", file = kp$file[[1]], line = kp$line[[1]],
          message = sprintf("R source assigns %d positional fields to %s.", nrow(kp), obj),
          stringsAsFactors = FALSE))
        want <- .anchors[.anchors$object == obj, , drop = FALSE]
        for (w in seq_len(nrow(want))) {
          fld <- want$field[[w]]
          rr <- kp[kp$field == fld, , drop = FALSE]
          code <- if (nzchar(want$code[[w]])) want$code[[w]] else "RSD-ANCHOR"
          if (nrow(rr)) {
            .add("findings", data.frame(
              severity = "INFO", code = code, file = rr$file[[1]], line = rr$line[[1]],
              message = sprintf("Source expectation: %s.%s is field %d (source observation only).",
                                obj, fld, rr$source_position[[1]]),
              stringsAsFactors = FALSE))
          } else {
            .add("findings", data.frame(
              severity = "INFO", code = paste0(code, "-ABSENT"), file = NA_character_, line = NA_integer_,
              message = sprintf("Anchor probe declared %s.%s; not found in the source's positional layout.", obj, fld),
              stringsAsFactors = FALSE))
          }
        }
      }
    }
  }

  # Text probes: report declared phrases found in the source, without
  # reconciling them. Every pattern sharing a code must match the same file.
  .texts <- .probe_rows[.probe_rows$kind == "text", , drop = FALSE]
  if (nrow(.texts)) {
    .all_text <- lapply(.r_files, function(f) paste(readLines(f, warn = FALSE), collapse = "\n"))
    names(.all_text) <- basename(.r_files)
    for (code in unique(.texts$code)) {
      pats <- .texts[.texts$code == code, , drop = FALSE]
      msg <- pats$message[[1]]
      for (nm in names(.all_text)) {
        txt <- .all_text[[nm]]
        if (all(vapply(pats$pattern, function(pp) grepl(pp, txt), logical(1)))) {
          .add("findings", data.frame(
            severity = "INFO", code = code, file = nm, line = NA_integer_,
            message = if (nzchar(msg)) msg else sprintf("Declared source phrase probe %s matched.", code),
            stringsAsFactors = FALSE))
        }
      }
    }
  }
}


# ---- data-frame normalisation ------------------------------------------------
.bind_rows <- function(x, cols = NULL) {
  if (length(x) == 0L) {
    if (is.null(cols)) return(data.frame())
    z <- as.data.frame(setNames(replicate(length(cols), logical(0), simplify = FALSE), cols), stringsAsFactors = FALSE)
    return(z)
  }
  do.call(rbind, x)
}
file_io_df <- .bind_rows(file_io)
positional_df <- .bind_rows(positional)
column_usage_df <- .bind_rows(column_usage)
field_groups_df <- .bind_rows(field_groups)
function_defaults_df <- .bind_rows(function_defaults)
hardcoded_indices_df <- .bind_rows(hardcoded_indices)
findings_df <- .bind_rows(findings)

# Deduplicate observations created by recursive context visits.
.dedup <- function(df) if (nrow(df)) unique(df) else df
file_io_df <- .dedup(file_io_df)
positional_df <- .dedup(positional_df)
column_usage_df <- .dedup(column_usage_df)
field_groups_df <- .dedup(field_groups_df)
function_defaults_df <- .dedup(function_defaults_df)
hardcoded_indices_df <- .dedup(hardcoded_indices_df)
findings_df <- .dedup(findings_df)

# ---- CSV outputs -------------------------------------------------------------
write.csv(file_io_df, file.path(.out_dir, "r_source_file_io.csv"), row.names = FALSE, na = "")
write.csv(positional_df, file.path(.out_dir, "r_source_positional_layout.csv"), row.names = FALSE, na = "")
write.csv(column_usage_df, file.path(.out_dir, "r_source_column_usage.csv"), row.names = FALSE, na = "")
write.csv(field_groups_df, file.path(.out_dir, "r_source_field_groups.csv"), row.names = FALSE, na = "")
write.csv(function_defaults_df, file.path(.out_dir, "r_source_function_defaults.csv"), row.names = FALSE, na = "")
write.csv(hardcoded_indices_df, file.path(.out_dir, "r_source_hardcoded_indices.csv"), row.names = FALSE, na = "")
write.csv(findings_df, file.path(.out_dir, "r_source_findings.csv"), row.names = FALSE, na = "")

# ---- minimal JSON writer (base R only) --------------------------------------
.jesc <- function(s) {
  s <- as.character(s)
  s <- gsub("\\\\", "\\\\\\\\", s)
  s <- gsub('"', '\\\\"', s, fixed = TRUE)
  s <- gsub("\r", "\\\\r", s, fixed = TRUE)
  s <- gsub("\n", "\\\\n", s, fixed = TRUE)
  s <- gsub("\t", "\\\\t", s, fixed = TRUE)
  s
}
.jstr <- function(s) ifelse(is.na(s), "null", paste0('"', .jesc(s), '"'))
.jnum <- function(x) ifelse(is.na(x), "null", format(x, scientific = FALSE, trim = TRUE))
.df_json <- function(df) {
  if (nrow(df) == 0L) return("[]")
  rows <- character(nrow(df))
  for (r in seq_len(nrow(df))) {
    kv <- character(ncol(df))
    for (c in seq_along(df)) {
      val <- df[[c]][[r]]
      enc <- if (is.numeric(df[[c]]) || is.integer(df[[c]])) .jnum(val) else if (is.logical(df[[c]])) {
        if (is.na(val)) "null" else if (isTRUE(val)) "true" else "false"
      } else .jstr(val)
      kv[[c]] <- paste0(.jstr(names(df)[[c]]), ":", enc)
    }
    rows[[r]] <- paste0("{", paste(kv, collapse = ","), "}")
  }
  paste0("[", paste(rows, collapse = ","), "]")
}

file_inventory <- data.frame(
  file = basename(.r_files),
  path = .r_files,
  bytes = as.numeric(file.info(.r_files)$size),
  md5 = unname(tools::md5sum(.r_files)),
  stringsAsFactors = FALSE
)

contract_json <- paste0(
  "{\n",
  '  "schema":"ocm-r-source-contract/1.0",\n',
  '  "evidence_role":"SOURCE_OBSERVATION_ONLY",\n',
  '  "target_use":"COMPARE_OR_REVIEW_ONLY",\n',
  '  "warning":"Do not silently configure target layout from this report. Target must independently detect or a reviewer must explicitly approve source-assisted resolution.",\n',
  '  "generated_at_utc":', .jstr(format(Sys.time(), tz = "UTC", usetz = TRUE)), ',\n',
  '  "files":', .df_json(file_inventory), ',\n',
  '  "input_reads":', .df_json(file_io_df), ',\n',
  '  "positional_layout":', .df_json(positional_df), ',\n',
  '  "column_usage":', .df_json(column_usage_df), ',\n',
  '  "field_groups":', .df_json(field_groups_df), ',\n',
  '  "function_defaults":', .df_json(function_defaults_df), ',\n',
  '  "hardcoded_indices":', .df_json(hardcoded_indices_df), ',\n',
  '  "findings":', .df_json(findings_df), '\n',
  "}\n"
)
writeLines(contract_json, file.path(.out_dir, "r_source_contract.json"), useBytes = TRUE)

# ---- Markdown human report --------------------------------------------------
.md_table <- function(df, max_rows = 100L) {
  if (nrow(df) == 0L) return("_None detected._")
  x <- head(df, max_rows)
  x[] <- lapply(x, function(v) { v <- as.character(v); v[is.na(v)] <- ""; gsub("\\|", "\\\\|", v) })
  h <- paste0("| ", paste(names(x), collapse = " | "), " |")
  s <- paste0("| ", paste(rep("---", ncol(x)), collapse = " | "), " |")
  b <- apply(x, 1L, function(r) paste0("| ", paste(r, collapse = " | "), " |"))
  paste(c(h, s, b), collapse = "\n")
}

md <- c(
  "# OCM R Source Detector Report",
  "",
  "**Evidence role:** `SOURCE_OBSERVATION_ONLY`  ",
  "**Target use:** `COMPARE_OR_REVIEW_ONLY`",
  "",
  "> This report describes what the R source says/assumes. It is not permission for Java to silently borrow source positions. Independent target detection remains required unless a reviewer explicitly approves a source-assisted resolution.",
  "",
  "## Files",
  "", .md_table(file_inventory), "",
  "## Input reads", "", .md_table(file_io_df), "",
  "## Positional layouts declared by R", "", .md_table(positional_df), "",
  "## Field groups", "", .md_table(field_groups_df), "",
  "## Function defaults", "", .md_table(function_defaults_df), "",
  "## Hard-coded indices", "", .md_table(hardcoded_indices_df), "",
  "## Findings", "", .md_table(findings_df), "",
  "## Column usage", "", .md_table(column_usage_df, 250L), ""
)
writeLines(md, file.path(.out_dir, "r_source_contract.md"), useBytes = TRUE)

cat("OCM R Source Detector complete.\n")
cat("R files:", length(.r_files), "\n")
cat("Input reads:", nrow(file_io_df), "\n")
cat("Positional fields:", nrow(positional_df), "\n")
cat("Column usages:", nrow(column_usage_df), "\n")
cat("Hard-coded indices:", nrow(hardcoded_indices_df), "\n")
cat("Findings:", nrow(findings_df), "\n")
cat("Output:", .out_dir, "\n")
