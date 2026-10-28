import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import fix_iif_gui as gui

SAMPLE = HERE / "samples" / "sample_export.iif"
EXPECTED = HERE / "samples" / "expected_output.iif"
EXPECTED_REDATED = HERE / "samples" / "expected_output_redated.iif"
EXAMPLE_MAP = HERE / "item_map.example.json"


def test_app_name():
    assert gui.APP_NAME == "Trinium to GSL IIF Fix"


def test_default_output_sits_next_to_input(tmp_path):
    source = tmp_path / "invoice.iif"
    assert gui.default_output_path(str(source)) == str(tmp_path / "invoice_fixed.iif")


def test_parse_helpers():
    assert gui.parse_keep_classes("  OPS, \"DRAY\" , ,") == ["OPS", "DRAY"]
    assert gui.parse_keep_classes("") == []
    assert gui.parse_optional_date("  ") is None
    assert gui.parse_optional_date("03/02/2026") == "03/02/2026"
    with pytest.raises(ValueError):
        gui.parse_optional_date("3/2/2026")
    with pytest.raises(ValueError):
        gui.parse_optional_date("02/31/2026")
    assert gui.parse_terms_days("") == 30
    assert gui.parse_terms_days(" 15 ") == 15
    with pytest.raises(ValueError):
        gui.parse_terms_days("thirty")
    assert gui.load_item_map("") is None
    assert gui.load_item_map(str(EXAMPLE_MAP))["Fuel Surcharge"] == "FSC"


def test_apply_fix_matches_sample(tmp_path):
    target = tmp_path / "invoice_fixed.iif"
    report = gui.apply_fix(str(SAMPLE), str(target))
    assert target.read_bytes() == EXPECTED.read_bytes()
    assert "Saved " in report
    assert "Drayage to DRAY" in report
    assert "Fuel Surcharge to FSC" in report
    assert "PER DIEM to PERDIEM" in report
    assert "Items mapped: 3" in report
    assert "Classes cleared: 4" in report
    assert '"OPS" removed' in report
    assert "Dates changed: 1" in report
    assert "Due date 02/04/26 to 02/04/2026" in report


def test_apply_fix_with_map_date_and_kept_class(tmp_path):
    target = tmp_path / "redated.iif"
    report = gui.apply_fix(
        str(SAMPLE),
        str(target),
        date_text="03/02/2026",
        terms_text="",
        map_path=str(EXAMPLE_MAP),
        keep_text="OPS",
    )
    text = target.read_text(encoding="utf-8")
    assert "DRAY" in text and "FSC" in text and "PERDIEM" in text
    assert "03/02/2026" in text and "04/01/2026" in text
    assert "\tOPS\t" in text
    assert "Classes kept: 1" in report
    assert "OPS (1 line)" in report
    assert '"OPS" removed' not in report
    assert "Invoice date 01/05/2026 to 03/02/2026" in report
    assert "Due date 02/04/26 to 04/01/2026" in report


def test_redate_without_a_kept_class_matches_sample(tmp_path):
    target = tmp_path / "redated.iif"
    gui.apply_fix(str(SAMPLE), str(target), date_text="03/02/2026", terms_text="30")
    assert target.read_bytes() == EXPECTED_REDATED.read_bytes()


def test_apply_fix_errors_do_not_write(tmp_path):
    target = tmp_path / "out.iif"
    with pytest.raises(ValueError, match="invoice file first"):
        gui.apply_fix("", str(target))
    source = tmp_path / "sample.iif"
    source.write_bytes(SAMPLE.read_bytes())
    with pytest.raises(ValueError, match="original"):
        gui.apply_fix(str(source), str(source))
    with pytest.raises(ValueError, match="folder"):
        gui.apply_fix(str(source), str(tmp_path / "missing" / "out.iif"), "03/02/2026", "30")
    bad_map = tmp_path / "bad.json"
    bad_map.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        gui.apply_fix(str(source), str(target), map_path=str(bad_map))
    with pytest.raises(ValueError, match="MM/DD/YYYY"):
        gui.apply_fix(str(source), str(target), date_text="March 2 2026")
    assert not target.exists()


def test_workflow_publishes_named_exe():
    workflow = (ROOT / ".github" / "workflows" / "trinium-to-gsl-iif-fix.yml").read_text(encoding="utf-8")
    assert "windows-latest" in workflow
    assert "workflow_dispatch" in workflow
    assert "contents: write" in workflow
    assert "Trinium-to-GSL-IIF-Fix.exe" in workflow
    assert 'title "Trinium to GSL IIF Fix"' in workflow or "Trinium to GSL IIF Fix" in workflow
    assert "v*" in workflow
    assert "GITHUB_TOKEN" in workflow
    assert "pytest" in workflow
    assert "--onefile" in workflow
    assert "--windowed" in workflow


def test_window_fills_output_and_reports(tmp_path, monkeypatch):
    pytest.importorskip("tkinter")
    import tkinter as tk
    from tkinter import messagebox, scrolledtext
    from tkinter import filedialog

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")

    gui.tk = tk
    gui.filedialog = filedialog
    gui.messagebox = messagebox
    gui.scrolledtext = scrolledtext
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: False)

    try:
        root.title("check")
        app = gui.App(root)
        assert root.title() == "check"
        app.root.title(gui.APP_NAME)
        source = tmp_path / "sample_export.iif"
        source.write_bytes(SAMPLE.read_bytes())
        app.input_var.set(str(source))
        root.update_idletasks()
        assert app.output_var.get() == str(tmp_path / "sample_export_fixed.iif")
        assert app.terms_var.get() == "30"
        app.fix_file()
        log = app.log.get("1.0", "end")
        assert "Items mapped: 3" in log
        assert "Classes cleared: 4" in log
        assert "Dates changed: 1" in log
        assert pathlib.Path(app.output_var.get()).read_bytes() == EXPECTED.read_bytes()

        app.fix_file()
        assert "left as it is" in app.log.get("1.0", "end")

        app.input_var.set("")
        app.output_var.set("")
        app.fix_file()
        assert "Choose the invoice file first." in app.log.get("1.0", "end")
    finally:
        root.destroy()
