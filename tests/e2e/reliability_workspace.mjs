import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const baseURL = process.env.WORKBENCH_URL || "http://127.0.0.1:8765";
const artifacts = process.env.E2E_ARTIFACTS || "/tmp/turkisheval-reliability-e2e";

async function ensureNoHorizontalOverflow(page, label) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  assert.ok(
    dimensions.scrollWidth <= dimensions.clientWidth + 1,
    `${label} has horizontal overflow: ${dimensions.scrollWidth} > ${dimensions.clientWidth}`,
  );
}

async function selectReadyTaskGroups(page) {
  const ready = page.locator(".reliability-group input[type='checkbox']:not(:disabled)");
  await ready.first().waitFor();
  assert.equal(await ready.count(), 3, "expected exactly three ready reliability task groups");
  for (let index = 0; index < 3; index += 1) {
    await ready.nth(index).check();
  }
  assert.equal(await page.locator("#selectionCount").textContent(), "3 selected");
  assert.equal(await page.locator("#analyzeReliability").isEnabled(), true);
}

async function exerciseDesktop(browser) {
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  const browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));

  await page.goto(`${baseURL}/reliability`, { waitUntil: "networkidle" });
  assert.equal(await page.title(), "Reliability · TurkishEvalKit");
  await page.locator("#reliabilityMessage").filter({ hasText: "3 ready task group(s) found." }).waitFor();
  assert.equal(await page.getByRole("link", { name: "Evaluations" }).isVisible(), true);
  assert.equal(await page.getByRole("link", { name: "Calibration" }).isVisible(), true);
  await ensureNoHorizontalOverflow(page, "reliability desktop viewport");

  await selectReadyTaskGroups(page);
  await page.locator("#analyzeReliability").click();
  await page
    .locator("#reliabilityMessage")
    .filter({ hasText: "Reliability report generated from the existing core." })
    .waitFor();
  await page.locator("#reliabilityReport:not(.hidden)").waitFor();

  assert.equal(await page.locator("#reliabilityReportTitle").textContent(), "text reliability · 3 tasks");
  assert.match(
    await page.locator("#reliabilityReportSubtitle").textContent(),
    /^tr-text-quality@1\.0 · declared minimum 3$/,
  );
  assert.equal(await page.locator("#reliabilityCriterionRows tr").count(), 5);
  assert.equal(await page.locator("#reliabilitySummary .metric-card").count(), 4);
  assert.equal(await page.locator("#reliabilityDesign .design-card").count(), 4);
  assert.equal(await page.locator("#populationMeasures .estimate-card").count(), 4);

  const firstRow = page.locator("#reliabilityCriterionRows tr").first();
  assert.equal(await firstRow.locator("td").nth(2).locator(".estimate-value").textContent(), "n/a");
  assert.match(
    await firstRow.locator("td").nth(2).locator(".estimate-reason").textContent(),
    /ordinal/,
  );
  assert.ok(
    (await firstRow.locator("details.estimate-assumptions li").count()) > 0,
    "expected reliability assumptions to remain inspectable in the browser",
  );

  const downloadPromise = page.waitForEvent("download");
  await page.locator("#exportReliabilityJson").click();
  const download = await downloadPromise;
  assert.match(download.suggestedFilename(), /^turkishevalkit-reliability-.*\.json$/);
  const downloadPath = path.join(artifacts, "reliability-report.json");
  await download.saveAs(downloadPath);
  const exported = JSON.parse(await fs.readFile(downloadPath, "utf8"));
  assert.equal(exported.task_count, 3);
  assert.equal(exported.declared_minimum_task_count, 3);
  assert.equal(exported.evaluation_type, "text");
  assert.equal(exported.rubric_id, "tr-text-quality");
  assert.equal(Object.keys(exported.criterion_reliability).length, 5);

  await ensureNoHorizontalOverflow(page, "rendered reliability desktop report");
  await page.screenshot({ path: path.join(artifacts, "reliability-desktop.png"), fullPage: true });
  assert.deepEqual(browserErrors, [], `reliability browser page errors: ${browserErrors.join(" | ")}`);
  await context.close();
}

async function exerciseMobile(browser) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  const browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));

  await page.goto(`${baseURL}/reliability`, { waitUntil: "networkidle" });
  await page.locator("#reliabilityMessage").filter({ hasText: "3 ready task group(s) found." }).waitFor();
  await ensureNoHorizontalOverflow(page, "reliability 390px mobile viewport");
  assert.equal(await page.locator(".reliability-group").count(), 3);
  assert.equal(await page.getByRole("link", { name: "Evaluations" }).isVisible(), true);
  assert.equal(await page.getByRole("link", { name: "Calibration" }).isVisible(), true);

  await selectReadyTaskGroups(page);
  await page.locator("#analyzeReliability").click();
  await page.locator("#reliabilityReport:not(.hidden)").waitFor();
  assert.equal(await page.locator("#reliabilityCriterionRows tr").count(), 5);
  await ensureNoHorizontalOverflow(page, "rendered reliability mobile report");
  await page.screenshot({ path: path.join(artifacts, "reliability-mobile.png"), fullPage: true });
  assert.deepEqual(browserErrors, [], `reliability mobile page errors: ${browserErrors.join(" | ")}`);
  await context.close();
}

await fs.mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  await exerciseDesktop(browser);
  await exerciseMobile(browser);
} finally {
  await browser.close();
}
