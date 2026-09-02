"use strict";

const AUDIO_ISSUE_CATEGORIES = [
  ["nativeness", "Nativeness"],
  ["pronunciation", "Pronunciation"],
  ["fluency", "Fluency"],
  ["intonation", "Intonation"],
  ["unnatural_pause", "Unnatural pause"],
  ["pace", "Pace"],
  ["emphasis", "Emphasis"],
  ["audio_artifact", "Audio artifact"],
  ["noise", "Noise"],
  ["clipping", "Clipping"],
  ["other", "Other"],
];

const AUDIO_ISSUE_SEVERITIES = [
  ["minor", "Minor"],
  ["major", "Major"],
  ["critical", "Critical"],
];

function audioOptionMarkup(options) {
  return options
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join("");
}

function audioAnnotationPanelMarkup() {
  return `
    <section id="audioAnnotationsPanel" class="audio-annotations-panel" aria-labelledby="audioAnnotationsTitle">
      <div class="audio-annotations-heading">
        <div>
          <span class="field-label">Localized evidence</span>
          <strong id="audioAnnotationsTitle">Timestamped audio issues</strong>
          <p>Mark a point or range without copying the referenced audio into history.</p>
        </div>
        <button id="addAudioAnnotationButton" class="audio-add-button" type="button">+ Add issue</button>
      </div>
      <div id="audioAnnotationList" class="audio-annotation-list"></div>
      <div class="audio-annotation-help">
        Time accepts <code>12.5</code>, <code>01:12.500</code>, or <code>00:01:12.500</code>.
        Leave End empty to create a point marker.
      </div>
    </section>
  `;
}

function parseAudioTimestamp(value, fieldName) {
  const raw = String(value || "").trim();
  if (!raw) {
    throw new Error(`${fieldName} is required for every audio issue.`);
  }

  const parts = raw.split(":");
  if (parts.length > 3) {
    throw new Error(`${fieldName} must use seconds, MM:SS, or HH:MM:SS.`);
  }

  const numbers = parts.map((part) => Number(part));
  if (numbers.some((part) => !Number.isFinite(part) || part < 0)) {
    throw new Error(`${fieldName} must be a non-negative timestamp.`);
  }

  if (parts.length >= 2 && numbers[numbers.length - 1] >= 60) {
    throw new Error(`${fieldName} seconds must be below 60 when using colon notation.`);
  }
  if (parts.length === 3 && numbers[1] >= 60) {
    throw new Error(`${fieldName} minutes must be below 60 when using HH:MM:SS.`);
  }

  let seconds = 0;
  for (const part of numbers) {
    seconds = seconds * 60 + part;
  }
  return Math.round(seconds * 1000);
}

function formatAudioTimestamp(ms) {
  const totalSeconds = ms / 1000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${seconds.toFixed(3).padStart(6, "0")}`;
}

function updateAudioAnnotationIndices() {
  const rows = document.querySelectorAll(".audio-annotation-row");
  rows.forEach((row, index) => {
    row.dataset.index = String(index);
    const badge = row.querySelector(".audio-annotation-index");
    if (badge) {
      badge.textContent = String(index + 1).padStart(2, "0");
    }
  });
}

function addAudioAnnotationRow(initial = null) {
  const list = byId("audioAnnotationList");
  if (!list) {
    return;
  }

  const row = document.createElement("article");
  row.className = "audio-annotation-row";
  row.innerHTML = `
    <div class="audio-annotation-index" aria-hidden="true"></div>
    <div class="audio-time-grid">
      <label class="field audio-annotation-field">
        <span>Start</span>
        <input class="audio-start" autocomplete="off" inputmode="decimal" placeholder="00:04.200">
      </label>
      <label class="field audio-annotation-field">
        <span>End <em>optional</em></span>
        <input class="audio-end" autocomplete="off" inputmode="decimal" placeholder="point marker">
      </label>
    </div>
    <div class="audio-classification-grid">
      <label class="field audio-annotation-field">
        <span>Issue type</span>
        <select class="audio-category">${audioOptionMarkup(AUDIO_ISSUE_CATEGORIES)}</select>
      </label>
      <label class="field audio-annotation-field">
        <span>Severity</span>
        <select class="audio-severity">${audioOptionMarkup(AUDIO_ISSUE_SEVERITIES)}</select>
      </label>
    </div>
    <label class="field audio-annotation-field audio-note-field">
      <span>Evidence note</span>
      <input class="audio-note" autocomplete="off"
        placeholder="What is audible at this point or interval?">
    </label>
    <button class="audio-remove-button" type="button" aria-label="Remove audio issue">Remove</button>
  `;

  const start = row.querySelector(".audio-start");
  const end = row.querySelector(".audio-end");
  const category = row.querySelector(".audio-category");
  const severity = row.querySelector(".audio-severity");
  const note = row.querySelector(".audio-note");

  if (initial) {
    start.value = formatAudioTimestamp(initial.start_ms);
    end.value = initial.end_ms === initial.start_ms ? "" : formatAudioTimestamp(initial.end_ms);
    category.value = initial.category;
    severity.value = initial.severity;
    note.value = initial.note;
  }

  row.querySelector(".audio-remove-button").addEventListener("click", () => {
    row.remove();
    updateAudioAnnotationIndices();
  });

  list.append(row);
  updateAudioAnnotationIndices();
  start.focus();
}

function collectAudioAnnotations() {
  const list = byId("audioAnnotationList");
  if (!list) {
    return [];
  }

  return [...list.querySelectorAll(".audio-annotation-row")].map((row, index) => {
    const number = index + 1;
    const startMs = parseAudioTimestamp(
      row.querySelector(".audio-start").value,
      `Audio issue ${number} start`,
    );
    const endRaw = row.querySelector(".audio-end").value.trim();
    const endMs = endRaw
      ? parseAudioTimestamp(endRaw, `Audio issue ${number} end`)
      : startMs;
    if (endMs < startMs) {
      throw new Error(`Audio issue ${number} end must not be before its start.`);
    }

    const note = row.querySelector(".audio-note").value.trim();
    if (!note) {
      throw new Error(`Audio issue ${number} needs an evidence note.`);
    }

    return {
      start_ms: startMs,
      end_ms: endMs,
      category: row.querySelector(".audio-category").value,
      severity: row.querySelector(".audio-severity").value,
      note,
    };
  });
}

const baseRenderSourceFieldsForAudioAnnotations = renderSourceFields;
renderSourceFields = function renderSourceFieldsWithAudioAnnotations() {
  baseRenderSourceFieldsForAudioAnnotations();
  if (state.type !== "audio") {
    return;
  }

  byId("sourceFields").insertAdjacentHTML("beforeend", audioAnnotationPanelMarkup());
  byId("addAudioAnnotationButton").addEventListener("click", () => addAudioAnnotationRow());
};

const baseBuildPayloadForAudioAnnotations = buildPayload;
buildPayload = function buildPayloadWithAudioAnnotations() {
  const payload = baseBuildPayloadForAudioAnnotations();
  if (state.type === "audio") {
    payload.audio_annotations = collectAudioAnnotations();
  }
  return payload;
};
