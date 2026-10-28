# Trinium to GSL IIF Fix

Cleans up invoice exports from Trinium so QuickBooks Desktop will import them (File > Utilities > Import > IIF Files).

## Windows app

The app is named **Trinium to GSL IIF Fix**. The file to download is `Trinium-to-GSL-IIF-Fix.exe`.

1. Open the [Releases](https://github.com/kennethsprom-glitch/it-automation-tools/releases) page for this repository.
2. On the release named **Trinium to GSL IIF Fix**, download `Trinium-to-GSL-IIF-Fix.exe`.
3. Double-click the file. If Windows says it protected your PC, choose **More info**, then **Run anyway**. The file is not code-signed.
4. Click **Choose file** and pick the `.iif` export.
5. The box labeled **Fixed file to save** fills in next to the original, with `_fixed` added to the name. The original file is not changed.
6. Leave the other boxes as they are unless QuickBooks rejected the file:
   - **New invoice date**: only if QuickBooks says the accounting period is closed. Use `MM/DD/YYYY`.
   - **Terms days**: usually `30`. This is used only together with a new invoice date, to set the due date.
   - **Item list file**: leave empty to use the built-in item names. Choose a JSON file only when accounting supplies a different list.
   - **Classes to keep**: leave empty, or type class names that already exist in QuickBooks, separated by commas (for example `OPS`). Every other class is cleared.
7. Click **Fix file**. The notes at the bottom list item names that were mapped, classes that were cleared, and dates that changed.
8. In QuickBooks, import the `_fixed` file. Try that import on a backup company file first.

GitHub Actions builds this exe on `windows-latest` after the tests pass. Pushing a tag such as `v1.0.0` publishes `Trinium-to-GSL-IIF-Fix.exe` on a public release named **Trinium to GSL IIF Fix**. The same workflow can be started by hand from the Actions tab; that builds the exe and does not publish a release.

To open the same window from source on a machine that has Python and Tkinter:

```bash
python3 fix_iif_gui.py
```

## Errors it fixes

| QuickBooks error | Cause | Fix |
|---|---|---|
| **11585 – Item does not exist** | The TMS writes long charge names (`Fuel Surcharge`, `PER DIEM`) in `INVITEM`, which don't match QuickBooks item names. | Maps each name to a QuickBooks item code via a JSON mapping. |
| **3140 – Invalid Class reference** | The TMS puts charge codes in the `CLASS` column, wrapped in quotes (`"FS"`), which aren't classes in QuickBooks. | Strips quotes and blanks any class not passed with `--keep-class`. |
| **Closed-period date** | Invoice dates fall in a period that's already closed in QuickBooks. | `--date MM/DD/YYYY` rewrites invoice and line dates; `--terms-days N` recomputes the due date. |
| Ambiguous due dates | Due dates exported as `MM/DD/YY`. | Converted to `MM/DD/YYYY`. |

## Usage

```bash
python3 fix_iif.py samples/sample_export.iif fixed.iif
python3 fix_iif.py export.iif fixed.iif --map item_map.example.json --keep-class OPS
python3 fix_iif.py export.iif fixed.iif --date 03/02/2026 --terms-days 30
```

`samples/` holds a made-up export (fictional customer "Acme Imports") and the expected outputs. Always test an import on a backup company file first.

## Tests

```bash
pip install pytest
pytest -q
```
