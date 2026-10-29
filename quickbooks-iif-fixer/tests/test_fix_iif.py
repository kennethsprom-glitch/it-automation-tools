import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import fix_iif

SAMPLE = HERE / "samples" / "sample_export.iif"
SAMPLE_NET45 = HERE / "samples" / "sample_net45.iif"
EXPECTED_NET45 = HERE / "samples" / "expected_output_net45.iif"


def rows(out, tag):
    return [l.split("\t") for l in out if l.split("\t")[0] == tag]


def run(**kw):
    return fix_iif.fix_lines(SAMPLE.read_text().splitlines(), **kw)


def test_default_item_map_is_the_gsl_codes():
    assert fix_iif.DEFAULT_ITEM_MAP == {
        "Drayage": "DR",
        "Fuel Surcharge": "FS",
        "PRE PULL": "PRE",
        "PER DIEM": "PD",
        "Chassis Rental": "CHR",
    }


def test_all_five_items_map_and_class_stays_blank():
    header = "!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tDOCNUM\tMEMO\tCLEAR\tPRICE\tINVITEM\tTAXABLE\tCLASS\tEXTRA"
    names = ["Drayage", "Fuel Surcharge", "PRE PULL", "PER DIEM", "Chassis Rental"]
    lines = [header]
    for index, name in enumerate(names, start=1):
        lines.append(
            f'SPL\t{index}\tINVOICE\t01/05/2026\t41000\tACME IMPORTS\t-10\t\tREF\tN\t\t{name}\tN\t"FS"'
        )
    out = fix_iif.fix_lines(lines)
    spl = rows(out, "SPL")
    assert [row[11] for row in spl] == ["DR", "FS", "PRE", "PD", "CHR"]
    assert all(row[13] == "" for row in spl)
    assert all(line.endswith("\t") and not line.endswith("\t\t") for line in out if line.startswith("SPL\t"))


def test_items_mapped():
    items = [r[11] for r in rows(run(), "SPL")]
    assert items == ["DR", "FS", "PD"]


def test_class_cleared_and_unquoted():
    out = run(keep_class=["OPS"])
    assert rows(out, "TRNS")[0][17] == "OPS"
    assert all(r[13] == "" for r in rows(out, "SPL"))
    assert all(line.endswith("\t") and not line.endswith("\t\t") for line in out if line.startswith("SPL\t"))
    assert '"' not in "\n".join(run())


def test_due_date_four_digit_year():
    row = rows(run(), "TRNS")[0]
    assert row[11] == "02/04/2026"
    assert row[19] == "Net 30"


def test_redate_and_terms():
    out = run(date="03/02/2026", terms_days=30)
    t = rows(out, "TRNS")[0]
    assert t[3] == "03/02/2026" and t[11] == "04/01/2026"
    assert all(r[3] == "03/02/2026" for r in rows(out, "SPL"))


def test_matches_expected_files(tmp_path):
    o = tmp_path / "o.iif"
    fix_iif.main([str(SAMPLE), str(o)])
    assert o.read_bytes() == (HERE / "samples" / "expected_output.iif").read_bytes()
    fix_iif.main([str(SAMPLE), str(o), "--date", "03/02/2026", "--terms-days", "30"])
    assert o.read_bytes() == (HERE / "samples" / "expected_output_redated.iif").read_bytes()


def _indexed(lines, tag):
    headers = {}
    found = []
    for line in lines:
        cols = line.split("\t")
        name = cols[0]
        if name.startswith("!"):
            headers[name[1:]] = cols
            continue
        header = headers.get(name)
        if name == tag and header:
            found.append({column: cols[i] if i < len(cols) else "" for i, column in enumerate(header)})
    return found


def test_net45_terms_and_due_dates_and_crlf(tmp_path, capsys):
    target = tmp_path / "fixed.iif"
    fix_iif.main([str(SAMPLE_NET45), str(target)])
    data = target.read_bytes()
    assert data == EXPECTED_NET45.read_bytes()
    assert data.endswith(b"\r\n")
    assert b"\n" not in data.replace(b"\r\n", b"")
    assert capsys.readouterr().err.count("warning:") == 0

    original = _indexed(SAMPLE_NET45.read_text().splitlines(), "TRNS")
    fixed = _indexed(data.decode().splitlines(), "TRNS")
    assert [row["TERMS"] for row in fixed] == ["Net 30", "Net 30"]
    # 10/29/2026 + 30 days rolls into November; 12/15/2026 + 30 days rolls into the next year.
    assert [row["DUEDATE"] for row in fixed] == ["11/28/2026", "01/14/2027"]
    assert [row["DATE"] for row in fixed] == ["10/29/2026", "12/15/2026"]
    for before, after in zip(original, fixed):
        for column, value in before.items():
            if column in ("TERMS", "DUEDATE", "CLASS"):
                continue
            assert after[column] == value
        assert before["CLASS"] == '"OPS"' or before["CLASS"] == '"FS"'
        assert after["CLASS"] == ""

    spl = _indexed(data.decode().splitlines(), "SPL")
    assert [row["INVITEM"] for row in spl] == ["DR", "FS", "PRE", "PD", "CHR", "DR"]
    assert all(row["CLASS"] == "" for row in spl)
    assert all(line.endswith("\t") and not line.endswith("\t\t") for line in data.decode().splitlines() if line.startswith("SPL\t"))


def test_terms_columns_are_found_by_header_name():
    # DATE, DUEDATE, and TERMS are not in the positions used by the sample export.
    lines = [
        "!TRNS\tTERMS\tMEMO\tDUEDATE\tCLASS\tDATE",
        'TRNS\tNet 45\tSAMPLE-NOTE\t12/13/2026\t"OPS"\t10/29/2026',
    ]
    out = fix_iif.fix_lines(lines)
    assert out[0] == lines[0]
    assert out[1].split("\t") == ["TRNS", "Net 30", "SAMPLE-NOTE", "11/28/2026", "", "10/29/2026"]


def test_due_date_year_rollover_uses_header_names():
    lines = [
        "!TRNS\tNAME\tDATE\tTERMS\tDUEDATE",
        "TRNS\tEXAMPLE FREIGHT CO\t12/15/2026\tNet 45\t01/29/2027",
    ]
    out = fix_iif.fix_lines(lines)
    assert out[1].split("\t") == ["TRNS", "EXAMPLE FREIGHT CO", "12/15/2026", "Net 30", "01/14/2027"]


def test_terms_flag_uses_the_day_count_in_the_name(tmp_path):
    target = tmp_path / "fixed.iif"
    fix_iif.main([str(SAMPLE_NET45), str(target), "--terms", "Net 15"])
    fixed = _indexed(target.read_text().splitlines(), "TRNS")
    assert [row["TERMS"] for row in fixed] == ["Net 15", "Net 15"]
    assert [row["DUEDATE"] for row in fixed] == ["11/13/2026", "12/30/2026"]
    assert [row["DATE"] for row in fixed] == ["10/29/2026", "12/15/2026"]


def test_closed_period_terms_days_still_sets_the_due_date():
    out = run(date="03/02/2026", terms_days=15, terms="Net 30")
    row = rows(out, "TRNS")[0]
    assert row[3] == "03/02/2026"
    assert row[11] == "03/17/2026"
    assert row[19] == "Net 30"
    assert all(line.split("\t")[3] == "03/02/2026" for line in out if line.startswith("SPL\t"))


def test_missing_terms_column_leaves_the_line_and_warns(capsys):
    lines = [
        "!TRNS\tDATE\tDUEDATE\tNAME",
        "TRNS\t10/29/2026\t12/13/2026\tACME HARBOR SAMPLE",
        "TRNS\t12/15/2026\t01/29/2027\tEXAMPLE FREIGHT CO",
    ]
    out = fix_iif.fix_lines(lines)
    assert out == lines
    err = capsys.readouterr().err
    assert err.count("warning:") == 1
    assert "TERMS" in err


def test_missing_date_or_duedate_skips_the_terms_fix(capsys):
    missing_date = [
        "!TRNS\tDUEDATE\tTERMS\tNAME",
        "TRNS\t12/13/2026\tNet 45\tACME HARBOR SAMPLE",
    ]
    assert fix_iif.fix_lines(missing_date) == missing_date
    missing_due = [
        "!TRNS\tDATE\tTERMS\tNAME",
        "TRNS\t10/29/2026\tNet 45\tEXAMPLE FREIGHT CO",
    ]
    assert fix_iif.fix_lines(missing_due) == missing_due
    err = capsys.readouterr().err
    assert "DATE" in err and "DUEDATE" in err
    assert err.count("warning:") == 2


def test_terms_without_a_day_count_does_not_move_the_due_date(capsys):
    lines = [
        "!TRNS\tDATE\tDUEDATE\tTERMS",
        "TRNS\t10/29/2026\t12/13/2026\tNet 45",
    ]
    out = fix_iif.fix_lines(lines, terms="Due on receipt")
    assert out[1].split("\t") == ["TRNS", "10/29/2026", "12/13/2026", "Due on receipt"]
    assert "warning:" in capsys.readouterr().err


def test_trns_without_a_header_is_unchanged(capsys):
    lines = ["TRNS\t10/29/2026\tNet 45\t12/13/2026"]
    assert fix_iif.fix_lines(lines) == lines
    assert "warning:" in capsys.readouterr().err


def test_default_run_does_not_warn(capsys):
    run()
    assert "warning:" not in capsys.readouterr().err
