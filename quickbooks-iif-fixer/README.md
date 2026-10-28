# QuickBooks IIF Fixer

A small Python 3 CLI that cleans up invoice exports produced by a trucking TMS so QuickBooks Desktop will import them (File > Utilities > Import > IIF Files).

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
