"""Run fix_iif.fix_lines with an explicit file encoding.

Same write path as fix_iif.main: universal newlines in, CRLF out.
The encoding argument is how the Windows app reads an ANSI export
(cp1252) or how a byte-preserving read (latin-1) behaves.
"""
import json
import sys
from pathlib import Path

FIXER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIXER))
import fix_iif


def main():
    opts = json.loads(sys.argv[1])
    src = Path(sys.argv[2])
    dest = Path(sys.argv[3])
    encoding = sys.argv[4]
    with open(src, encoding=encoding, newline="") as handle:
        lines = handle.readlines()
    warnings = []
    kwargs = {"warnings": warnings}
    if opts.get("terms") is not None:
        kwargs["terms"] = opts["terms"]
    if opts.get("date"):
        kwargs["date"] = opts["date"]
    if "termsDays" in opts and opts["termsDays"] is not None:
        kwargs["terms_days"] = opts["termsDays"]
    if opts.get("keepClass"):
        kwargs["keep_class"] = opts["keepClass"]
    if "itemMap" in opts and opts["itemMap"] is not None:
        kwargs["item_map"] = opts["itemMap"]
    out = fix_iif.fix_lines(lines, **kwargs)
    with open(dest, "w", encoding=encoding, newline="") as handle:
        handle.write("\r\n".join(out) + "\r\n")
    json.dump(warnings, sys.stdout)


if __name__ == "__main__":
    main()
