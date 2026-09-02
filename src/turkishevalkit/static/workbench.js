"use strict";

const state = {
  config: null,
  type: "text",
  rubric: null,
  currentArtifact: null,
  currentWorkflow: null,
};

const byId = (id) => document.getElementById(id);

function timestampToken() {
  return new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
}

function taskIdFor(type) {
  return `${type}-${timestampToken()}`;
}

function sessionIdFor() {
  const random = Math.random().toString(36).slice(2, 8);
  return `session-${timestampToken()}-${random}`;
}

function setMessage(text, kind = "") {
  const node = byId("message");
  node.textContent = text;
  node.className = `message ${kind}`.trim();
}

function setWorkflowMessage(text, kind = "") {
  const node = byId("workflowMessage");
  node.textContent = text;
  node.className = `message ${kind}`.trim();
}

function preferenceOutcome(value) {
  const normalized = String(value).toLowerCase();
  if (normalized === "tie") {
    return "Tie";
  }
  if (normalized === "a" || normalized === "b") {
    return `${normalized.toUpperCase()} preferred`;
  }
  return "—";
}

function preferenceLabel(value) {
  const normalized = String(value).toLowerCase();
  if (normalized === "tie") {
    return "Tie";
  }
  if (normalized === "a" || normalized === "b") {
    return normalized.toUpperCase();
  }
  return "—";
}

function titleCaseToken(value) {
  return String(value || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function loadSessionDefaults() {
  const evaluatorId = localStorage.getItem("turkishevalkit.evaluatorId") || "evaluator-local";
  const sessionId = localStorage.getItem("turkishevalkit.sessionId") || sessionIdFor();
  byId("evaluatorId").value = evaluatorId;
  byId("sessionId").value = sessionId;
  localStorage.setItem("turkishevalkit.evaluatorId", evaluatorId);
  localStorage.setItem("turkishevalkit.sessionId", sessionId);
}

function persistSessionFields() {
  const evaluatorId = byId("evaluatorId").value.trim();
  const sessionId = byId("sessionId").value.trim();
  if (evaluatorId) {
    localStorage.setItem("turkishevalkit.evaluatorId", evaluatorId);
  }
  if (sessionId) {
    localStorage.setItem("turkishevalkit.sessionId", sessionId);
  }
}

function newSession() {
  const sessionId = sessionIdFor();
  byId("sessionId").value = sessionId;
  localStorage.setItem("turkishevalkit.sessionId", sessionId);
  setWorkflowMessage("");
}

function renderSourceFields() {
  const container = byId("sourceFields");
  if (state.type === "text") {
    container.innerHTML = `
      <label class="field">
        <span>Prompt / instruction</span>
        <textarea id="sourcePrompt" rows="4"
          placeholder="The Turkish prompt or instruction shown to the model."></textarea>
      </label>
      <label class="field">
        <span>Model response</span>
        <textarea id="sourceResponse" rows="8"
          placeholder="Paste the Turkish response being evaluated."></textarea>
      </label>
    `;
    return;
  }

  if (state.type === "audio") {
    container.innerHTML = `
      <label class="field">
        <span>Audio reference</span>
        <input id="sourceAudioRef" autocomplete="off"
          placeholder="Local asset path, asset id, or other authorized reference">
        <small>The workbench stores the reference only; it does not copy audio into history.</small>
      </label>
      <label class="field">
        <span>Transcript / context</span>
        <textarea id="sourceTranscript" rows="7"
          placeholder="Optional transcript or context needed for pronunciation and prosody review."></textarea>
      </label>
    `;
    return;
  }

  container.innerHTML = `
    <label class="field">
      <span>Prompt / instruction</span>
      <textarea id="sourcePrompt" rows="4"
        placeholder="The same Turkish prompt shown to both candidates."></textarea>
    </label>
    <div class="candidate-grid">
      <label class="field candidate candidate-a">
        <span>Response A</span>
        <textarea id="sourceResponseA" rows="10"
          placeholder="Paste candidate A exactly as evaluated."></textarea>
      </label>
      <label class="field candidate candidate-b">
        <span>Response B</span>
        <textarea id="sourceResponseB" rows="10"
          placeholder="Paste candidate B exactly as evaluated."></textarea>
      </label>
    </div>
  `;
}

function renderScalarCriterion(row, criterion) {
  const scores = document.createElement("div");
  scores.className = "score-group";
  for (let score = 1; score <= 5; score += 1) {
    const input = document.createElement("input");
    input.type = "radio";
    input.name = `score-${criterion.id}`;
    input.id = `score-${criterion.id}-${score}`;
    input.value = String(score);

    const label = document.createElement("label");
    label.htmlFor = input.id;
    label.textContent = String(score);
    scores.append(input, label);
  }
  row.append(scores);
}

function renderPairwiseCriterion(row, criterion) {
  const choices = document.createElement("div");
  choices.className = "score-group preference-group";
  for (const [value, labelText] of [["a", "A"], ["tie", "Tie"], ["b", "B"]]) {
    const input = document.createElement("input");
    input.type = "radio";
    input.name = `preference-${criterion.id}`;
    input.id = `preference-${criterion.id}-${value}`;
    input.value = value;

    const label = document.createElement("label");
    label.htmlFor = input.id;
    label.textContent = labelText;
    choices.append(input, label);
  }
  row.append(choices);
}

function renderCriteria() {
  const container = byId("criteriaList");
  container.replaceChildren();

  for (const criterion of state.rubric.criteria) {
    const row = document.createElement("div");
    row.className = `criterion ${state.type === "pairwise" ? "pairwise-criterion" : ""}`.trim();
    row.dataset.criterion = criterion.id;

    const description = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = criterion.label;
    const detail = document.createElement("p");
    detail.textContent = criterion.description;
    description.append(title, detail);
    row.append(description);

    if (state.type === "pairwise") {
      renderPairwiseCriterion(row, criterion);
    } else {
      renderScalarCriterion(row, criterion);
    }

    const note = document.createElement("input");
    note.className = "criterion-note";
    note.dataset.noteFor = criterion.id;
    note.placeholder = "Criterion note (optional)";
    note.autocomplete = "off";

    row.append(note);
    container.append(row);
  }
}

function renderPairwiseOverall() {
  const container = byId("pairwiseOverall");
  if (state.type !== "pairwise") {
    container.replaceChildren();
    container.classList.add("hidden");
    return;
  }

  container.innerHTML = `
    <div class="overall-copy">
      <span class="field-label">Overall decision</span>
      <strong>Which response is better overall?</strong>
      <p>Use Tie only when neither candidate is meaningfully preferable.</p>
    </div>
    <div class="overall-controls">
      <div>
        <span class="field-label">Preference</span>
        <div class="score-group preference-group overall-preference" role="radiogroup"
          aria-label="Overall preference">
          <input type="radio" name="overall-preference" id="overall-a" value="a">
          <label for="overall-a">A</label>
          <input type="radio" name="overall-preference" id="overall-tie" value="tie">
          <label for="overall-tie">Tie</label>
          <input type="radio" name="overall-preference" id="overall-b" value="b">
          <label for="overall-b">B</label>
        </div>
      </div>
      <div>
        <span class="field-label">Strength</span>
        <div class="score-group strength-group" role="radiogroup"
          aria-label="Preference strength">
          <input type="radio" name="preference-strength" id="strength-1" value="1">
          <label for="strength-1" title="Slight preference">1</label>
          <input type="radio" name="preference-strength" id="strength-2" value="2">
          <label for="strength-2" title="Moderate preference">2</label>
          <input type="radio" name="preference-strength" id="strength-3" value="3">
          <label for="strength-3" title="Strong preference">3</label>
        </div>
      </div>
    </div>
  `;
  container.classList.remove("hidden");
}

function resetResultAndWorkflow() {
  state.currentArtifact = null;
  state.currentWorkflow = null;
  byId("resultCard").classList.add("hidden");
  byId("workflowCard").classList.add("hidden");
  byId("workflowControls").replaceChildren();
  byId("workflowEvents").replaceChildren();
  setWorkflowMessage("");
}

function setType(type) {
  state.type = type;
  state.rubric = state.config.rubrics.find((item) => item.evaluation_type === type);
  if (!state.rubric) {
    throw new Error(`No built-in rubric is available for ${type}.`);
  }

  for (const button of document.querySelectorAll(".type-button")) {
    button.classList.toggle("active", button.dataset.type === type);
  }

  byId("taskId").value = taskIdFor(type);
  byId("rubricTitle").textContent = state.rubric.title;
  byId("rubricVersion").textContent = `${state.rubric.id}@${state.rubric.version}`;
  byId("criteriaHeading").textContent =
    type === "pairwise" ? "Criterion preferences" : "Rubric ratings";
  byId("scaleHint").textContent =
    type === "pairwise" ? "Choose A, Tie, or B for every criterion" : "1 = poor · 5 = excellent";
  renderSourceFields();
  renderCriteria();
  renderPairwiseOverall();
  byId("evaluatorNote").value = "";
  byId("justificationEn").value = "";
  resetResultAndWorkflow();
  setMessage("");
}

function collectRatings() {
  return state.rubric.criteria.map((criterion) => {
    const checked = document.querySelector(`input[name="score-${criterion.id}"]:checked`);
    const note = document.querySelector(`[data-note-for="${criterion.id}"]`);
    return {
      criterion_id: criterion.id,
      score: checked ? Number(checked.value) : null,
      note: note.value.trim(),
    };
  });
}

function collectJudgments() {
  return state.rubric.criteria.map((criterion) => {
    const checked = document.querySelector(`input[name="preference-${criterion.id}"]:checked`);
    const note = document.querySelector(`[data-note-for="${criterion.id}"]`);
    return {
      criterion_id: criterion.id,
      preference: checked ? checked.value : null,
      note: note.value.trim(),
    };
  });
}

function collectSource() {
  if (state.type === "text") {
    return {
      prompt: byId("sourcePrompt").value,
      response: byId("sourceResponse").value,
    };
  }
  if (state.type === "audio") {
    return {
      audio_ref: byId("sourceAudioRef").value,
      transcript: byId("sourceTranscript").value,
    };
  }
  return {
    prompt: byId("sourcePrompt").value,
    response_a: byId("sourceResponseA").value,
    response_b: byId("sourceResponseB").value,
  };
}

function buildPayload() {
  const taskId = byId("taskId").value.trim();
  if (!taskId) {
    throw new Error("Task ID is required.");
  }
  const evaluatorId = byId("evaluatorId").value.trim();
  const sessionId = byId("sessionId").value.trim();
  if (!evaluatorId) {
    throw new Error("Evaluator ID is required for workflow attribution.");
  }
  if (!sessionId) {
    throw new Error("Session ID is required for workflow attribution.");
  }
  persistSessionFields();

  const common = {
    task_id: taskId,
    evaluation_type: state.type,
    rubric_id: state.rubric.id,
    rubric_version: state.rubric.version,
    evaluator_note: byId("evaluatorNote").value.trim(),
    justification_en: byId("justificationEn").value.trim(),
    source: collectSource(),
    metadata: {
      client: "local-workbench",
    },
    workflow_context: {
      evaluator_id: evaluatorId,
      session_id: sessionId,
    },
  };

  if (state.type === "pairwise") {
    const judgments = collectJudgments();
    if (judgments.some((item) => item.preference === null)) {
      throw new Error("Choose A, Tie, or B for every rubric criterion before saving.");
    }
    const overall = document.querySelector('input[name="overall-preference"]:checked');
    if (!overall) {
      throw new Error("Choose an overall A, Tie, or B preference before saving.");
    }
    const strength = document.querySelector('input[name="preference-strength"]:checked');
    if (!strength) {
      throw new Error("Choose preference strength from 1 to 3 before saving.");
    }
    return {
      ...common,
      judgments,
      overall_preference: overall.value,
      preference_strength: Number(strength.value),
    };
  }

  const ratings = collectRatings();
  if (ratings.some((item) => item.score === null)) {
    throw new Error("Rate every rubric criterion before saving.");
  }
  return {
    ...common,
    ratings,
  };
}

function formatSigned(value) {
  if (!Number.isFinite(value)) {
    return "—";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function renderResult(result, filename) {
  const evaluationType = result.payload ? result.payload.evaluation_type : "";
  if (evaluationType === "pairwise") {
    const outcome = preferenceOutcome(result.overall_preference);
    const score = Number(result.preference_score);
    byId("resultScore").textContent = `${outcome} · ${formatSigned(score)} A↔B`;
  } else {
    const score = Number(result.normalized_score);
    byId("resultScore").textContent = `${score.toFixed(2)} / 100`;
  }
  byId("resultTask").textContent = result.task_id;
  byId("resultDownload").href = `/api/history/${encodeURIComponent(filename)}`;
  byId("resultCard").classList.remove("hidden");
}

function workflowStateLabel(value) {
  const labels = {
    draft: "Draft",
    submitted: "Submitted",
    reviewed: "Reviewed",
    adjudicated: "Adjudicated",
  };
  return labels[value] || titleCaseToken(value) || "—";
}

function renderWorkflowEvents(workflow) {
  const container = byId("workflowEvents");
  container.replaceChildren();
  for (const event of workflow.events) {
    const row = document.createElement("div");
    row.className = "workflow-event";
    const marker = document.createElement("span");
    marker.className = "workflow-event-marker";
    marker.textContent = String(event.sequence);

    const copy = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = `${titleCaseToken(event.kind)} · ${event.actor_id}`;
    const meta = document.createElement("span");
    const extras = [];
    if (event.review_outcome) {
      extras.push(titleCaseToken(event.review_outcome));
    }
    if (event.adjudication_outcome) {
      extras.push(titleCaseToken(event.adjudication_outcome));
    }
    meta.textContent = [event.actor_role, event.occurred_at, ...extras].join(" · ");
    copy.append(heading, meta);
    if (event.note) {
      const note = document.createElement("p");
      note.textContent = event.note;
      copy.append(note);
    }
    row.append(marker, copy);
    container.append(row);
  }
}

function workflowControlField(labelText, control) {
  const label = document.createElement("label");
  label.className = "field workflow-field";
  const title = document.createElement("span");
  title.textContent = labelText;
  label.append(title, control);
  return label;
}

function makeTextInput(id, placeholder) {
  const input = document.createElement("input");
  input.id = id;
  input.autocomplete = "off";
  input.placeholder = placeholder;
  return input;
}

function makeTextarea(id, placeholder) {
  const textarea = document.createElement("textarea");
  textarea.id = id;
  textarea.rows = 3;
  textarea.placeholder = placeholder;
  return textarea;
}

function makeSelect(id, options) {
  const select = document.createElement("select");
  select.id = id;
  for (const [value, labelText] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labelText;
    select.append(option);
  }
  return select;
}

function makeActionButton(id, labelText) {
  const button = document.createElement("button");
  button.id = id;
  button.type = "button";
  button.className = "primary-button workflow-action";
  button.textContent = labelText;
  return button;
}

function renderWorkflowControls(workflow) {
  const container = byId("workflowControls");
  container.replaceChildren();
  setWorkflowMessage("");

  if (workflow.state === "draft") {
    const copy = document.createElement("p");
    copy.className = "workflow-guidance";
    copy.textContent = "The evaluation is saved as a draft. Submission freezes this artifact for independent review.";
    const note = makeTextarea("submitNote", "Optional handoff note for the reviewer.");
    const button = makeActionButton("submitWorkflowButton", "Submit for review");
    container.append(copy, workflowControlField("Handoff note", note), button);
    button.addEventListener("click", () => postWorkflowAction("submit", {
      actor_id: workflow.session.evaluator_id,
      note: note.value.trim(),
    }));
    return;
  }

  if (workflow.state === "submitted") {
    const grid = document.createElement("div");
    grid.className = "workflow-control-grid";
    const reviewer = makeTextInput("reviewerId", "Independent reviewer ID");
    const outcome = makeSelect("reviewOutcome", [
      ["accept", "Accept evaluation"],
      ["escalate", "Escalate disagreement"],
    ]);
    grid.append(
      workflowControlField("Reviewer ID", reviewer),
      workflowControlField("Review outcome", outcome),
    );
    const note = makeTextarea(
      "reviewNote",
      "Required when escalating; optional evidence note when accepting.",
    );
    const button = makeActionButton("reviewWorkflowButton", "Record review");
    container.append(grid, workflowControlField("Review note", note), button);
    button.addEventListener("click", () => postWorkflowAction("review", {
      actor_id: reviewer.value.trim(),
      outcome: outcome.value,
      note: note.value.trim(),
    }));
    return;
  }

  const latestReview = [...workflow.events].reverse().find((event) => event.review_outcome);
  if (workflow.state === "reviewed" && latestReview && latestReview.review_outcome === "escalate") {
    const grid = document.createElement("div");
    grid.className = "workflow-control-grid";
    const adjudicator = makeTextInput("adjudicatorId", "Independent adjudicator ID");
    const outcome = makeSelect("adjudicationOutcome", [
      ["evaluation_upheld", "Original evaluation upheld"],
      ["review_concern_upheld", "Reviewer concern upheld"],
      ["inconclusive", "Inconclusive"],
    ]);
    grid.append(
      workflowControlField("Adjudicator ID", adjudicator),
      workflowControlField("Resolution", outcome),
    );
    const note = makeTextarea("adjudicationNote", "Required independent resolution evidence.");
    const button = makeActionButton("adjudicateWorkflowButton", "Record adjudication");
    container.append(grid, workflowControlField("Resolution note", note), button);
    button.addEventListener("click", () => postWorkflowAction("adjudicate", {
      actor_id: adjudicator.value.trim(),
      outcome: outcome.value,
      note: note.value.trim(),
    }));
    return;
  }

  const copy = document.createElement("p");
  copy.className = "workflow-guidance terminal";
  if (workflow.state === "reviewed") {
    copy.textContent = "Independent review accepted this evaluation. No adjudication is required.";
  } else {
    const latest = workflow.events[workflow.events.length - 1];
    copy.textContent = `Adjudication complete: ${titleCaseToken(latest.adjudication_outcome)}.`;
  }
  container.append(copy);
}

function renderWorkflow(workflow, filename) {
  state.currentArtifact = filename;
  state.currentWorkflow = workflow;
  if (!workflow) {
    byId("workflowCard").classList.add("hidden");
    return;
  }

  byId("workflowTitle").textContent = workflow.task_id;
  byId("workflowState").textContent = workflowStateLabel(workflow.state);
  byId("workflowState").dataset.state = workflow.state;
  byId("workflowSession").textContent = workflow.session.session_id;
  byId("workflowEvaluator").textContent = workflow.session.evaluator_id;
  renderWorkflowEvents(workflow);
  renderWorkflowControls(workflow);
  byId("workflowCard").classList.remove("hidden");
}

async function postWorkflowAction(action, payload) {
  if (!state.currentArtifact) {
    setWorkflowMessage("No evaluation workflow is selected.", "error");
    return;
  }
  setWorkflowMessage("Validating workflow transition…");
  try {
    const response = await fetch(
      `/api/workflows/${encodeURIComponent(state.currentArtifact)}/${action}`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      },
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Workflow transition failed.");
    }
    renderWorkflow(body.workflow, state.currentArtifact);
    setWorkflowMessage("Workflow updated.", "success");
    await refreshHistory();
  } catch (error) {
    setWorkflowMessage(error.message, "error");
  }
}

async function loadHistoryItem(filename) {
  setWorkflowMessage("");
  try {
    const response = await fetch(`/api/history/${encodeURIComponent(filename)}/details`);
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Evaluation details could not be loaded.");
    }
    renderResult(body.evaluation, filename);
    renderWorkflow(body.workflow, filename);
    byId("resultCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function refreshHistory() {
  const container = byId("historyList");
  try {
    const response = await fetch("/api/history");
    if (!response.ok) {
      throw new Error("History request failed.");
    }
    const payload = await response.json();
    container.replaceChildren();

    if (payload.items.length === 0) {
      const empty = document.createElement("div");
      empty.className = "history-empty";
      empty.textContent = "No evaluations saved in this workspace yet.";
      container.append(empty);
      return;
    }

    for (const item of payload.items.slice(0, 40)) {
      const card = document.createElement("article");
      card.className = "history-item";

      const open = document.createElement("button");
      open.type = "button";
      open.className = "history-open";
      open.title = "Open evaluation workflow";
      const title = document.createElement("strong");
      title.textContent = item.task_id || item.filename;
      const meta = document.createElement("span");
      if (item.evaluation_type === "pairwise") {
        const preference = preferenceLabel(item.overall_preference);
        meta.textContent = `pairwise · ${preference} · ${formatSigned(Number(item.preference_score))} A↔B`;
      } else {
        const score = Number(item.normalized_score);
        meta.textContent =
          `${item.evaluation_type || "evaluation"} · ` +
          `${Number.isFinite(score) ? score.toFixed(2) : "—"}/100`;
      }
      open.append(title, meta);
      open.addEventListener("click", () => loadHistoryItem(item.filename));

      const footer = document.createElement("div");
      footer.className = "history-footer";
      const workflow = document.createElement("span");
      workflow.className = `history-workflow ${item.workflow_state || "untracked"}`;
      workflow.textContent = item.workflow_state ? workflowStateLabel(item.workflow_state) : "Untracked";
      const download = document.createElement("a");
      download.href = `/api/history/${encodeURIComponent(item.filename)}`;
      download.textContent = "JSON";
      download.title = "Download saved JSON";
      footer.append(workflow, download);

      card.append(open, footer);
      container.append(card);
    }
  } catch (error) {
    container.textContent = "Could not load local history.";
  }
}

async function saveEvaluation(event) {
  event.preventDefault();
  const button = byId("saveButton");

  let payload;
  try {
    payload = buildPayload();
  } catch (error) {
    setMessage(error.message, "error");
    return;
  }

  button.disabled = true;
  setMessage("Validating and saving…");

  try {
    const response = await fetch("/api/evaluations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Evaluation could not be saved.");
    }

    renderResult(body.result, body.filename);
    renderWorkflow(body.workflow, body.filename);
    setMessage("Saved to the local workspace.", "success");
    await refreshHistory();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function boot() {
  try {
    loadSessionDefaults();
    const response = await fetch("/api/config");
    if (!response.ok) {
      throw new Error("Configuration request failed.");
    }
    state.config = await response.json();
    byId("workspacePath").textContent = state.config.workspace;
    setType("text");
    await refreshHistory();
  } catch (error) {
    setMessage("Workbench initialization failed.", "error");
    byId("saveButton").disabled = true;
  }
}

for (const button of document.querySelectorAll(".type-button")) {
  button.addEventListener("click", () => setType(button.dataset.type));
}

byId("evaluationForm").addEventListener("submit", saveEvaluation);
byId("newButton").addEventListener("click", () => setType(state.type));
byId("refreshHistory").addEventListener("click", refreshHistory);
byId("newSessionButton").addEventListener("click", newSession);
byId("evaluatorId").addEventListener("change", persistSessionFields);
byId("sessionId").addEventListener("change", persistSessionFields);

boot();
