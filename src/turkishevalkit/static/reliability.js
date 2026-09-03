"use strict";

const state = {
  groups: [],
  selectedKeys: new Set(),
  datasetKey: null,
  report: null,
};

const candidatesRoot = document.getElementById("reliabilityCandidates");
const selectionCount = document.getElementById("selectionCount");
const minimumTaskCount = document.getElementById("minimumTaskCount");
const analyzeButton = document.getElementById("analyzeReliability");
const refreshButton = document.getElementById("refreshReliabilityCandidates");
const message = document.getElementById("reliabilityMessage");
const reportPanel = document.getElementById("reliabilityReport");
const reportTitle = document.getElementById("reliabilityReportTitle");
const reportSubtitle = document.getElementById("reliabilityReportSubtitle");
const summaryRoot = document.getElementById("reliabilitySummary");
const designRoot = document.getElementById("reliabilityDesign");
const criterionRows = document.getElementById("reliabilityCriterionRows");
const populationMeasures = document.getElementById("populationMeasures");
const notesRoot = document.getElementById("reliabilityNotes");
const exportButton = document.getElementById("exportReliabilityJson");

function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function setMessage(text, kind = "") {
  message.textContent = text;
  message.className = kind ? `message ${kind}` : "message";
}

function minimumValue() {
  const parsed = Number.parseInt(minimumTaskCount.value, 10);
  return Number.isFinite(parsed) ? parsed : 3;
}

function selectedGroups() {
  return state.groups.filter((group) => state.selectedKeys.has(group.compatibility_key));
}

function syncSelectionState() {
  if (state.selectedKeys.size === 0) {
    state.datasetKey = null;
  }
  selectionCount.textContent = `${state.selectedKeys.size} selected`;
  const minimum = minimumValue();
  analyzeButton.disabled = state.selectedKeys.size < minimum || minimum < 3;

  for (const card of candidatesRoot.querySelectorAll(".reliability-group")) {
    const key = card.dataset.key;
    const group = state.groups.find((item) => item.compatibility_key === key);
    if (!group) continue;
    const selected = state.selectedKeys.has(key);
    const incompatible = Boolean(state.datasetKey && group.dataset_key !== state.datasetKey);
    card.classList.toggle("selected", selected);
    card.classList.toggle("incompatible", incompatible && !selected);
    const checkbox = card.querySelector("input[type='checkbox']");
    if (checkbox) {
      checkbox.checked = selected;
      checkbox.disabled = !group.ready || (incompatible && !selected);
    }
  }
}

function artifactScoreText(artifact) {
  if (typeof artifact.normalized_score === "number") {
    return `${artifact.normalized_score.toFixed(1)}/100`;
  }
  if (typeof artifact.preference_score === "number") {
    const sign = artifact.preference_score > 0 ? "+" : "";
    return `${sign}${artifact.preference_score.toFixed(1)}`;
  }
  return "—";
}

function renderGroup(group) {
  const card = createElement("article", "reliability-group");
  card.dataset.key = group.compatibility_key;
  if (!group.ready) card.classList.add("not-ready");

  const label = createElement("label", "group-select");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.disabled = !group.ready;
  checkbox.setAttribute("aria-label", `Select ${group.task_id}`);

  const content = createElement("div");
  const title = createElement("div", "group-title");
  title.append(
    createElement("strong", "", group.task_id),
    createElement("span", "group-badge", `${group.evaluator_count} evaluators`),
  );
  const meta = createElement(
    "div",
    "group-meta",
    `${group.evaluation_type} · ${group.rubric_id}@${group.rubric_version}`,
  );
  content.append(title, meta);
  label.append(checkbox, content);
  card.append(label);

  const artifacts = createElement("div", "artifact-list");
  for (const artifact of group.artifacts) {
    const row = createElement("div", "artifact-row");
    row.append(
      createElement("span", "", artifact.evaluator_id || "Unattributed"),
      createElement("span", "artifact-meta", artifactScoreText(artifact)),
    );
    artifacts.append(row);
  }
  card.append(artifacts);

  if (group.reasons.length) {
    const reasons = createElement("ul", "group-reasons");
    for (const reason of group.reasons) {
      reasons.append(createElement("li", "", reason));
    }
    card.append(reasons);
  }

  checkbox.addEventListener("change", () => {
    if (checkbox.checked) {
      if (!state.datasetKey) state.datasetKey = group.dataset_key;
      if (group.dataset_key !== state.datasetKey) {
        checkbox.checked = false;
        return;
      }
      state.selectedKeys.add(group.compatibility_key);
    } else {
      state.selectedKeys.delete(group.compatibility_key);
    }
    syncSelectionState();
  });
  return card;
}

function renderCandidates() {
  candidatesRoot.replaceChildren();
  if (!state.groups.length) {
    candidatesRoot.append(
      createElement(
        "div",
        "empty-state",
        "No saved evaluation groups are available. Create independently attributed evaluations first.",
      ),
    );
    syncSelectionState();
    return;
  }

  for (const group of state.groups) {
    candidatesRoot.append(renderGroup(group));
  }
  syncSelectionState();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || `Request failed with status ${response.status}`);
  }
  return payload;
}

async function loadCandidates() {
  refreshButton.disabled = true;
  setMessage("Loading task groups…");
  try {
    const payload = await fetchJson("/api/reliability/candidates");
    state.groups = Array.isArray(payload.groups) ? payload.groups : [];
    state.selectedKeys.clear();
    state.datasetKey = null;
    state.report = null;
    reportPanel.classList.add("hidden");
    renderCandidates();
    const readyCount = state.groups.filter((group) => group.ready).length;
    setMessage(`${readyCount} ready task group(s) found.`, "success");
  } catch (error) {
    state.groups = [];
    renderCandidates();
    setMessage(error.message, "error");
  } finally {
    refreshButton.disabled = false;
  }
}

function metricCard(label, value) {
  const card = createElement("div", "metric-card");
  card.append(createElement("span", "", label), createElement("strong", "", value));
  return card;
}

function designCard(label, value) {
  const card = createElement("div", "design-card");
  card.append(createElement("span", "", label), createElement("strong", "", value));
  return card;
}

function formatEstimateValue(estimate) {
  if (!estimate || !estimate.applicable || typeof estimate.value !== "number") return "n/a";
  return estimate.value.toFixed(4);
}

function estimateDetails(estimate, compact = false) {
  const root = createElement(compact ? "div" : "section", compact ? "estimate-cell" : "estimate-card");
  root.append(createElement("strong", "estimate-value", formatEstimateValue(estimate)));
  if (!estimate) return root;

  if (!estimate.applicable && estimate.reason) {
    root.append(createElement("span", "estimate-reason", estimate.reason));
  }
  if (Array.isArray(estimate.assumptions) && estimate.assumptions.length) {
    const details = document.createElement("details");
    details.className = "estimate-assumptions";
    const summary = document.createElement("summary");
    summary.textContent = "Assumptions";
    const list = document.createElement("ul");
    for (const assumption of estimate.assumptions) {
      list.append(createElement("li", "", assumption));
    }
    details.append(summary, list);
    root.append(details);
  }
  return root;
}

function renderSummary(report) {
  summaryRoot.replaceChildren(
    metricCard("Task units", report.task_count),
    metricCard("Evaluators", Array.isArray(report.evaluator_ids) ? report.evaluator_ids.length : 0),
    metricCard("Min raters / task", report.min_evaluators_per_task),
    metricCard("Max raters / task", report.max_evaluators_per_task),
  );

  designRoot.replaceChildren(
    designCard("Evaluation type", report.evaluation_type),
    designCard("Rubric", `${report.rubric_id}@${report.rubric_version}`),
    designCard("Fixed rater count", report.fixed_rater_count ? "Yes" : "No"),
    designCard("Fixed evaluator panel", report.fixed_evaluator_panel ? "Yes" : "No"),
  );
}

function renderCriterionTable(report) {
  criterionRows.replaceChildren();
  const criterionReports = report.criterion_reliability || {};
  for (const [criterionId, criterion] of Object.entries(criterionReports)) {
    const row = document.createElement("tr");
    row.append(createElement("td", "", criterionId));
    const alpha = document.createElement("td");
    alpha.append(estimateDetails(criterion.krippendorff_alpha, true));
    const fleiss = document.createElement("td");
    fleiss.append(estimateDetails(criterion.fleiss_kappa, true));
    const icc = document.createElement("td");
    icc.append(estimateDetails(criterion.icc_a1, true));
    row.append(alpha, fleiss, icc);
    criterionRows.append(row);
  }
}

function populationEstimateCard(label, estimate) {
  const card = estimateDetails(estimate, false);
  card.prepend(createElement("span", "estimate-label", label));
  return card;
}

function renderPopulationMeasures(report) {
  populationMeasures.replaceChildren(
    populationEstimateCard("Aggregate score ICC(A,1)", report.aggregate_score_icc_a1),
    populationEstimateCard(
      "Overall preference Krippendorff α",
      report.overall_preference_krippendorff_alpha,
    ),
    populationEstimateCard("Overall preference Fleiss κ", report.overall_preference_fleiss_kappa),
    populationEstimateCard(
      "Preference strength Krippendorff α",
      report.preference_strength_krippendorff_alpha,
    ),
  );
}

function renderNotes(report) {
  notesRoot.replaceChildren();
  for (const note of report.notes || []) {
    notesRoot.append(createElement("li", "", note));
  }
}

function renderReport(report) {
  state.report = report;
  reportTitle.textContent = `${report.evaluation_type} reliability · ${report.task_count} tasks`;
  reportSubtitle.textContent = `${report.rubric_id}@${report.rubric_version} · declared minimum ${report.declared_minimum_task_count}`;
  renderSummary(report);
  renderCriterionTable(report);
  renderPopulationMeasures(report);
  renderNotes(report);
  reportPanel.classList.remove("hidden");
  reportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function analyzeReliability() {
  const minimum = minimumValue();
  const groups = selectedGroups();
  if (minimum < 3 || groups.length < minimum) return;

  analyzeButton.disabled = true;
  setMessage("Analyzing selected task groups…");
  try {
    const payload = await fetchJson("/api/reliability/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        minimum_task_count: minimum,
        groups: groups.map((group) => ({
          filenames: group.artifacts.map((artifact) => artifact.filename),
        })),
      }),
    });
    renderReport(payload.report);
    setMessage("Reliability report generated from the existing core.", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    syncSelectionState();
  }
}

function exportReport() {
  if (!state.report) return;
  const blob = new Blob([`${JSON.stringify(state.report, null, 2)}\n`], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  link.href = url;
  link.download = `turkishevalkit-reliability-${timestamp}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

minimumTaskCount.addEventListener("input", () => {
  const minimum = minimumValue();
  if (minimum < 3) {
    setMessage("minimum_task_count must be at least 3.", "error");
  } else if (state.selectedKeys.size < minimum) {
    setMessage(`Select at least ${minimum} compatible task groups.`);
  } else {
    setMessage("");
  }
  syncSelectionState();
});

refreshButton.addEventListener("click", loadCandidates);
analyzeButton.addEventListener("click", analyzeReliability);
exportButton.addEventListener("click", exportReport);

loadCandidates();
