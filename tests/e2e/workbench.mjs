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
    await row.locator(".score-group label", { hasText: String(score) }).click();
  }
}

async function choosePairwisePreferences(page, preferences) {
  const criteria = page.locator("#criteriaList .criterion");
  const count = await criteria.count();
  assert.equal(count, preferences.length, "pairwise preference fixture must cover every criterion");

  for (let index = 0; index < count; index += 1) {
    const row = criteria.nth(index);
    const value = preferences[index];
    await row.locator(`input[name^="preference-"][value="${value}"] + label`).click();
  }
}

async function waitForSaved(page, taskId) {
  await page.locator("#saveButton").click();
  await page.locator("#resultCard:not(.hidden)").waitFor();
  await page.locator("#message").filter({ hasText: "Saved to the local workspace." }).waitFor();
  assert.equal(await page.locator("#resultTask").textContent(), taskId);
  await page
    .locator("#historyList .history-item", { hasText: taskId })
    .waitFor({ state: "attached" });
}

async function exerciseReviewWorkflow(page, taskId) {
  await page.locator("#workflowCard:not(.hidden)").waitFor();
  assert.equal(await page.locator("#workflowState").textContent(), "Draft");
  assert.equal(await page.locator("#workflowEvaluator").textContent(), "evaluator-local");
  assert.match(await page.locator("#workflowSession").textContent(), /^session-/);

  await page.locator("#submitWorkflowButton").click();
  await page.locator("#workflowMessage").filter({ hasText: "Workflow updated." }).waitFor();
  assert.equal(await page.locator("#workflowState").textContent(), "Submitted");

  await page.locator("#reviewerId").fill("reviewer-e2e");
  await page.locator("#reviewOutcome").selectOption("escalate");
  await page.locator("#reviewNote").fill("Factuality evidence requires independent resolution.");
  await page.locator("#reviewWorkflowButton").click();
  await page.locator("#workflowMessage").filter({ hasText: "Workflow updated." }).waitFor();
  assert.equal(await page.locator("#workflowState").textContent(), "Reviewed");

  await page.locator("#adjudicatorId").fill("adjudicator-e2e");
  await page.locator("#adjudicationOutcome").selectOption("review_concern_upheld");
  await page.locator("#adjudicationNote").fill("Independent adjudication confirms the reviewer concern.");
  await page.locator("#adjudicateWorkflowButton").click();
  await page.locator("#workflowMessage").filter({ hasText: "Workflow updated." }).waitFor();
  assert.equal(await page.locator("#workflowState").textContent(), "Adjudicated");
  assert.match(await page.locator("#workflowControls").textContent(), /Review Concern Upheld/);
  assert.equal(await page.locator("#workflowEvents .workflow-event").count(), 4);

  const history = page.locator("#historyList .history-item", { hasText: taskId });
  await history.locator(".history-workflow", { hasText: "Adjudicated" }).waitFor();
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
  assert.ok(await page.getByRole("button", { name: "Pairwise" }).isVisible());
  assert.equal(await page.locator("#evaluatorId").inputValue(), "evaluator-local");
  assert.match(await page.locator("#sessionId").inputValue(), /^session-/);

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
  await exerciseReviewWorkflow(page, textTask);
  await ensureNoHorizontalOverflow(page, "desktop adjudication workflow");

  const textDownloadPromise = page.waitForEvent("download");
  await page.locator("#resultDownload").click();
  const textDownload = await textDownloadPromise;
  const textSuggested = textDownload.suggestedFilename();
  assert.ok(textSuggested.endsWith(".json"), `unexpected download filename: ${textSuggested}`);
  const textDownloadPath = path.join(artifacts, textSuggested);
  await textDownload.saveAs(textDownloadPath);
  const textExported = JSON.parse(await fs.readFile(textDownloadPath, "utf8"));
  assert.equal(textExported.task_id, textTask);
  assert.equal(textExported.normalized_score, 100);

  const originalSession = await page.locator("#sessionId").inputValue();
  await page.locator("#newSessionButton").click();
  assert.notEqual(await page.locator("#sessionId").inputValue(), originalSession);

  await page.locator("#newButton").click();
  assert.notEqual(await page.locator("#taskId").inputValue(), textTask);
  assert.ok(await page.locator("#resultCard").evaluate((node) => node.classList.contains("hidden")));
  assert.ok(await page.locator("#workflowCard").evaluate((node) => node.classList.contains("hidden")));

  await page.getByRole("button", { name: "Audio" }).click();
  await page.locator("#sourceAudioRef").waitFor();
  await page.locator("#audioAnnotationsPanel").waitFor();
  assert.match(await page.locator("#rubricVersion").textContent(), /^tr-audio-quality@/);

  const audioTask = "e2e-audio-001";
  await page.locator("#taskId").fill(audioTask);
  await page.locator("#sourceAudioRef").fill("authorized://sample/audio-001");
  await page.locator("#sourceTranscript").fill("Merhaba, bugün nasılsınız?");
  await rateEveryCriterion(page, 4);

  await page.locator("#addAudioAnnotationButton").click();
  let audioRows = page.locator("#audioAnnotationList .audio-annotation-row");
  let audioRow = audioRows.nth(0);
  await audioRow.locator(".audio-start").fill("00:01.250");
  await audioRow.locator(".audio-end").fill("00:01.900");
  await audioRow.locator(".audio-category").selectOption("pronunciation");
  await audioRow.locator(".audio-severity").selectOption("major");
  await audioRow.locator(".audio-note").fill("The vowel is prolonged beyond natural Turkish pronunciation.");

  await page.locator("#addAudioAnnotationButton").click();
  audioRows = page.locator("#audioAnnotationList .audio-annotation-row");
  audioRow = audioRows.nth(1);
  await audioRow.locator(".audio-start").fill("5.1");
  await audioRow.locator(".audio-category").selectOption("intonation");
  await audioRow.locator(".audio-severity").selectOption("minor");
  await audioRow.locator(".audio-note").fill("Sentence-final intonation becomes noticeably flat.");
  assert.equal(await audioRows.count(), 2);
  await ensureNoHorizontalOverflow(page, "desktop audio annotation editor");

  await page.locator("#evaluatorNote").fill("Akıcılık iyi; tonlama genel olarak doğal.");
  await page.locator("#justificationEn").fill("Fluency is strong and intonation is mostly natural.");
  await waitForSaved(page, audioTask);
  assert.equal(await page.locator("#workflowState").textContent(), "Draft");

  const audioDownloadPromise = page.waitForEvent("download");
  await page.locator("#resultDownload").click();
  const audioDownload = await audioDownloadPromise;
  const audioSuggested = audioDownload.suggestedFilename();
  const audioDownloadPath = path.join(artifacts, audioSuggested);
  await audioDownload.saveAs(audioDownloadPath);
  const audioExported = JSON.parse(await fs.readFile(audioDownloadPath, "utf8"));
  assert.deepEqual(audioExported.payload.audio_annotations, [
    {
      start_ms: 1250,
      end_ms: 1900,
      category: "pronunciation",
      severity: "major",
      note: "The vowel is prolonged beyond natural Turkish pronunciation.",
    },
    {
      start_ms: 5100,
      end_ms: 5100,
      category: "intonation",
      severity: "minor",
      note: "Sentence-final intonation becomes noticeably flat.",
    },
  ]);

  await page.getByRole("button", { name: "Pairwise" }).click();
  await page.locator("#sourceResponseA").waitFor();
  await page.locator("#sourceResponseB").waitFor();
  assert.match(await page.locator("#rubricVersion").textContent(), /^tr-pairwise-quality@/);
  assert.equal(await page.locator("#criteriaHeading").textContent(), "Criterion preferences");
  assert.match(await page.locator("#scaleHint").textContent(), /A, Tie, or B/);
  await ensureNoHorizontalOverflow(page, "desktop pairwise viewport");

  await page.locator("#saveButton").click();
  await page
    .locator("#message")
    .filter({ hasText: "Choose A, Tie, or B for every rubric criterion before saving." })
    .waitFor();

  const pairwiseTask = "e2e-pairwise-001";
  await page.locator("#taskId").fill(pairwiseTask);
  await page.locator("#sourcePrompt").fill("İki yanıtı Türkçe kalite açısından karşılaştır.");
  await page.locator("#sourceResponseA").fill("A yanıtı daha doğal ve doğrudan bir açıklama sunuyor.");
  await page.locator("#sourceResponseB").fill("B yanıtı ayrıntılıdır fakat daha dolambaçlıdır.");
  await choosePairwisePreferences(page, ["a", "a", "tie", "b", "a"]);
  await page.locator('label[for="overall-a"]').click();
  await page.locator('label[for="strength-2"]').click();
  await page.locator("#evaluatorNote").fill("A genel olarak daha doğal ve talimata daha uygun.");
  await page.locator("#justificationEn").fill("A is preferred overall for fluency and instruction following.");
  await waitForSaved(page, pairwiseTask);

  assert.equal(await page.locator("#resultScore").textContent(), "A preferred · +40.00 A↔B");
  const pairwiseHistory = page.locator("#historyList .history-item", { hasText: pairwiseTask });
  assert.match(await pairwiseHistory.textContent(), /pairwise · A · \+40\.00 A↔B/);

  const pairwiseDownloadPromise = page.waitForEvent("download");
  await page.locator("#resultDownload").click();
  const pairwiseDownload = await pairwiseDownloadPromise;
  const pairwiseSuggested = pairwiseDownload.suggestedFilename();
  const pairwiseDownloadPath = path.join(artifacts, pairwiseSuggested);
  await pairwiseDownload.saveAs(pairwiseDownloadPath);
  const pairwiseExported = JSON.parse(await fs.readFile(pairwiseDownloadPath, "utf8"));
  assert.equal(pairwiseExported.task_id, pairwiseTask);
  assert.equal(pairwiseExported.overall_preference, "a");
  assert.equal(pairwiseExported.preference_strength, 2);
  assert.equal(pairwiseExported.preference_score, 40);
  assert.deepEqual(pairwiseExported.preference_counts, { a: 3, b: 1, tie: 1 });
  assert.equal(pairwiseExported.payload.source.response_a.startsWith("A yanıtı"), true);
  assert.equal(pairwiseExported.payload.source.response_b.startsWith("B yanıtı"), true);

  const historyItems = page.locator("#historyList .history-item");
  assert.ok((await historyItems.count()) >= 3, "expected text, audio, and pairwise history entries");
  assert.ok(await page.locator("#historyList .history-item", { hasText: textTask }).count());
  assert.ok(await page.locator("#historyList .history-item", { hasText: audioTask }).count());
  assert.ok(await page.locator("#historyList .history-item", { hasText: pairwiseTask }).count());

  await textHistory.locator(".history-open").click();
  await page.locator("#workflowState").filter({ hasText: "Adjudicated" }).waitFor();
  assert.equal(await page.locator("#resultTask").textContent(), textTask);
  assert.equal(await page.locator("#workflowEvents .workflow-event").count(), 4);

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
  await page.locator("#workspacePath").filter({ hasNotText: "Loading" }).waitFor({ state: "attached" });
  await ensureNoHorizontalOverflow(page, "390px mobile viewport");

  assert.ok(await page.locator("#saveButton").isVisible(), "save button should be visible on mobile");
  assert.ok(await page.getByRole("button", { name: "Text" }).isVisible());
  assert.ok(await page.getByRole("button", { name: "Audio" }).isVisible());
  assert.ok(await page.getByRole("button", { name: "Pairwise" }).isVisible());
  assert.ok(await page.locator("#evaluatorId").isVisible());
  assert.ok(await page.locator("#sessionId").isVisible());

  await page.getByRole("button", { name: "Audio" }).click();
  await page.locator("#audioAnnotationsPanel").waitFor();
  await page.locator("#addAudioAnnotationButton").click();
  assert.equal(await page.locator("#audioAnnotationList .audio-annotation-row").count(), 1);
  await ensureNoHorizontalOverflow(page, "390px mobile audio annotation editor");

  await page.getByRole("button", { name: "Pairwise" }).click();
  await page.locator("#sourceResponseA").waitFor();
  await ensureNoHorizontalOverflow(page, "390px mobile pairwise viewport");

  await page.locator("#taskId").fill("e2e-mobile-pairwise-001");
  await page.locator("#sourcePrompt").fill("Mobil pairwise test istemi.");
  await page.locator("#sourceResponseA").fill("A mobil yanıtı.");
  await page.locator("#sourceResponseB").fill("B mobil yanıtı.");
  await choosePairwisePreferences(page, ["tie", "tie", "tie", "tie", "tie"]);
  await page.locator('label[for="overall-tie"]').click();
  await page.locator('label[for="strength-1"]').click();
  await waitForSaved(page, "e2e-mobile-pairwise-001");
  assert.equal(await page.locator("#resultScore").textContent(), "Tie · 0.00 A↔B");
  assert.equal(await page.locator("#workflowState").textContent(), "Draft");
  await ensureNoHorizontalOverflow(page, "mobile pairwise viewport after result rendering");

  await page.locator("#submitWorkflowButton").click();
  await page.locator("#workflowState").filter({ hasText: "Submitted" }).waitFor();
  await ensureNoHorizontalOverflow(page, "mobile submitted workflow");

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
  console.log(
    "Browser E2E passed: text, timestamped audio annotations, pairwise, evaluator sessions, review/adjudication, persistence, history, and JSON export.",
  );
} finally {
  await browser.close();
}
