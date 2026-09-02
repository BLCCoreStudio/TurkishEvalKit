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
      if (item.evaluation_type === "pairwise") {
        const preference = String(item.overall_preference || "—").toUpperCase();
        meta.textContent = `pairwise · ${preference} · ${formatSigned(Number(item.preference_score))} A↔B`;
      } else {
        const score = Number(item.normalized_score);
        meta.textContent =
          `${item.evaluation_type || "evaluation"} · ` +
          `${Number.isFinite(score) ? score.toFixed(2) : "—"}/100`;
      }
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

    if (state.type === "pairwise") {
      const preference = String(body.result.overall_preference).toUpperCase();
      const score = Number(body.result.preference_score);
      byId("resultScore").textContent = `${preference} preferred · ${formatSigned(score)} A↔B`;
    } else {
      const score = Number(body.result.normalized_score);
      byId("resultScore").textContent = `${score.toFixed(2)} / 100`;
    }
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
