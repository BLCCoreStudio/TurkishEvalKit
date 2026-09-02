"use strict";

const byId = (id) => document.getElementById(id);

const ACTION_LABELS = {
  awaiting_review: "Awaiting review",
  awaiting_revision: "Awaiting revision",
  awaiting_adjudication: "Awaiting adjudication",
  draft: "Draft",
  complete: "Complete",
  superseded: "Superseded",
  untracked: "Untracked",
};

const state = {
  page: 1,
  pages: 0,
  selectedFilename: null,
  controller: null,
  searchTimer: null,
};

function setQueueMessage(message, kind = "") {
  const element = byId("queueMessage");
  element.textContent = message;
  element.className = `message ${kind}`.trim();
}

function selectedValue(id) {
  return byId(id).value.trim();
}

function buildQuery() {
  const params = new URLSearchParams();
  const search = selectedValue("filterSearch");
  const action = selectedValue("filterAction");
  const type = selectedValue("filterType");
  const rubric = selectedValue("filterRubric");
  const evaluator = selectedValue("filterEvaluator");
  const sort = selectedValue("filterSort");
  const perPage = selectedValue("filterPageSize");

  if (search) params.set("q", search);
  if (action) params.append("action", action);
  if (type) params.append("evaluation_type", type);
  if (rubric) params.append("rubric_id", rubric);
  if (evaluator) params.append("evaluator_id", evaluator);
  params.set("sort", sort || "priority");
  params.set("page", String(state.page));
  params.set("per_page", perPage || "50");
  return params;
}

function updateLocation(params) {
  const publicParams = new URLSearchParams(params);
  publicParams.delete("page");
  publicParams.delete("per_page");
  if (state.page > 1) publicParams.set("page", String(state.page));
  const perPage = selectedValue("filterPageSize");
  if (perPage && perPage !== "50") publicParams.set("per_page", perPage);
  const query = publicParams.toString();
  history.replaceState(null, "", query ? `/queue?${query}` : "/queue");
}

function setSummary(summary) {
  const byAction = summary.by_action || {};
  byId("summaryActionable").textContent = String(summary.actionable_total ?? 0);
  byId("summaryReview").textContent = String(byAction.awaiting_review ?? 0);
  byId("summaryRevision").textContent = String(byAction.awaiting_revision ?? 0);
  byId("summaryAdjudication").textContent = String(byAction.awaiting_adjudication ?? 0);
  byId("summaryTotal").textContent = String(summary.workspace_total ?? 0);
}

function populateFacet(id, defaultLabel, values) {
  const select = byId(id);
  const current = select.value;
  const fragment = document.createDocumentFragment();
  const all = document.createElement("option");
  all.value = "";
  all.textContent = defaultLabel;
  fragment.append(all);

  for (const facet of values || []) {
    const option = document.createElement("option");
    option.value = facet.value;
    option.textContent = `${facet.value} (${facet.count})`;
    fragment.append(option);
  }
  select.replaceChildren(fragment);
  if ([...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
}

function formatSavedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function revisionLabel(item) {
  if (Number(item.revision_number) > 0) return `r${item.revision_number}`;
  if (item.superseded_by) return "r0 · superseded";
  return "r0";
}

function makeCell(text, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text;
  return cell;
}

function renderRows(items) {
  const body = byId("queueBody");
  body.replaceChildren();
  if (!items.length) {
    const row = document.createElement("tr");
    row.className = "queue-empty";
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "No evaluations match the current queue filters.";
    row.append(cell);
    body.append(row);
    return;
  }

  for (const item of items) {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.dataset.filename = item.filename;
    if (item.filename === state.selectedFilename) row.classList.add("selected");

    const actionCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `queue-action-badge ${item.queue_action}`;
    badge.textContent = ACTION_LABELS[item.queue_action] || item.queue_action;
    actionCell.append(badge);

    const taskCell = document.createElement("td");
    taskCell.className = "queue-task";
    const task = document.createElement("strong");
    task.textContent = item.task_id || "Untitled task";
    const artifact = document.createElement("span");
    artifact.textContent = item.filename;
    taskCell.append(task, artifact);

    const typeCell = document.createElement("td");
    typeCell.textContent = item.evaluation_type || "—";
    const rubric = document.createElement("span");
    rubric.className = "queue-secondary";
    rubric.textContent = item.rubric_id
      ? `${item.rubric_id}@${item.rubric_version || "?"}`
      : "No rubric";
    typeCell.append(rubric);

    const evaluatorCell = makeCell(item.evaluator_id || "—");
    const revisionCell = makeCell(revisionLabel(item));
    const savedCell = makeCell(formatSavedAt(item.saved_at));

    row.append(actionCell, taskCell, typeCell, evaluatorCell, revisionCell, savedCell);
    row.addEventListener("click", () => loadDetails(item.filename));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        loadDetails(item.filename);
      }
    });
    body.append(row);
  }
}

function renderPagination(payload) {
  state.pages = payload.pages || 0;
  byId("pageLabel").textContent = state.pages
    ? `Page ${payload.page} of ${state.pages}`
    : "Page 0 of 0";
  byId("previousPage").disabled = payload.page <= 1;
  byId("nextPage").disabled = !state.pages || payload.page >= state.pages;
}

async function loadQueue() {
  if (state.controller) state.controller.abort();
  state.controller = new AbortController();
  const params = buildQuery();
  updateLocation(params);
  setQueueMessage("Loading…");

  try {
    const response = await fetch(`/api/review-queue?${params.toString()}`, {
      signal: state.controller.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Queue request failed.");

    setSummary(payload.summary);
    populateFacet("filterType", "All types", payload.facets.evaluation_type);
    populateFacet("filterRubric", "All rubrics", payload.facets.rubric_id);
    populateFacet("filterEvaluator", "All evaluators", payload.facets.evaluator_id);
    renderRows(payload.items);
    renderPagination(payload);
    byId("queueCount").textContent = `${payload.total} matching evaluation${payload.total === 1 ? "" : "s"}`;
    setQueueMessage("");
  } catch (error) {
    if (error.name === "AbortError") return;
    setQueueMessage(error.message, "error");
    byId("queueBody").replaceChildren();
  }
}

function workflowValue(workflow, field) {
  if (!workflow) return "—";
  return workflow[field] || "—";
}

function updateSelectedRow(filename) {
  for (const row of document.querySelectorAll("#queueBody tr[data-filename]")) {
    row.classList.toggle("selected", row.dataset.filename === filename);
  }
}

async function loadDetails(filename) {
  state.selectedFilename = filename;
  updateSelectedRow(filename);
  try {
    const response = await fetch(`/api/history/${encodeURIComponent(filename)}/details`);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Evaluation details could not be loaded.");

    const evaluation = body.evaluation || {};
    const workflow = body.workflow;
    const revision = body.revision;
    byId("queueDetails").classList.remove("hidden");
    byId("detailTitle").textContent = evaluation.task_id || filename;
    byId("detailMeta").textContent = filename;
    byId("detailState").textContent = workflowValue(workflow, "state");
    byId("detailReviewOutcome").textContent = workflowValue(workflow, "review_outcome");
    byId("detailAdjudication").textContent = workflowValue(workflow, "adjudication_outcome");
    byId("detailLineage").textContent = revision
      ? `r${revision.revision_number} · parent ${revision.supersedes_artifact_id}`
      : body.superseded_by
        ? `r0 · superseded by ${body.superseded_by}`
        : "r0 · original";
    byId("detailJson").href = `/api/history/${encodeURIComponent(filename)}`;

    const reviewPanel = byId("reviewActionPanel");
    const adjudicationPanel = byId("adjudicationActionPanel");
    reviewPanel.classList.toggle("hidden", !workflow || workflow.state !== "submitted");
    adjudicationPanel.classList.toggle(
      "hidden",
      !workflow || workflow.state !== "reviewed" || workflow.review_outcome !== "escalate",
    );
    byId("queueDetails").scrollIntoView({behavior: "smooth", block: "nearest"});
  } catch (error) {
    setQueueMessage(error.message, "error");
  }
}

async function postWorkflowAction(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Workflow update failed.");
  return body;
}

async function submitReview() {
  if (!state.selectedFilename) return;
  const actorId = byId("reviewerId").value.trim();
  const outcome = byId("reviewOutcome").value;
  const note = byId("reviewNote").value;
  try {
    await postWorkflowAction(
      `/api/workflows/${encodeURIComponent(state.selectedFilename)}/review`,
      {actor_id: actorId, outcome, note},
    );
    setQueueMessage("Review decision saved.", "success");
    await loadQueue();
    await loadDetails(state.selectedFilename);
  } catch (error) {
    setQueueMessage(error.message, "error");
  }
}

async function submitAdjudication() {
  if (!state.selectedFilename) return;
  const actorId = byId("adjudicatorId").value.trim();
  const outcome = byId("adjudicationOutcome").value;
  const note = byId("adjudicationNote").value;
  try {
    await postWorkflowAction(
      `/api/workflows/${encodeURIComponent(state.selectedFilename)}/adjudicate`,
      {actor_id: actorId, outcome, note},
    );
    setQueueMessage("Adjudication saved.", "success");
    await loadQueue();
    await loadDetails(state.selectedFilename);
  } catch (error) {
    setQueueMessage(error.message, "error");
  }
}

function resetPageAndLoad() {
  state.page = 1;
  loadQueue();
}

function ensureDynamicOption(id, value) {
  if (!value) return;
  const select = byId(id);
  if (![...select.options].some((option) => option.value === value)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
  select.value = value;
}

function loadStateFromUrl() {
  const params = new URLSearchParams(location.search);
  byId("filterSearch").value = params.get("q") || "";
  byId("filterAction").value = params.get("action") || "";
  byId("filterSort").value = params.get("sort") || "priority";
  byId("filterPageSize").value = params.get("per_page") || "50";
  ensureDynamicOption("filterType", params.get("evaluation_type") || "");
  ensureDynamicOption("filterRubric", params.get("rubric_id") || "");
  ensureDynamicOption("filterEvaluator", params.get("evaluator_id") || "");
  const page = Number(params.get("page") || "1");
  state.page = Number.isInteger(page) && page > 0 ? page : 1;
}

for (const id of ["filterAction", "filterType", "filterRubric", "filterEvaluator", "filterSort", "filterPageSize"]) {
  byId(id).addEventListener("change", resetPageAndLoad);
}

byId("filterSearch").addEventListener("input", () => {
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(resetPageAndLoad, 220);
});

byId("refreshQueue").addEventListener("click", loadQueue);
byId("clearFilters").addEventListener("click", () => {
  byId("filterSearch").value = "";
  byId("filterAction").value = "";
  byId("filterType").value = "";
  byId("filterRubric").value = "";
  byId("filterEvaluator").value = "";
  byId("filterSort").value = "priority";
  byId("filterPageSize").value = "50";
  state.page = 1;
  loadQueue();
});
byId("previousPage").addEventListener("click", () => {
  if (state.page <= 1) return;
  state.page -= 1;
  loadQueue();
});
byId("nextPage").addEventListener("click", () => {
  if (state.pages && state.page >= state.pages) return;
  state.page += 1;
  loadQueue();
});
byId("submitReview").addEventListener("click", submitReview);
byId("submitAdjudication").addEventListener("click", submitAdjudication);

loadStateFromUrl();
loadQueue();
