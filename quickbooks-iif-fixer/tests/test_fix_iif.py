import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import fix_iif

SAMPLE = HERE / "samples" / "sample_export.iif"


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
    assert all(len(row) <= 13 or row[13] == "" for row in spl)


def test_items_mapped():
    items = [r[11] for r in rows(run(), "SPL")]
    assert items == ["DR", "FS", "PD"]


def test_class_cleared_and_unquoted():
    out = run(keep_class=["OPS"])
    assert rows(out, "TRNS")[0][17] == "OPS"
    assert all(len(r) <= 13 or r[13] == "" for r in rows(out, "SPL"))
    assert '"' not in "\n".join(run())


def test_due_date_four_digit_year():
    assert rows(run(), "TRNS")[0][11] == "02/04/2026"


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
