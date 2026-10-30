import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  assertMatchesCli,
  assertSameBytes,
  htmlPath,
  loadApi,
  readHtml,
  runCli,
  runOracle,
  samplesDir,
  writeTemp,
} from "./helpers.mjs";

const api = loadApi();
const sampleExport = path.join(samplesDir, "sample_export.iif");
const sampleNet45 = path.join(samplesDir, "sample_net45.iif");
const sampleReordered = path.join(samplesDir, "sample_reordered.iif");
const sampleEncoding = path.join(samplesDir, "sample_encoding.iif");
const sampleCp1252 = path.join(samplesDir, "sample_cp1252.iif");

test("the page is one self-contained file", () => {
  const html = readHtml();
  assert.equal(path.basename(htmlPath), "Trinium-to-GSL-IIF-Fix.html");
  assert.match(html, /<title>Trinium to GSL IIF Fix \(Web\)<\/title>/);
  assert.match(html, /Files are processed only in your browser\./);
  assert.doesNotMatch(html, /<script[^>]+src=/i);
  assert.doesNotMatch(html, /<link[^>]+href=/i);
  assert.doesNotMatch(html, /\bfetch\s*\(/);
  assert.doesNotMatch(html, /XMLHttpRequest/);
  assert.doesNotMatch(html, /\bimport\s*\(/);
  assert.doesNotMatch(html, /https?:\/\//i);
  assert.doesNotMatch(html, /WebSocket/);
  assert.doesNotMatch(html, /sendBeacon/);
});

test("built-in item map is the five codes, exact and case-sensitive", () => {
  assert.deepEqual(api.DEFAULT_ITEM_MAP, {
    Drayage: "DR",
    "Fuel Surcharge": "FS",
    "PRE PULL": "PRE",
    "PER DIEM": "PD",
    "Chassis Rental": "CHR",
  });
  assert.equal(api.DEFAULT_TERMS, "Net 30");
  assert.equal(api.LOGIC_VERSION, "1.1.0");
});

test("import-ready names keep the original extension", () => {
  assert.equal(api.importReadyName("sample_export.iif"), "sample_export_IMPORT-READY.iif");
  assert.equal(api.importReadyName("C:\\invoices\\export.IIF"), "export_IMPORT-READY.IIF");
  assert.equal(api.importReadyName("noext"), "noext_IMPORT-READY");
});

test("sample_export matches the Python CLI and the checked-in file", () => {
  const js = assertMatchesCli(api, sampleExport);
  assertSameBytes(js.bytes, fs.readFileSync(path.join(samplesDir, "expected_output.iif")), "expected_output");
  const again = api.fixFileBytes(js.bytes);
  assertSameBytes(again.bytes, js.bytes, "idempotent");
});

test("closed period --date and --terms-days match the Python CLI", () => {
  const js = assertMatchesCli(api, sampleExport, ["--date", "03/02/2026", "--terms-days", "30"]);
  assertSameBytes(
    js.bytes,
    fs.readFileSync(path.join(samplesDir, "expected_output_redated.iif")),
    "expected_output_redated",
  );
  assertMatchesCli(api, sampleExport, ["--date", "03/02/2026", "--terms-days", "15", "--terms", "Net 30"]);
  assertMatchesCli(api, sampleExport, ["--date", "3/2/2026", "--terms-days", "30"]);
});

test("Net 45 sample maps every item and rolls the month and the year", () => {
  const js = assertMatchesCli(api, sampleNet45);
  assertSameBytes(js.bytes, fs.readFileSync(path.join(samplesDir, "expected_output_net45.iif")), "expected_output_net45");
  const text = Buffer.from(js.bytes).toString("latin1");
  assert.match(text, /11\/28\/2026/);
  assert.match(text, /01\/14\/2027/);
  for (const code of ["DR", "FS", "PRE", "PD", "CHR"]) assert.match(text, new RegExp(`\\t${code}\\t`));
  const spl = text.split("\r\n").filter((line) => line.startsWith("SPL\t"));
  assert.ok(spl.length >= 6);
  for (const line of spl) {
    assert.equal(line.endsWith("\t"), true);
    assert.equal(line.endsWith("\t\t"), false);
  }
});

test("custom terms and a terms name with no day count match the Python CLI", () => {
  assertMatchesCli(api, sampleNet45, ["--terms", "Net 15"]);
  assertMatchesCli(api, sampleNet45, ["--terms", "  Net 15  "]);
  const js = assertMatchesCli(api, sampleNet45, ["--terms", "Due on receipt"]);
  assert.deepEqual(js.warnings, [
    "warning: terms 'Due on receipt' does not name a number of days; TRNS due dates were left unchanged",
  ]);
});

test("kept classes, LF input, and a reordered header match the Python CLI", () => {
  assertMatchesCli(api, sampleExport, ["--keep-class", "OPS"]);
  const lf = writeTemp(fs.readFileSync(sampleExport).toString("latin1").replaceAll("\r\n", "\n"));
  try {
    const fromLf = assertMatchesCli(api, lf.path);
    const fromCrlf = api.fixFileBytes(fs.readFileSync(sampleExport));
    assertSameBytes(fromLf.bytes, fromCrlf.bytes, "lf vs crlf");
  } finally {
    lf.cleanup();
  }
  assertMatchesCli(api, sampleReordered);
});

test("UTF-8 accented text matches the Python CLI byte for byte", () => {
  const js = assertMatchesCli(api, sampleEncoding);
  const raw = fs.readFileSync(sampleEncoding);
  assert.ok(raw.includes(Buffer.from("é", "utf8")));
  assert.ok(Buffer.from(js.bytes).includes(Buffer.from("é", "utf8")));
  assert.ok(Buffer.from(js.bytes).includes(Buffer.from("€", "utf8")));
});

test("windows-1252 bytes match Python opened as cp1252", () => {
  const options = { terms: "Net 15", date: "01/31/2026", termsDays: 30 };
  const oracle = runOracle(sampleCp1252, options, "cp1252");
  const js = api.fixFileBytes(fs.readFileSync(sampleCp1252), options);
  assertSameBytes(js.bytes, oracle.bytes, "cp1252");
  assert.deepEqual(js.warnings, oracle.warnings);
  const out = Buffer.from(js.bytes);
  assert.ok(out.includes(Buffer.from([0xe9])), "é byte survives");
  assert.ok(out.includes(Buffer.from([0x80])), "euro byte survives");
  assert.ok(out.includes(Buffer.from([0x93])), "smart quote survives");
  assert.ok(out.includes(Buffer.from("01/31/2026")));
  assert.ok(out.includes(Buffer.from("03/02/2026")));
  assert.throws(() => runCli(sampleCp1252), /exited/);
});

test("a latin-1 byte Python's cp1252 codec rejects still round-trips", () => {
  const base = fs.readFileSync(sampleExport);
  const extra = Buffer.from("SAMPLE\x81NOTE", "latin1");
  const patched = Buffer.concat([base.subarray(0, base.indexOf(Buffer.from("CONT0000001"))), extra, base.subarray(base.indexOf(Buffer.from("CONT0000001")) + "CONT0000001".length)]);
  const file = writeTemp(patched);
  try {
    const oracle = runOracle(file.path, {}, "latin-1");
    const js = api.fixFileBytes(fs.readFileSync(file.path));
    assertSameBytes(js.bytes, oracle.bytes, "latin-1 0x81");
    assert.ok(Buffer.from(js.bytes).includes(Buffer.from([0x81])));
  } finally {
    file.cleanup();
  }
});

test("missing columns, a bad date, and an unknown item match the Python CLI", () => {
  const missing = writeTemp(Buffer.from(
    "!TRNS\tDATE\tDUEDATE\tNAME\r\nTRNS\t10/29/2026\t12/13/2026\tACME HARBOR SAMPLE\r\n",
    "latin1",
  ));
  const badDate = writeTemp(Buffer.from(
    "!TRNS\tDATE\tDUEDATE\tTERMS\r\nTRNS\tnot-a-date\t01/01/2026\tNet 45\r\n",
    "latin1",
  ));
  const items = writeTemp(Buffer.from(
    [
      "!SPL\tINVITEM\tCLASS",
      "SPL\tDrayage\t\"DRAY\"",
      "SPL\tdrayage\t\"FS\"",
      "SPL\tStorage\t\"ZZ\"",
      "SPL\tFuel Surcharge\t\"FS\"",
      "SPL\tPRE PULL\t\"PRE\"",
      "SPL\tPER DIEM\t\"PD\"",
      "SPL\tChassis Rental\t\"CHR\"",
    ].join("\r\n") + "\r\n",
    "latin1",
  ));
  const noHeader = writeTemp(Buffer.from("TRNS\t10/29/2026\tNet 45\t12/13/2026\r\n", "latin1"));
  try {
    const missingJs = assertMatchesCli(api, missing.path);
    assert.match(missingJs.warnings.join("\n"), /missing column TERMS/);
    const badJs = assertMatchesCli(api, badDate.path);
    assert.match(badJs.warnings.join("\n"), /could not read TRNS DATE 'not-a-date'/);
    const itemJs = assertMatchesCli(api, items.path);
    const text = Buffer.from(itemJs.bytes).toString("latin1");
    assert.match(text, /SPL\tDR\t\r\n/);
    assert.match(text, /SPL\tdrayage\t\r\n/);
    assert.match(text, /SPL\tStorage\t\r\n/);
    assert.match(text, /SPL\tFS\t\r\n/);
    assert.match(text, /SPL\tPRE\t\r\n/);
    assert.match(text, /SPL\tPD\t\r\n/);
    assert.match(text, /SPL\tCHR\t\r\n/);
    const headerJs = assertMatchesCli(api, noHeader.path);
    assert.match(headerJs.warnings.join("\n"), /missing !TRNS header/);
  } finally {
    missing.cleanup();
    badDate.cleanup();
    items.cleanup();
    noHeader.cleanup();
  }
});

test("empty input matches the Python CLI", () => {
  const empty = writeTemp(Buffer.alloc(0));
  try {
    assertMatchesCli(api, empty.path);
  } finally {
    empty.cleanup();
  }
});
