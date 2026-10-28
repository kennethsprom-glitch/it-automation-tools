# IT automation tools for a logistics operation

Hi, I'm Ken Prom. I handle IT for a trucking/logistics company, and these are cleaned-up versions of small tools I built to save the office time. All data in this repo is fake placeholder data.

## Projects

- **[directory-site/](directory-site/)**: a single-file static staff phone directory with search, plus Employees, Departments and Phone numbers views and a detail popup for each person. Plain HTML, CSS and JavaScript, no build step. Open `index.html` in a browser.
- **[quickbooks-iif-fixer/](quickbooks-iif-fixer/)**: **Trinium to GSL IIF Fix**, a Windows app that repairs Trinium QuickBooks IIF invoice exports (item-name mapping, class cleanup, closed-period re-dating, due-date fixes). Download `Trinium-to-GSL-IIF-Fix.exe` from the release named Trinium to GSL IIF Fix on [Releases](https://github.com/kennethsprom-glitch/it-automation-tools/releases). The same folder has the Python CLI and pytest tests.

## Tech used

HTML, CSS, vanilla JavaScript, Python 3 (standard library, including Tkinter), PyInstaller, pytest, QuickBooks Desktop IIF format.

## License

MIT, see [LICENSE](LICENSE).
