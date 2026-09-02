"use strict";

const state = {
  config: null,
  type: "text",
  rubric: null,
};

const byId = (id) => document.getElementById(id);

function taskIdFor(type) {
  const now = new Date();
  const stamp = now.toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  return `${type}-${stamp}`;
}

function setMessage(text, kind = "") {
  const node = byId("message");
  node.textContent = text;
  node.className = `message ${kind}`.trim();
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
  } else {
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
  }
}

function renderCriteria() {
  const container = byId("criteriaList");
  container.replaceChildren();

  for (const criterion of state.rubric.criteria) {
    const row = document.createElement("div");
    row.className = "criterion";
    row.dataset.criterion = criterion.id;

    const description = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = criterion.label;
    const detail = document.createElement("p");
    detail.textContent = criterion.description;
    description.append(title, detail);

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

    const note = document.createElement("input");
    note.className = "criterion-note";
    note.dataset.noteFor = criterion.id;
    note.placeholder = "Criterion note (optional)";
    note.autocomplete = "off";

    row.append(description, scores, note);
    container.append(row);
  }
}

function setType(type) {
  state.type = type;
  state.rubric = state.config.rubrics.find((item) => item.evaluation_type === type);

  for (const button of document.querySelectorAll(".type-button")) {
    button.classList.toggle("active", button.dataset.type === type);
  }

  byId("taskId").value = taskIdFor(type);
  byId("rubricTitle").textContent = state.rubric.title;
  byId("rubricVersion").textContent = `${state.rubric.id}@${state.rubric.version}`;
  renderSourceFields();
  renderCriteria();
  byId("evaluatorNote").value = "";
  byId("justificationEn").value = "";
  byId("resultCard").classList.add("hidden");
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

function collectSource() {
  if (state.type === "text") {
    return {
      prompt: byId("sourcePrompt").value,
      response: byId("sourceResponse").value,
    };
  }
  return {
    audio_ref: byId("sourceAudioRef").value,
    transcript: byId("sourceTranscript").value,
  };
}

function buildPayload() {
  const ratings = collectRatings();
  if (ratings.some((item) => item.score === null)) {
    throw new Error("Rate every rubric criterion before saving.");
  }

  const taskId = byId("taskId").value.trim();
  if (!taskId) {
    throw new Error("Task ID is required.");
  }

  return {
    task_id: taskId,
    evaluation_type: state.type,
    rubric_id: state.rubric.id,
    rubric_version: state.rubric.version,
    ratings,
    evaluator_note: byId("evaluatorNote").value.trim(),
    justification_en: byId("justificationEn").value.trim(),
    source: collectSource(),
    metadata: {
      client: "local-workbench",
    },
  };
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
      const link = document.createElement("a");
      link.className = "history-item";
      link.href = `/api/history/${encodeURIComponent(item.filename)}`;
      link.title = "Download saved JSON";

      const title = document.createElement("strong");
      title.textContent = item.task_id || item.filename;
      const meta = document.createElement("span");
      const score = Number(item.normalized_score);
      meta.textContent =
        `${item.evaluation_type || "evaluation"} · ` +
        `${Number.isFinite(score) ? score.toFixed(2) : "—"}/100`;
      link.append(title, meta);
      container.append(link);
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

    const score = Number(body.result.normalized_score);
    byId("resultScore").textContent = `${score.toFixed(2)} / 100`;
    byId("resultTask").textContent = body.result.task_id;
    byId("resultDownload").href = `/api/history/${encodeURIComponent(body.filename)}`;
    byId("resultCard").classList.remove("hidden");
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

boot();
