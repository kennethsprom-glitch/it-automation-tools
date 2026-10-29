#!/usr/bin/env python3
"""Clean a TMS-generated QuickBooks IIF invoice export so it imports cleanly.

Fixes:
  * long TMS item names -> QuickBooks item codes (QB error 11585 "Item does not exist")
  * quoted/unknown values in the CLASS column        (QB error 3140 invalid Class reference)
  * TERMS written as a term QuickBooks has (default Net 30) and DUEDATE set to
    DATE plus the number of days in that term       (QB error 11710 "Terms does not exist")
  * invoice dates in a closed period (--date) and due-date recompute (--terms-days)
  * 2-digit-year due dates -> 4-digit
"""
import argparse, json, re, sys
from datetime import datetime, timedelta

VERSION = "1.1.0"
DEFAULT_TERMS = "Net 30"
_TERMS_COLUMNS = ("DATE", "DUEDATE", "TERMS")

DEFAULT_ITEM_MAP = {
    "Drayage": "DR",
    "Fuel Surcharge": "FS",
    "PRE PULL": "PRE",
    "PER DIEM": "PD",
    "Chassis Rental": "CHR",
}


def four_digit_year(d):
    d = d.strip()
    if not d:
        return d
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(d, fmt).strftime("%m/%d/%Y")
        except ValueError:
            pass
    return d


def days_in_terms(terms):
    """Return the day count named by a term such as 'Net 30'."""
    numbers = re.findall(r"\d+", terms or "")
    if not numbers:
        return None
    return int(numbers[-1])


def _warn(warnings, message):
    if message not in warnings:
        warnings.append(message)
        print(message, file=sys.stderr)


def fix_lines(lines, item_map=None, keep_class=None, date=None, terms_days=None, terms=None, warnings=None):
    item_map = DEFAULT_ITEM_MAP if item_map is None else item_map
    terms = DEFAULT_TERMS if terms is None else str(terms).strip() or DEFAULT_TERMS
    if warnings is None:
        warnings = []
    keep = set(keep_class or [])
    headers = {}
    warned_headers = set()
    offset = days_in_terms(terms)
    if offset is None:
        _warn(
            warnings,
            f"warning: terms {terms!r} does not name a number of days; TRNS due dates were left unchanged",
        )
    # --date together with --terms-days is the existing closed-period redate.
    # That pair still decides DUEDATE. The terms name is written either way.
    closed_period_due = bool(date) and terms_days is not None
    out = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        cols = line.split("\t")
        tag = cols[0]
        if tag.startswith("!"):
            headers[tag[1:]] = cols
            out.append(line)
            continue
        hdr = headers.get(tag)
        if not hdr:
            if tag == "TRNS":
                _warn(
                    warnings,
                    "warning: missing !TRNS header; the terms fix was not applied",
                )
            out.append(line)
            continue
        cols += [""] * (len(hdr) - len(cols))
        idx = {name: i for i, name in enumerate(hdr)}

        if "CLASS" in idx:
            c = cols[idx["CLASS"]].strip().strip('"')
            cols[idx["CLASS"]] = c if c in keep else ""
        if "INVITEM" in idx:
            it = cols[idx["INVITEM"]]
            cols[idx["INVITEM"]] = item_map.get(it, it)
        if date and "DATE" in idx:
            cols[idx["DATE"]] = date
        if "DUEDATE" in idx:
            if date and terms_days is not None:
                due = datetime.strptime(date, "%m/%d/%Y") + timedelta(days=terms_days)
                cols[idx["DUEDATE"]] = due.strftime("%m/%d/%Y")
            else:
                cols[idx["DUEDATE"]] = four_digit_year(cols[idx["DUEDATE"]])
        if tag == "TRNS":
            missing = [name for name in _TERMS_COLUMNS if name not in idx]
            if missing:
                if id(hdr) not in warned_headers:
                    warned_headers.add(id(hdr))
                    names = ", ".join(missing)
                    label = "column" if len(missing) == 1 else "columns"
                    _warn(
                        warnings,
                        f"warning: missing {label} {names}; the terms fix was not applied",
                    )
            else:
                cols[idx["TERMS"]] = terms
                if offset is not None and not closed_period_due:
                    invoice = four_digit_year(cols[idx["DATE"]].strip())
                    try:
                        parsed = datetime.strptime(invoice, "%m/%d/%Y")
                    except ValueError:
                        shown = cols[idx["DATE"]]
                        _warn(
                            warnings,
                            f"warning: could not read TRNS DATE {shown!r}; DUEDATE was left unchanged",
                        )
                    else:
                        cols[idx["DUEDATE"]] = (parsed + timedelta(days=offset)).strftime("%m/%d/%Y")
        if tag == "TRNS":
            rendered = "\t".join(cols)
        elif tag == "SPL" and "CLASS" in idx:
            # Keep a blank CLASS column (a trailing tab). Still drop empty columns after it.
            end = len(cols)
            keep_through = idx["CLASS"] + 1
            while end > keep_through and cols[end - 1] == "":
                end -= 1
            rendered = "\t".join(cols[:end])
        else:
            rendered = "\t".join(cols).rstrip("\t")
        out.append(rendered)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--map", help="JSON file of {TMS item name: QB item code}")
    ap.add_argument("--keep-class", action="append", default=[],
                    help="class value that exists in QuickBooks and should be kept (repeatable)")
    ap.add_argument("--date", help="rewrite invoice/line dates to MM/DD/YYYY")
    ap.add_argument("--terms-days", type=int,
                    help="with --date, recompute the due date as that date plus N days "
                         "(overrides the day count in --terms)")
    ap.add_argument("--terms", default=DEFAULT_TERMS,
                    help="terms name written on every TRNS line (default: Net 30). "
                         "The due date is DATE plus the number of days in the name")
    a = ap.parse_args(argv)
    if a.date:
        datetime.strptime(a.date, "%m/%d/%Y")
    item_map = DEFAULT_ITEM_MAP
    if a.map:
        with open(a.map) as f:
            item_map = json.load(f)
    with open(a.input, newline="") as f:
        lines = f.readlines()
    out = fix_lines(lines, item_map, a.keep_class, a.date, a.terms_days, terms=a.terms)
    with open(a.output, "w", newline="") as f:
        f.write("\r\n".join(out) + "\r\n")
    print(f"Wrote {a.output} ({len(out)} lines)", file=sys.stderr)


if __name__ == "__main__":
    main()
