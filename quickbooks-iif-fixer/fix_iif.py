#!/usr/bin/env python3
"""Clean a TMS-generated QuickBooks IIF invoice export so it imports cleanly.

Fixes:
  * long TMS item names -> QuickBooks item codes (QB error 11585 "Item does not exist")
  * quoted/unknown values in the CLASS column        (QB error 3140 invalid Class reference)
  * invoice dates in a closed period (--date) and due-date recompute (--terms-days)
  * 2-digit-year due dates -> 4-digit
"""
import argparse, json, sys
from datetime import datetime, timedelta

DEFAULT_ITEM_MAP = {
    "Drayage": "DRAY",
    "Fuel Surcharge": "FSC",
    "PRE PULL": "PREPULL",
    "PER DIEM": "PERDIEM",
    "Chassis Rental": "CHASSIS",
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


def fix_lines(lines, item_map=None, keep_class=None, date=None, terms_days=None):
    item_map = DEFAULT_ITEM_MAP if item_map is None else item_map
    keep = set(keep_class or [])
    headers = {}
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
        out.append("\t".join(cols).rstrip("\t") if tag != "TRNS" else "\t".join(cols))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--map", help="JSON file of {TMS item name: QB item code}")
    ap.add_argument("--keep-class", action="append", default=[],
                    help="class value that exists in QuickBooks and should be kept (repeatable)")
    ap.add_argument("--date", help="rewrite invoice/line dates to MM/DD/YYYY")
    ap.add_argument("--terms-days", type=int, help="recompute due date as DATE + N days (needs --date)")
    a = ap.parse_args(argv)
    if a.date:
        datetime.strptime(a.date, "%m/%d/%Y")
    item_map = DEFAULT_ITEM_MAP
    if a.map:
        with open(a.map) as f:
            item_map = json.load(f)
    with open(a.input, newline="") as f:
        lines = f.readlines()
    out = fix_lines(lines, item_map, a.keep_class, a.date, a.terms_days)
    with open(a.output, "w", newline="") as f:
        f.write("\r\n".join(out) + "\r\n")
    print(f"Wrote {a.output} ({len(out)} lines)", file=sys.stderr)


if __name__ == "__main__":
    main()
