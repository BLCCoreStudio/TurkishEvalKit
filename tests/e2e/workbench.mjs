import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const baseURL = process.env.WORKBENCH_URL || "http://127.0.0.1:8765";
const artifacts = process.env.E2E_ARTIFACTS || "/tmp/turkisheval-browser-e2e";

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

async function rateEveryCriterion(page, score) {
  const criteria = page.locator("#criteriaList .criterion");
  const count = await criteria.count();
  assert.ok(count > 0, "expected at least one rubric criterion");

  for (let index = 0; index < count; index += 1) {
    const row = criteria.nth(index);
    await row.locator(`input[type="radio"][value="${score}"]`).check();
  }
}

async function waitForSaved(page, taskId) {
  await page.locator("#saveButton").click();
  await page.locator("#resultCard:not(.hidden)").waitFor();
  await page.locator("#message").filter({ hasText: "Saved to the local workspace." }).waitFor();
  assert.equal(await page.locator("#resultTask").textContent(), taskId);
  await page.locator("#historyList .history-item", { hasText: taskId }).waitFor();
}

async function exerciseDesktop(browser) {
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  const browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));

  await page.goto(baseURL, { waitUntil: "networkidle" });
  await page.locator("#workspacePath").filter({ hasNotText: "Loading" }).waitFor();
  await ensureNoHorizontalOverflow(page, "desktop viewport");

  assert.equal(await page.title(), "TurkishEvalKit Workbench");
  assert.match(await page.locator("#rubricVersion").textContent(), /^tr-text-quality@/);

  await page.locator("#saveButton").click();
  await page.locator("#message").filter({ hasText: "Rate every rubric criterion before saving." }).waitFor();
  assert.ok(await page.locator("#resultCard").evaluate((node) => node.classList.contains("hidden")));

  const textTask = "e2e-text-001";
  await page.locator("#taskId").fill(textTask);
  await page.locator("#sourcePrompt").fill("Bu cevabı açıklık ve doğruluk açısından değerlendir.");
  await page.locator("#sourceResponse").fill("İstanbul, Türkiye'nin en kalabalık şehridir.");
  await rateEveryCriterion(page, 5);
  await page.locator("#evaluatorNote").fill("Yanıt doğal, açık ve doğrudan.");
  await page.locator("#justificationEn").fill("The response is concise, fluent, and directly addresses the prompt.");
  await waitForSaved(page, textTask);

  assert.equal(await page.locator("#resultScore").textContent(), "100.00 / 100");
  const textHistory = page.locator("#historyList .history-item", { hasText: textTask });
  assert.match(await textHistory.textContent(), /text · 100\.00\/100/);

  const downloadPromise = page.waitForEvent("download");
  await page.locator("#resultDownload").click();
  const download = await downloadPromise;
  const suggested = download.suggestedFilename();
  assert.ok(suggested.endsWith(".json"), `unexpected download filename: ${suggested}`);
  const downloadPath = path.join(artifacts, suggested);
  await download.saveAs(downloadPath);
  const exported = JSON.parse(await fs.readFile(downloadPath, "utf8"));
  assert.equal(exported.task_id, textTask);
  assert.equal(exported.normalized_score, 100);

  await page.locator("#newButton").click();
  assert.notEqual(await page.locator("#taskId").inputValue(), textTask);
  assert.ok(await page.locator("#resultCard").evaluate((node) => node.classList.contains("hidden")));

  await page.getByRole("button", { name: "Audio" }).click();
  await page.locator("#sourceAudioRef").waitFor();
  assert.match(await page.locator("#rubricVersion").textContent(), /^tr-audio-quality@/);

  const audioTask = "e2e-audio-001";
  await page.locator("#taskId").fill(audioTask);
  await page.locator("#sourceAudioRef").fill("authorized://sample/audio-001");
  await page.locator("#sourceTranscript").fill("Merhaba, bugün nasılsınız?");
  await rateEveryCriterion(page, 4);
  await page.locator("#evaluatorNote").fill("Akıcılık iyi; tonlama genel olarak doğal.");
  await page.locator("#justificationEn").fill("Fluency is strong and intonation is mostly natural.");
  await waitForSaved(page, audioTask);

  const historyItems = page.locator("#historyList .history-item");
  assert.ok((await historyItems.count()) >= 2, "expected text and audio history entries");
  assert.ok(await page.locator("#historyList .history-item", { hasText: textTask }).count());
  assert.ok(await page.locator("#historyList .history-item", { hasText: audioTask }).count());

  await page.screenshot({ path: path.join(artifacts, "desktop.png"), fullPage: true });
  assert.deepEqual(browserErrors, [], `browser page errors: ${browserErrors.join(" | ")}`);
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

  await page.goto(baseURL, { waitUntil: "networkidle" });
  await page.locator("#workspacePath").filter({ hasNotText: "Loading" }).waitFor();
  await ensureNoHorizontalOverflow(page, "390px mobile viewport");

  assert.ok(await page.locator("#saveButton").isVisible(), "save button should be visible on mobile");
  assert.ok(await page.getByRole("button", { name: "Text" }).isVisible());
  assert.ok(await page.getByRole("button", { name: "Audio" }).isVisible());

  await page.locator("#taskId").fill("e2e-mobile-001");
  await page.locator("#sourcePrompt").fill("Kısa bir mobil test istemi.");
  await page.locator("#sourceResponse").fill("Mobil görünümde değerlendirme akışı kullanılabilir.");
  await rateEveryCriterion(page, 5);
  await waitForSaved(page, "e2e-mobile-001");
  await ensureNoHorizontalOverflow(page, "mobile viewport after result rendering");

  await page.screenshot({ path: path.join(artifacts, "mobile.png"), fullPage: true });
  assert.deepEqual(browserErrors, [], `browser page errors: ${browserErrors.join(" | ")}`);
  await context.close();
}

await fs.mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  await exerciseDesktop(browser);
  await exerciseMobile(browser);
  const files = await fs.readdir(artifacts);
  assert.ok(files.includes("desktop.png"));
  assert.ok(files.includes("mobile.png"));
  console.log("Browser E2E passed: desktop + mobile UI flows, persistence, history, and JSON export.");
} finally {
  await browser.close();
}
