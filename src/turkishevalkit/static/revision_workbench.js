"use strict";

state.revisionBase = null;
state.revisionDetails = null;
state.loadingRevision = false;

const baseSetTypeForRevision = setType;
setType = function setTypeWithRevisionReset(type) {
  if (state.revisionBase && !state.loadingRevision) {
    state.revisionBase = null;
    state.revisionDetails = null;
    byId("saveButton").textContent = "Validate & save evaluation";
  }
  baseSetTypeForRevision(type);
};

const baseWorkflowStateLabelForRevision = workflowStateLabel;
workflowStateLabel = function workflowStateLabelWithRevision(value) {
  const labels = {
    revision_requested: "Revision requested",
    superseded: "Superseded",
  };
  return labels[value] || baseWorkflowStateLabelForRevision(value);
};

function latestReviewEvent(workflow) {
  return [...workflow.events].reverse().find((event) => event.review_outcome) || null;
}

function revisionGuidance(workflow) {
  const review = latestReviewEvent(workflow);
  const copy = document.createElement("p");
  copy.className = "workflow-guidance";
  copy.textContent = review && review.note
    ? `Reviewer requested a new immutable revision: ${review.note}`
    : "Reviewer requested a new immutable revision.";
  return copy;
}

const baseRenderWorkflowControlsForRevision = renderWorkflowControls;
renderWorkflowControls = function renderWorkflowControlsWithRevision(workflow) {
  const container = byId("workflowControls");

  if (workflow.state === "submitted") {
    container.replaceChildren();
    setWorkflowMessage("");
    const grid = document.createElement("div");
    grid.className = "workflow-control-grid";
    const reviewer = makeTextInput("reviewerId", "Independent reviewer ID");
    const outcome = makeSelect("reviewOutcome", [
      ["accept", "Accept evaluation"],
      ["request_changes", "Request changes / new revision"],
      ["escalate", "Escalate disagreement"],
    ]);
    grid.append(
      workflowControlField("Reviewer ID", reviewer),
      workflowControlField("Review outcome", outcome),
    );
    const note = makeTextarea(
      "reviewNote",
      "Required for request changes or escalation; describe the evidence precisely.",
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

  if (workflow.state === "revision_requested") {
    container.replaceChildren();
    setWorkflowMessage("");
    const button = makeActionButton("startRevisionButton", "Create requested revision");
    container.append(revisionGuidance(workflow), button);
    button.addEventListener("click", () => startRequestedRevision(state.currentArtifact));
    return;
  }

  if (workflow.state === "superseded") {
    container.replaceChildren();
    setWorkflowMessage("");
    const copy = document.createElement("p");
    copy.className = "workflow-guidance terminal";
    const child = workflow.events.find((event) => event.kind === "revision_created");
    copy.textContent = child && child.related_artifact_id
      ? `This artifact is immutable and has been superseded by ${child.related_artifact_id}.`
      : "This artifact is immutable and has been superseded by a revision.";
    container.append(copy);
    return;
  }

  baseRenderWorkflowControlsForRevision(workflow);
};

function setValue(id, value) {
  const node = byId(id);
  if (node) {
    node.value = value == null ? "" : String(value);
  }
}

function prefillScalar(record) {
  for (const rating of record.ratings || []) {
    const input = document.querySelector(
      `input[name="score-${rating.criterion_id}"][value="${rating.score}"]`,
    );
    if (input) {
      input.checked = true;
    }
    const note = document.querySelector(`[data-note-for="${rating.criterion_id}"]`);
    if (note) {
      note.value = rating.note || "";
    }
  }
}

function prefillPairwise(record) {
  for (const judgment of record.judgments || []) {
    const input = document.querySelector(
      `input[name="preference-${judgment.criterion_id}"][value="${judgment.preference}"]`,
    );
    if (input) {
      input.checked = true;
    }
    const note = document.querySelector(`[data-note-for="${judgment.criterion_id}"]`);
    if (note) {
      note.value = judgment.note || "";
    }
  }
  const overall = document.querySelector(
    `input[name="overall-preference"][value="${record.overall_preference}"]`,
  );
  if (overall) {
    overall.checked = true;
  }
  const strength = document.querySelector(
    `input[name="preference-strength"][value="${record.preference_strength}"]`,
  );
  if (strength) {
    strength.checked = true;
  }
}

function prefillSource(record) {
  const source = record.source || {};
  if (record.evaluation_type === "text") {
    setValue("sourcePrompt", source.prompt);
    setValue("sourceResponse", source.response);
  } else if (record.evaluation_type === "audio") {
    setValue("sourceAudioRef", source.audio_ref);
    setValue("sourceTranscript", source.transcript);
    const list = byId("audioAnnotationList");
    if (list) {
      list.replaceChildren();
      for (const annotation of record.audio_annotations || []) {
        addAudioAnnotationRow(annotation);
      }
    }
  } else {
    setValue("sourcePrompt", source.prompt);
    setValue("sourceResponseA", source.response_a);
    setValue("sourceResponseB", source.response_b);
  }
}

function lockRevisionIdentityFields() {
  byId("taskId").readOnly = true;
  for (const id of [
    "sourcePrompt",
    "sourceResponse",
    "sourceAudioRef",
    "sourceTranscript",
    "sourceResponseA",
    "sourceResponseB",
  ]) {
    const node = byId(id);
    if (node) {
      node.readOnly = true;
    }
  }
}

function unlockRevisionIdentityFields() {
  byId("taskId").readOnly = false;
  for (const id of [
    "sourcePrompt",
    "sourceResponse",
    "sourceAudioRef",
    "sourceTranscript",
    "sourceResponseA",
    "sourceResponseB",
  ]) {
    const node = byId(id);
    if (node) {
      node.readOnly = false;
    }
  }
}

async function startRequestedRevision(filename) {
  if (!filename) {
    setWorkflowMessage("No revision base is selected.", "error");
    return;
  }
  try {
    const response = await fetch(`/api/history/${encodeURIComponent(filename)}/details`);
    const details = await response.json();
    if (!response.ok) {
      throw new Error(details.error || "Revision base could not be loaded.");
    }
    if (!details.workflow || details.workflow.state !== "revision_requested") {
      throw new Error("This artifact is not awaiting requested changes.");
    }
    const record = details.evaluation && details.evaluation.payload;
    if (!record) {
      throw new Error("Revision base does not contain an evaluation payload.");
    }

    state.loadingRevision = true;
    state.revisionBase = filename;
    state.revisionDetails = details;
    baseSetTypeForRevision(record.evaluation_type);
    state.loadingRevision = false;
    state.revisionBase = filename;
    state.revisionDetails = details;

    setValue("taskId", record.task_id);
    setValue("evaluatorId", details.workflow.session.evaluator_id);
    newSession();
    prefillSource(record);
    if (record.evaluation_type === "pairwise") {
      prefillPairwise(record);
    } else {
      prefillScalar(record);
    }
    setValue("evaluatorNote", record.evaluator_note);
    setValue("justificationEn", record.justification_en);
    lockRevisionIdentityFields();
    byId("saveButton").textContent = "Save immutable revision";
    setMessage(`Revision mode · supersedes ${filename}`, "success");
    document.querySelector(".session-card").scrollIntoView({behavior: "smooth", block: "start"});
  } catch (error) {
    state.loadingRevision = false;
    setWorkflowMessage(error.message, "error");
  }
}

const baseSaveEvaluationForRevision = saveEvaluation;
byId("evaluationForm").removeEventListener("submit", baseSaveEvaluationForRevision);

saveEvaluation = async function saveEvaluationWithRevision(event) {
  if (!state.revisionBase) {
    unlockRevisionIdentityFields();
    return baseSaveEvaluationForRevision(event);
  }

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
  setMessage("Validating and saving immutable revision…");
  try {
    const response = await fetch(
      `/api/evaluations/${encodeURIComponent(state.revisionBase)}/revisions`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      },
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Revision could not be saved.");
    }

    state.revisionBase = null;
    state.revisionDetails = null;
    unlockRevisionIdentityFields();
    byId("saveButton").textContent = "Validate & save evaluation";
    renderResult(body.result, body.filename);
    renderWorkflow(body.workflow, body.filename);
    setMessage(`Revision ${body.revision.revision_number} saved to local history.`, "success");
    await refreshHistory();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
};

byId("evaluationForm").addEventListener("submit", saveEvaluation);
