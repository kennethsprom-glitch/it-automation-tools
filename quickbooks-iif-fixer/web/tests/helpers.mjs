import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const here = path.dirname(fileURLToPath(import.meta.url));
export const webDir = path.resolve(here, "..");
export const fixerDir = path.resolve(webDir, "..");
export const htmlPath = path.join(webDir, "Trinium-to-GSL-IIF-Fix.html");
export const samplesDir = path.join(fixerDir, "samples");
const fixPy = path.join(fixerDir, "fix_iif.py");
const oraclePy = path.join(here, "oracle.py");

export function loadApi() {
  const html = fs.readFileSync(htmlPath, "utf8");
  const match = html.match(/<script id="trinium-iif-fix">([\s\S]*?)<\/script>/);
  if (!match) throw new Error("core script missing from the HTML file");
  const fn = new Function(`${match[1]}\nreturn globalThis.TriniumIifFix;`);
  return fn();
}

export function readHtml() {
  return fs.readFileSync(htmlPath, "utf8");
}

function tempOut() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "iif-"));
  return { dir, out: path.join(dir, "out.iif") };
}

export function runCli(inputPath, args = []) {
  const { dir, out } = tempOut();
  const res = spawnSync("python3", [fixPy, inputPath, out, ...args], { encoding: "utf8" });
  if (res.status !== 0) {
    fs.rmSync(dir, { recursive: true, force: true });
    const error = new Error(`python exited ${res.status}\n${res.stderr || ""}\n${res.stdout || ""}`);
    error.status = res.status;
    error.stderr = res.stderr;
    throw error;
  }
  const bytes = fs.readFileSync(out);
  const warnings = (res.stderr || "").split(/\r?\n/).filter((line) => line.startsWith("warning:"));
  fs.rmSync(dir, { recursive: true, force: true });
  return { bytes, warnings };
}

export function runOracle(inputPath, options, encoding) {
  const { dir, out } = tempOut();
  const res = spawnSync(
    "python3",
    [oraclePy, JSON.stringify(options || {}), inputPath, out, encoding],
    { encoding: "utf8" },
  );
  if (res.status !== 0) {
    fs.rmSync(dir, { recursive: true, force: true });
    throw new Error(`oracle exited ${res.status}\n${res.stderr || ""}\n${res.stdout || ""}`);
  }
  const bytes = fs.readFileSync(out);
  const warnings = JSON.parse(res.stdout || "[]");
  fs.rmSync(dir, { recursive: true, force: true });
  return { bytes, warnings };
}

export function jsOptionsFromCli(args) {
  const opts = {};
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--terms") opts.terms = args[++i];
    else if (arg === "--date") opts.date = args[++i];
    else if (arg === "--terms-days") opts.termsDays = Number(args[++i]);
    else if (arg === "--keep-class") {
      opts.keepClass = opts.keepClass || [];
      opts.keepClass.push(args[++i]);
    } else if (arg === "--map") opts.itemMap = JSON.parse(fs.readFileSync(args[++i], "utf8"));
    else throw new Error(`unsupported arg ${arg}`);
  }
  return opts;
}

export function assertSameBytes(actual, expected, label) {
  const left = Buffer.from(actual);
  const right = Buffer.from(expected);
  if (left.equals(right)) return;
  const n = Math.max(left.length, right.length);
  let i = 0;
  while (i < n && left[i] === right[i]) i++;
  const start = Math.max(0, i - 30);
  throw new Error(
    `${label} differ at byte ${i} (len ${left.length} vs ${right.length})\n` +
      `actual ${JSON.stringify(left.subarray(start, i + 50).toString("latin1"))}\n` +
      `expect ${JSON.stringify(right.subarray(start, i + 50).toString("latin1"))}`,
  );
}

export function assertCrlf(bytes) {
  const text = Buffer.from(bytes).toString("latin1");
  assert.ok(text.endsWith("\r\n"), "output should end with CRLF");
  assert.equal(text.replaceAll("\r\n", "").includes("\n"), false);
  assert.equal(text.replaceAll("\r\n", "").includes("\r"), false);
}

export function assertMatchesCli(api, inputPath, args = []) {
  const cli = runCli(inputPath, args);
  const js = api.fixFileBytes(fs.readFileSync(inputPath), jsOptionsFromCli(args));
  const label = `${path.basename(inputPath)} ${args.join(" ")}`.trim();
  assertSameBytes(js.bytes, cli.bytes, label);
  assert.deepEqual(js.warnings, cli.warnings);
  assertCrlf(js.bytes);
  return js;
}

export function writeTemp(bytes) {
  const { dir, out } = tempOut();
  fs.writeFileSync(out, bytes);
  return { dir, path: out, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}
