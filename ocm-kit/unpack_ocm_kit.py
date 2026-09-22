#!/usr/bin/env python3
"""
Unpack an OCM kit bundle into a directory tree.

    python unpack_ocm_kit.py ocm_run_kit.md              # -> ./ocm-kit
    python unpack_ocm_kit.py ocm_run_kit.md my-dir       # -> ./my-dir
    python unpack_ocm_kit.py ocm_run_kit.md --list       # show contents only

A file in the bundle starts at a line beginning with BEGIN and ends at the
next line beginning with FINIS. Everything between is written verbatim.
"""
import io
import os
import sys

BEGIN = "<<<<<<<<<< OCM-KIT FILE: "
FINIS = "<<<<<<<<<< OCM-KIT END"


def parse(text):
    """Return [(relative_path, contents), ...] in bundle order."""
    items, name, buf = [], None, []
    for line in text.split("\n"):
        if line.startswith(BEGIN):
            name, buf = line[len(BEGIN):].strip(), []
        elif line.startswith(FINIS):
            if name is not None:
                items.append((name, "\n".join(buf)))
            name, buf = None, []
        elif name is not None:
            buf.append(line)
    if name is not None:
        raise SystemExit("bundle truncated: no END marker for %r" % name)
    return items


def main(argv):
    if not argv:
        raise SystemExit(__doc__.strip())
    bundle = argv[0]
    rest = argv[1:]
    listing = "--list" in rest
    target = next((a for a in rest if not a.startswith("-")), "ocm-kit")

    with io.open(bundle, "r", encoding="utf-8") as fh:
        items = parse(fh.read())
    if not items:
        raise SystemExit("no files found in %s -- are the markers intact?" % bundle)

    if listing:
        for name, body in items:
            print("%8d  %s" % (len(body.encode("utf-8")), name))
        print("%d files" % len(items))
        return 0

    for name, body in items:
        path = os.path.join(target, *name.split("/"))
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body if body.endswith("\n") else body + "\n")
    print("extracted %d files into %s" % (len(items), os.path.abspath(target)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
