#!/usr/bin/env python3
"""Trinium to GSL IIF Fix: a plain window around the QuickBooks IIF fixer.

The cleanup rules live in fix_iif.py. This file only collects choices and
reports what changed.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import fix_iif

APP_NAME = "Trinium to GSL IIF Fix"

tk = None
filedialog = None
messagebox = None
scrolledtext = None


def default_output_path(input_path):
    path = Path(input_path)
    return str(path.with_name(path.stem + "_fixed.iif"))


def parse_keep_classes(text):
    classes = []
    for part in (text or "").split(","):
        name = part.strip().strip('"')
        if name:
            classes.append(name)
    return classes


def parse_optional_date(text):
    text = (text or "").strip()
    if not text:
        return None
    if len(text) != 10 or text[2] != "/" or text[5] != "/":
        raise ValueError("Enter the new date as MM/DD/YYYY, for example 03/02/2026.")
    try:
        datetime.strptime(text, "%m/%d/%Y")
    except ValueError:
        raise ValueError(
            "That date is not a real calendar day. Use MM/DD/YYYY, for example 03/02/2026."
        )
    return text


def parse_terms_days(text):
    text = (text or "").strip()
    if not text:
        return 30
    if not text.isdigit():
        raise ValueError("Terms days should be a whole number such as 30.")
    days = int(text)
    if days > 3650:
        raise ValueError("Terms days looks too large. Use a number such as 30.")
    return days


def load_item_map(path):
    path = (path or "").strip()
    if not path:
        return None
    file = Path(path)
    if not file.is_file():
        raise ValueError(
            "That item list could not be found. Leave the box empty to use the built-in list."
        )
    try:
        with open(file, encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        raise ValueError(
            "That item list is not valid JSON. Leave the box empty to use the built-in list."
        )
    if not isinstance(data, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in data.items()
    ):
        raise ValueError(
            'The item list must look like {"Fuel Surcharge": "FS"}. '
            "Leave the box empty to use the built-in list."
        )
    return data


def _data_rows(lines):
    headers = {}
    rows = []
    for raw in lines:
        cols = raw.rstrip("\r\n").split("\t")
        tag = cols[0] if cols else ""
        if tag.startswith("!"):
            headers[tag[1:]] = cols
            continue
        header = headers.get(tag)
        if not header:
            continue
        if len(cols) < len(header):
            cols = cols + [""] * (len(header) - len(cols))
        rows.append((cols, {name: index for index, name in enumerate(header)}))
    return rows


def _tally(pairs):
    order = []
    counts = {}
    for pair in pairs:
        if pair not in counts:
            order.append(pair)
            counts[pair] = 0
        counts[pair] += 1
    return [(item, counts[item]) for item in order]


def _lines_word(count):
    return "1 line" if count == 1 else f"{count} lines"


def summarize_changes(original_lines, fixed_lines):
    before = _data_rows(original_lines)
    after = _data_rows(fixed_lines)
    items = []
    cleared = []
    kept = []
    dates = []
    for (left, left_idx), (right, right_idx) in zip(before, after):
        if "INVITEM" in left_idx and "INVITEM" in right_idx:
            old = left[left_idx["INVITEM"]]
            new = right[right_idx["INVITEM"]]
            if old != new:
                items.append((old, new))
        if "CLASS" in left_idx and "CLASS" in right_idx:
            old = left[left_idx["CLASS"]]
            new = right[right_idx["CLASS"]]
            if old != new:
                if new == "":
                    cleared.append(old or "(blank)")
                else:
                    kept.append(new)
        for field, label in (("DATE", "Invoice date"), ("DUEDATE", "Due date")):
            if field in left_idx and field in right_idx:
                old = left[left_idx[field]]
                new = right[right_idx[field]]
                if old != new:
                    dates.append((label, old, new))

    sections = [f"Items mapped: {len(items)}"]
    if items:
        for (old, new), count in _tally(items):
            sections.append(f"  {old} to {new} ({_lines_word(count)})")
    else:
        sections.append("  No item names needed a change.")

    sections.append("")
    sections.append(f"Classes cleared: {len(cleared)}")
    if cleared:
        for old, count in _tally(cleared):
            sections.append(f"  {old} removed ({_lines_word(count)})")
    else:
        sections.append("  No classes needed to be cleared.")
    if kept:
        sections.append(f"Classes kept: {len(kept)}")
        for name, count in _tally(kept):
            sections.append(f"  {name} ({_lines_word(count)})")

    sections.append("")
    sections.append(f"Dates changed: {len(dates)}")
    if dates:
        for (label, old, new), count in _tally(dates):
            sections.append(f"  {label} {old} to {new} ({_lines_word(count)})")
    else:
        sections.append("  No dates needed a change.")

    if len(before) != len(after):
        sections.append("")
        sections.append("Some lines could not be compared. Check the saved file before importing it.")
    return "\n".join(sections)


def apply_fix(input_path, output_path, date_text="", terms_text="30", map_path="", keep_text=""):
    input_path = (input_path or "").strip()
    output_path = (output_path or "").strip()
    if not input_path:
        raise ValueError("Choose the invoice file first.")
    source = Path(input_path)
    if not source.is_file():
        raise ValueError("That invoice file could not be found. Choose it again.")
    if not output_path:
        raise ValueError("Choose where to save the fixed file.")
    target = Path(output_path)
    if source.resolve() == target.resolve():
        raise ValueError(
            "Choose a different name for the fixed file so the original export is kept."
        )
    if not target.parent.exists():
        raise ValueError("The folder for the fixed file does not exist. Choose another location.")

    date = parse_optional_date(date_text)
    terms = parse_terms_days(terms_text) if date else None
    item_map = load_item_map(map_path)
    keep = parse_keep_classes(keep_text)

    with open(source, newline="") as handle:
        original = handle.readlines()
    if not any(line.lstrip("\ufeff").startswith("!TRNS") for line in original):
        raise ValueError(
            "That file does not look like a QuickBooks IIF invoice. Choose the .iif export."
        )

    fixed = fix_iif.fix_lines(
        original,
        item_map=item_map,
        keep_class=keep,
        date=date,
        terms_days=terms,
    )
    with open(target, "w", newline="") as handle:
        handle.write("\r\n".join(fixed) + "\r\n")
    return f"Saved {target}\n\n{summarize_changes(original, fixed)}"


class App:
    def __init__(self, root):
        self.root = root
        self.output_is_automatic = True
        self._setting_output = False

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.terms_var = tk.StringVar(value="30")
        self.map_var = tk.StringVar()
        self.keep_var = tk.StringVar()

        self.input_var.trace_add("write", self._on_input_write)
        self.output_var.trace_add("write", self._on_output_write)

        outer = tk.Frame(root, padx=16, pady=12)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text=APP_NAME, font=("Segoe UI", 18, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            outer,
            text="Prepare a Trinium invoice export so QuickBooks Desktop can import it.",
            anchor="w",
            justify="left",
            wraplength=620,
        ).pack(fill="x", pady=(2, 10))

        self._file_row(outer, "Invoice file (.iif)", self.input_var, self.browse_input, "Choose file")
        self._hint(outer, "The .iif file exported from Trinium.")

        self._file_row(outer, "Fixed file to save", self.output_var, self.browse_output, "Save as")
        self._hint(outer, "Filled in next to the original, with _fixed in the name. The original file is not changed.")

        dates = tk.Frame(outer)
        dates.pack(fill="x", pady=(0, 8))
        left = tk.Frame(dates)
        right = tk.Frame(dates)
        left.pack(side="left", fill="x", expand=True, padx=(0, 12))
        right.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="New invoice date (optional)", anchor="w").pack(fill="x")
        tk.Entry(left, textvariable=self.date_var).pack(fill="x", ipady=2, pady=(2, 2))
        tk.Label(left, text="MM/DD/YYYY. Only if the period is closed.", fg="#444444", anchor="w").pack(fill="x")
        tk.Label(right, text="Terms days (optional)", anchor="w").pack(fill="x")
        tk.Entry(right, textvariable=self.terms_var).pack(fill="x", ipady=2, pady=(2, 2))
        tk.Label(right, text="Default 30. Used with the new date.", fg="#444444", anchor="w").pack(fill="x")

        self._file_row(outer, "Item list file (optional JSON)", self.map_var, self.browse_map, "Choose file")
        self._hint(outer, "Leave empty to use the built-in item names.")

        tk.Label(outer, text="Classes to keep (optional)", anchor="w").pack(fill="x")
        tk.Entry(outer, textvariable=self.keep_var).pack(fill="x", ipady=2, pady=(2, 2))
        self._hint(
            outer,
            "Comma-separated class names that exist in QuickBooks, for example OPS. Other classes are cleared.",
        )

        self.fix_button = tk.Button(
            outer,
            text="Fix file",
            command=self.fix_file,
            font=("Segoe UI", 16, "bold"),
            bg="#0b6e4f",
            fg="white",
            activebackground="#095c42",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
        )
        self.fix_button.pack(fill="x", pady=(4, 0))

        tk.Label(outer, text="What happened", anchor="w").pack(fill="x", pady=(12, 2))
        self.log = scrolledtext.ScrolledText(outer, height=11, wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        self.set_log("Choose the .iif file, then click Fix file.")

    def _hint(self, parent, text):
        tk.Label(parent, text=text, fg="#444444", anchor="w", justify="left", wraplength=620).pack(
            fill="x", pady=(0, 8)
        )

    def _file_row(self, parent, label, variable, command, button_text):
        tk.Label(parent, text=label, anchor="w").pack(fill="x")
        row = tk.Frame(parent)
        row.pack(fill="x", pady=(2, 2))
        tk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, ipady=2)
        tk.Button(row, text=button_text, command=command).pack(side="left", padx=(8, 0))

    def _set_automatic_output(self, value):
        self._setting_output = True
        self.output_var.set(value)
        self._setting_output = False
        self.output_is_automatic = True

    def _on_input_write(self, *_args):
        if not self.output_is_automatic:
            return
        path = self.input_var.get().strip()
        self._set_automatic_output(default_output_path(path) if path else "")

    def _on_output_write(self, *_args):
        if not self._setting_output:
            self.output_is_automatic = False

    def set_log(self, text):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", text)
        self.log.configure(state="disabled")

    def browse_input(self):
        path = filedialog.askopenfilename(
            title="Choose the invoice export",
            filetypes=[("QuickBooks IIF", "*.iif"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)

    def browse_output(self):
        initial = self.output_var.get().strip()
        initial_path = Path(initial) if initial else None
        path = filedialog.asksaveasfilename(
            title="Save the fixed file",
            defaultextension=".iif",
            filetypes=[("QuickBooks IIF", "*.iif"), ("All files", "*.*")],
            initialfile=initial_path.name if initial_path else "",
            initialdir=str(initial_path.parent) if initial_path else "",
        )
        if path:
            self.output_var.set(path)

    def browse_map(self):
        path = filedialog.askopenfilename(
            title="Choose an item list",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.map_var.set(path)

    def fix_file(self):
        output = self.output_var.get().strip()
        if output and Path(output).exists():
            replace = messagebox.askyesno(
                APP_NAME,
                "A file with that name already exists. Replace it?",
            )
            if not replace:
                self.set_log("The existing file was left as it is.")
                return
        try:
            report = apply_fix(
                self.input_var.get(),
                self.output_var.get(),
                self.date_var.get(),
                self.terms_var.get(),
                self.map_var.get(),
                self.keep_var.get(),
            )
        except ValueError as exc:
            self.set_log(str(exc))
            messagebox.showerror(APP_NAME, str(exc))
            return
        except OSError as exc:
            message = "The file could not be read or saved.\n\n" + str(exc)
            self.set_log(message)
            messagebox.showerror(APP_NAME, message)
            return
        self.set_log(report)
        messagebox.showinfo(
            APP_NAME,
            "The fixed file is ready.\n\nIn QuickBooks, choose File > Utilities > Import > IIF Files.",
        )


def run_app():
    global tk, filedialog, messagebox, scrolledtext
    try:
        import tkinter as tk_module
        from tkinter import filedialog as filedialog_module
        from tkinter import messagebox as messagebox_module
        from tkinter import scrolledtext as scrolledtext_module
    except ImportError:
        raise SystemExit(
            "Tkinter is not available. On Windows, use Trinium-to-GSL-IIF-Fix.exe instead."
        )
    tk = tk_module
    filedialog = filedialog_module
    messagebox = messagebox_module
    scrolledtext = scrolledtext_module

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("700x740")
    root.minsize(560, 640)
    App(root)
    root.mainloop()


def main():
    run_app()


if __name__ == "__main__":
    main()
