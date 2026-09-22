#!/usr/bin/env python3
# Controller barrier scanner (protocol §2). Mechanical, leak-validated.
# Scans artifacts that cross source -> target for source-language syntax.
import re, sys, json

PATTERNS = [
    (r"<-", "assignment arrow"),
    (r"%>%|%in%|%\|\|%", "percent operator"),
    (r"\b(sapply|lapply|vapply|mapply|tapply|do\.call|rbind|cbind)\s*\(", "apply/bind call"),
    (r"\bfunction\s*\(", "function literal"),
    (r"\b(read\.table|read_excel|read\.csv|splinefun|write\.xlsx|excel_sheets|datatable|formatStyle|styleEqual|pivot_longer|ggplot|aes)\s*\(", "source API call"),
    (r"\b(data\.frame|stringsAsFactors|na\.rm|check\.names|drop\s*=\s*FALSE)\b", "source API idiom"),
    (r"[A-Za-z_.\]]\$[A-Za-z_.`]", "dollar column access"),
    (r"\blibrary\s*\(|\brequire(Namespace)?\s*\(", "package load"),
    (r"\[\[\s*\"?[A-Za-z0-9_.]+\"?\s*\]\]", "double-bracket index"),
    # Boolean.TRUE / Boolean.FALSE are Java constants, not source-language
    # literals (adjudicated false positive, 2026-08-29).
    (r"\bNULL\b|(?<!Boolean\.)\bTRUE\b|(?<!Boolean\.)\bFALSE\b|\bNA_real_\b|\bNA_character_\b", "source literal token"),
    (r"\bifelse\s*\(|\bpaste0?\s*\(|\bsprintf\s*\(|\bsuppressWarnings\s*\(", "source builtin call"),
    # R shape only: `for (x in seq)` — the char after `in ` must not be `:`
    # (Java's enhanced-for with a variable literally named `in`, `for (T in : c)`,
    # tripped the earlier version: an R18 false positive on sound input,
    # adjudicated + fixed 2026-08-29, recorded in the evidence bundle).
    (r"\bfor\s*\(\s*[A-Za-z_.]+\s+in\s+[^:\s)]", "for-in loop header"),
]

LEAK = 'comfortable <- sapply(valuation_by_year, function(df) sum(df$DaBetrag, na.rm=TRUE))'

def scan_text(text):
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for pat, name in PATTERNS:
            m = re.search(pat, line)
            if m:
                hits.append((i, name, m.group(0), line.strip()[:110]))
    return hits

def main():
    # 1) validate the detector by injecting the protocol's own leak line
    leak_hits = scan_text(LEAK)
    fired = {name for _, name, _, _ in leak_hits}
    print("leak-injection validation: %d patterns fired: %s" % (len(fired), sorted(fired)))
    if len(fired) < 4:
        print("DETECTOR INVALID — fewer than 4 patterns on the known leak"); sys.exit(2)
    # 2) scan the artifacts
    rc = 0
    for path in sys.argv[1:]:
        text = open(path, encoding="utf-8").read()
        hits = scan_text(text)
        if hits:
            rc = 1
            print("FAIL %s — %d hits:" % (path, len(hits)))
            for i, name, tok, ctx in hits[:25]:
                print("   line %d [%s] %r :: %s" % (i, name, tok, ctx))
            if len(hits) > 25: print("   ... (%d more; list truncated — full count above)" % (len(hits) - 25))
        else:
            print("CLEAN %s (0 hits; detector validated this run)" % path)
    sys.exit(rc)

main()
