import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { test, before, after } from "node:test";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import {
  assertSameBytes,
  htmlPath,
  runCli,
  samplesDir,
} from "./helpers.mjs";

const sampleExport = path.join(samplesDir, "sample_export.iif");
const sampleNet45 = path.join(samplesDir, "sample_net45.iif");
const pageUrl = pathToFileURL(htmlPath).href;

let browser;

before(async () => {
  browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
});

after(async () => {
  if (browser) await browser.close();
});

async function openPage() {
  const context = await browser.newContext({ acceptDownloads: true, offline: true });
  const page = await context.newPage();
  const requests = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto(pageUrl);
  return { context, page, requests };
}

async function downloadBytes(page) {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#download"),
  ]);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "iif-dl-"));
  const target = path.join(dir, download.suggestedFilename());
  await download.saveAs(target);
  const bytes = fs.readFileSync(target);
  fs.rmSync(dir, { recursive: true, force: true });
  return { bytes, filename: download.suggestedFilename() };
}

async function noHorizontalOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1);
}

test("file:// page loads a fake sample and the download matches Python", { timeout: 120000 }, async () => {
  const before = fs.readFileSync(sampleNet45);
  const { context, page, requests } = await openPage();
  try {
    assert.equal(await page.title(), "Trinium to GSL IIF Fix (Web)");
    assert.match(await page.locator("header").innerText(), /Files are processed only in your browser\./);
    await page.setInputFiles("#file", sampleNet45);
    await page.waitForSelector("#preview .invoice");
    const preview = await page.locator("#preview").innerText();
    assert.match(preview, /Invoice 9001/);
    assert.match(preview, /ACME HARBOR SAMPLE/);
    assert.match(preview, /Net 45/);
    assert.match(preview, /Net 30/);
    assert.match(preview, /12\/13\/2026/);
    assert.match(preview, /11\/28\/2026/);
    assert.match(preview, /01\/29\/2027/);
    assert.match(preview, /01\/14\/2027/);
    assert.match(preview, /Drayage/);
    assert.match(preview, /Fuel Surcharge/);
    assert.match(preview, /PRE PULL/);
    assert.match(preview, /PER DIEM/);
    assert.match(preview, /Chassis Rental/);
    for (const code of ["DR", "FS", "PRE", "PD", "CHR"]) assert.match(preview, new RegExp(`\\b${code}\\b`));
    assert.match(preview, /before/i);
    assert.match(preview, /after/i);

    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await noHorizontalOverflow(page), true);
    await page.setViewportSize({ width: 1280, height: 800 });
    assert.equal(await noHorizontalOverflow(page), true);

    const saved = await downloadBytes(page);
    assert.equal(saved.filename, "sample_net45_IMPORT-READY.iif");
    const cli = runCli(sampleNet45);
    assertSameBytes(saved.bytes, cli.bytes, "browser default download");
    assert.deepEqual(fs.readFileSync(sampleNet45), before);
    assert.equal(requests.some((url) => url.startsWith("http:") || url.startsWith("https:")), false);
  } finally {
    await context.close();
  }
});

test("file:// custom terms and closed-period downloads match Python", { timeout: 120000 }, async () => {
  const { context, page } = await openPage();
  try {
    await page.setInputFiles("#file", sampleNet45);
    await page.waitForSelector("#preview .invoice");
    await page.fill("#terms", "Net 15");
    await page.waitForFunction(() => document.body.innerText.includes("11/13/2026"));
    let saved = await downloadBytes(page);
    assert.equal(saved.filename, "sample_net45_IMPORT-READY.iif");
    assertSameBytes(saved.bytes, runCli(sampleNet45, ["--terms", "Net 15"]).bytes, "browser Net 15");

    await page.fill("#terms", "Due on receipt");
    await page.waitForSelector("#warnings");
    assert.match(await page.locator("#warnings").innerText(), /does not name a number of days/);
    saved = await downloadBytes(page);
    assertSameBytes(saved.bytes, runCli(sampleNet45, ["--terms", "Due on receipt"]).bytes, "browser due on receipt");

    await page.setInputFiles("#file", sampleExport);
    await page.fill("#terms", "Net 30");
    await page.fill("#date", "03/02/2026");
    await page.fill("#termsDays", "30");
    await page.waitForSelector("#preview .flag");
    assert.equal(await page.locator("#preview .flag").count(), 1);
    assert.match(await page.locator("#preview").innerText(), /01\/05\/2026/);
    assert.match(await page.locator("#preview").innerText(), /03\/02\/2026/);
    saved = await downloadBytes(page);
    assert.equal(saved.filename, "sample_export_IMPORT-READY.iif");
    assertSameBytes(
      saved.bytes,
      runCli(sampleExport, ["--date", "03/02/2026", "--terms-days", "30", "--terms", "Net 30"]).bytes,
      "browser closed period",
    );

    await page.fill("#date", "01/01/2026");
    await page.waitForFunction(() => !document.querySelector("#preview .flag"));
    saved = await downloadBytes(page);
    assertSameBytes(
      saved.bytes,
      runCli(sampleExport, ["--date", "01/01/2026", "--terms-days", "30"]).bytes,
      "browser rewrites dates that are not before the new date",
    );
    assert.equal(await page.locator("#preview .flag").count(), 0);

    await page.setInputFiles("#file", sampleNet45);
    await page.fill("#date", "11/01/2026");
    await page.fill("#termsDays", "30");
    await page.waitForSelector("#preview .flag");
    assert.equal(await page.locator("#preview .flag").count(), 1);
    saved = await downloadBytes(page);
    assertSameBytes(
      saved.bytes,
      runCli(sampleNet45, ["--date", "11/01/2026", "--terms-days", "30", "--terms", "Net 30"]).bytes,
      "browser flags only the earlier invoice and still rewrites every date",
    );
  } finally {
    await context.close();
  }
});

test("file:// drag and drop loads the sample", { timeout: 120000 }, async () => {
  const { context, page } = await openPage();
  try {
    const payload = fs.readFileSync(sampleExport).toString("base64");
    await page.evaluate((b64) => {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const file = new File([bytes], "sample_export.iif");
      const transfer = new DataTransfer();
      transfer.items.add(file);
      const drop = document.getElementById("drop");
      drop.dispatchEvent(new DragEvent("drop", { dataTransfer: transfer, bubbles: true, cancelable: true }));
    }, payload);
    await page.waitForSelector("#preview .invoice");
    const saved = await downloadBytes(page);
    assert.equal(saved.filename, "sample_export_IMPORT-READY.iif");
    assertSameBytes(saved.bytes, runCli(sampleExport).bytes, "drag and drop download");
  } finally {
    await context.close();
  }
});
