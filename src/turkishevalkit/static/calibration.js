(() => {
  "use strict";

  const state = {
    candidates: [],
    selected: new Set(),
    activeCompatibilityKey: null,
    history: [],
    activeHistoryFilename: null,
  };

  const $ = (id) => document.getElementById(id);
  const candidateGroups = $("candidateGroups");
  const historyList = $("calibrationHistory");
  const createButton = $("createCalibration");
  const message = $("calibrationMessage");
  const reportPanel = $("reportPanel");

  function formatPercent(value) {
    if (value === null || value === undefined) return "—";
    return `${(Number(value) * 100).toFixed(1)}%`;
  }

  function formatNumber(value, digits = 2) {
    if (value === null || value === undefined) return "—";
    return Number(value).toFixed(digits).replace(/\.00$/, "");
  }

  function setMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle("error", isError);
  }

  function emptyState(text) {
    const node = document.createElement("div");
    node.className = "empty-state";
    node.textContent = text;
    return node;
  }

  function scoreLabel(candidate) {
    if (candidate.normalized_score !== null && candidate.normalized_score !== undefined) {
      return `${formatNumber(candidate.normalized_score, 1)}/100`;
    }
    if (candidate.preference_score !== null && candidate.preference_score !== undefined) {
      return `${formatNumber(candidate.preference_score, 1)}`;
    }
    return "—";
  }

  function selectionChanged() {
    const selectedCandidates = state.candidates.filter((item) => state.selected.has(item.filename));
    state.activeCompatibilityKey = selectedCandidates.length
      ? selectedCandidates[0].compatibility_key
      : null;
    createButton.disabled = selectedCandidates.length < 2;
    renderCandidates();
  }

  function toggleCandidate(candidate, checked) {
    if (checked) {
      if (
        state.activeCompatibilityKey &&
        state.activeCompatibilityKey !== candidate.compatibility_key
      ) {
        return;
      }
      state.selected.add(candidate.filename);
    } else {
      state.selected.delete(candidate.filename);
    }
    selectionChanged();
  }

  function renderCandidates() {
    candidateGroups.replaceChildren();
    if (!state.candidates.length) {
      candidateGroups.appendChild(
        emptyState("No saved evaluations are available in this workspace yet.")
      );
      return;
    }

    const grouped = new Map();
    for (const candidate of state.candidates) {
      if (!grouped.has(candidate.compatibility_key)) grouped.set(candidate.compatibility_key, []);
      grouped.get(candidate.compatibility_key).push(candidate);
    }

    for (const [, candidates] of grouped) {
      const first = candidates[0];
      const group = document.createElement("section");
      group.className = "candidate-group";

      const head = document.createElement("div");
      head.className = "candidate-group-head";
      const titleWrap = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = first.task_id || "Untitled task";
      const meta = document.createElement("div");
      meta.className = "candidate-group-meta";
      meta.textContent = `${first.evaluation_type} · ${first.rubric_id}@${first.rubric_version}`;
      titleWrap.append(title, meta);
      const count = document.createElement("span");
      count.className = "candidate-group-meta";
      const readyCount = candidates.filter((item) => item.calibration_ready).length;
      count.textContent = `${readyCount}/${candidates.length} ready`;
      head.append(titleWrap, count);
      group.appendChild(head);

      const list = document.createElement("div");
      list.className = "candidate-list";
      for (const candidate of candidates) {
        const row = document.createElement("label");
        row.className = "candidate-row";
        const incompatible = Boolean(
          state.activeCompatibilityKey &&
            state.activeCompatibilityKey !== candidate.compatibility_key
        );
        const unavailable = !candidate.calibration_ready;
        if (incompatible || unavailable) row.classList.add("disabled");

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = state.selected.has(candidate.filename);
        checkbox.disabled = incompatible || unavailable;
        checkbox.addEventListener("change", () => toggleCandidate(candidate, checkbox.checked));

        const info = document.createElement("div");
        const evaluator = document.createElement("strong");
        evaluator.textContent = candidate.evaluator_id || "Missing evaluator identity";
        const candidateMeta = document.createElement("div");
        candidateMeta.className = "candidate-meta";
        candidateMeta.textContent = unavailable
          ? "Not calibration-ready · save with an evaluator session"
          : new Date(candidate.saved_at).toLocaleString();
        info.append(evaluator, candidateMeta);

        const score = document.createElement("span");
        score.className = "candidate-score";
        score.textContent = scoreLabel(candidate);
        row.append(checkbox, info, score);
        list.appendChild(row);
      }
      group.appendChild(list);
      candidateGroups.appendChild(group);
    }
  }

  async function loadCandidates() {
    setMessage("");
    const response = await fetch("/api/calibrations/candidates");
    if (!response.ok) throw new Error("Could not load evaluation candidates.");
    const payload = await response.json();
    state.candidates = Array.isArray(payload.items) ? payload.items : [];
    const available = new Set(state.candidates.map((item) => item.filename));
    state.selected = new Set([...state.selected].filter((item) => available.has(item)));
    selectionChanged();
  }

  function renderHistory() {
    historyList.replaceChildren();
    if (!state.history.length) {
      historyList.appendChild(emptyState("No calibration artifacts have been saved yet."));
      return;
    }

    for (const item of state.history) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "history-item";
      if (state.activeHistoryFilename === item.filename) button.classList.add("active");

      const title = document.createElement("strong");
      title.textContent = item.task_id || "Untitled calibration";
      const meta = document.createElement("div");
      meta.className = "history-meta";
      meta.textContent = `${item.evaluation_type} · ${item.evaluator_count || 0} evaluators · ${new Date(item.created_at).toLocaleString()}`;
      const stats = document.createElement("div");
      stats.className = "history-statline";
      const exact = document.createElement("span");
      exact.textContent = `Exact ${formatPercent(item.exact_criterion_agreement_rate)}`;
      const spread = document.createElement("span");
      spread.textContent = `Spread ${formatNumber(item.aggregate_score_spread)}`;
      stats.append(exact, spread);
      button.append(title, meta, stats);
      button.addEventListener("click", () => loadCalibrationDetails(item.filename));
      historyList.appendChild(button);
    }
  }

  async function loadHistory() {
    const response = await fetch("/api/calibrations");
    if (!response.ok) throw new Error("Could not load calibration history.");
    const payload = await response.json();
    state.history = Array.isArray(payload.items) ? payload.items : [];
    renderHistory();
  }

  function metricCard(label, value) {
    const card = document.createElement("div");
    card.className = "metric-card";
    const title = document.createElement("span");
    title.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    card.append(title, strong);
    return card;
  }

  function renderSummary(report) {
    const metrics = $("summaryMetrics");
    metrics.replaceChildren();
    metrics.append(
      metricCard("Evaluators", String(report.evaluator_count ?? "—")),
      metricCard("Exact criterion agreement", formatPercent(report.exact_criterion_agreement_rate)),
      metricCard("Aggregate score spread", formatNumber(report.aggregate_score_spread)),
      metricCard(
        report.overall_preference_agreement_rate !== null &&
          report.overall_preference_agreement_rate !== undefined
          ? "Overall preference agreement"
          : "Within ±1 rating",
        report.overall_preference_agreement_rate !== null &&
          report.overall_preference_agreement_rate !== undefined
          ? formatPercent(report.overall_preference_agreement_rate)
          : formatPercent(report.within_one_criterion_agreement_rate)
      )
    );
  }

  function renderAggregates(report) {
    const target = $("aggregateScores");
    target.replaceChildren();
    const entries = Object.entries(report.aggregate_scores || {});
    if (!entries.length) {
      target.appendChild(emptyState("No aggregate scores are present in this report."));
      return;
    }
    const pairwise = String(report.aggregate_score_scale || "").startsWith("-100");
    for (const [evaluatorId, rawValue] of entries) {
      const value = Number(rawValue);
      const row = document.createElement("div");
      row.className = "aggregate-row";
      const name = document.createElement("strong");
      name.textContent = evaluatorId;
      const track = document.createElement("div");
      track.className = "aggregate-track";
      const fill = document.createElement("div");
      fill.className = "aggregate-fill";
      const percentage = pairwise ? (value + 100) / 2 : value;
      fill.style.width = `${Math.max(0, Math.min(100, percentage))}%`;
      track.appendChild(fill);
      const display = document.createElement("span");
      display.className = "aggregate-value";
      display.textContent = formatNumber(value, 1);
      row.append(name, track, display);
      target.appendChild(row);
    }
  }

  function renderCriteria(report) {
    const target = $("criterionRows");
    target.replaceChildren();
    const entries = Object.entries(report.criterion_agreement || {});
    for (const [criterionId, criterion] of entries) {
      const row = document.createElement("tr");
      const idCell = document.createElement("td");
      idCell.textContent = criterionId;
      const agreementCell = document.createElement("td");
      agreementCell.textContent = formatPercent(criterion.exact_agreement_rate);
      const observationsCell = document.createElement("td");
      const chips = document.createElement("div");
      chips.className = "observation-chips";
      for (const [value, count] of Object.entries(criterion.observations || {})) {
        const chip = document.createElement("span");
        chip.className = "observation-chip";
        chip.textContent = `${value}: ${count}`;
        chips.appendChild(chip);
      }
      observationsCell.appendChild(chips);
      const differenceCell = document.createElement("td");
      differenceCell.textContent = criterion.mean_absolute_difference === null ||
        criterion.mean_absolute_difference === undefined
        ? "—"
        : `MAD ${formatNumber(criterion.mean_absolute_difference, 2)} · ${criterion.min_rating}–${criterion.max_rating}`;
      row.append(idCell, agreementCell, observationsCell, differenceCell);
      target.appendChild(row);
    }
  }

  function renderAudio(report) {
    const section = $("audioAgreementSection");
    const audio = report.audio_annotation_agreement;
    section.classList.toggle("hidden", !audio);
    if (!audio) return;

    const summary = $("audioSummary");
    summary.replaceChildren(
      metricCard("Mean pairwise F1", formatPercent(audio.mean_pairwise_f1)),
      metricCard("Severity agreement", formatPercent(audio.severity_agreement_rate)),
      metricCard("Temporal similarity", formatPercent(audio.mean_temporal_similarity))
    );

    const rows = $("audioPairRows");
    rows.replaceChildren();
    for (const pair of audio.pair_agreements || []) {
      const row = document.createElement("tr");
      const cells = [
        `${pair.evaluator_a} ↔ ${pair.evaluator_b}`,
        `${pair.matched_count}/${Math.max(pair.annotation_count_a, pair.annotation_count_b)}`,
        formatPercent(pair.f1),
        formatPercent(pair.severity_agreement_rate),
        formatPercent(pair.mean_temporal_similarity),
      ];
      for (const value of cells) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      }
      rows.appendChild(row);
    }
  }

  function renderReport(artifact) {
    const report = artifact.report || {};
    const filename = artifact.filename || artifact._filename || "";
    $("reportTitle").textContent = report.task_id || "Calibration report";
    $("reportSubtitle").textContent = `${report.evaluation_type || ""} · ${report.rubric_id || ""}@${report.rubric_version || ""} · ${report.aggregate_score_scale || ""}`;
    $("reportDownload").href = filename
      ? `/api/calibrations/${encodeURIComponent(filename)}/download`
      : "#";
    renderSummary(report);
    renderAggregates(report);
    renderCriteria(report);
    renderAudio(report);
    reportPanel.classList.remove("hidden");
    reportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function createCalibration() {
    const filenames = [...state.selected];
    if (filenames.length < 2) return;
    setMessage("Generating calibration report…");
    createButton.disabled = true;
    try {
      const tolerance = Number.parseInt($("toleranceMs").value, 10);
      const response = await fetch("/api/calibrations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filenames,
          annotation_tolerance_ms: Number.isFinite(tolerance) ? tolerance : 250,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Calibration failed.");
      state.activeHistoryFilename = payload.filename;
      renderReport({ ...payload, _filename: payload.filename });
      setMessage(`Saved ${payload.filename}`);
      await loadHistory();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error), true);
    } finally {
      createButton.disabled = state.selected.size < 2;
    }
  }

  async function loadCalibrationDetails(filename) {
    try {
      const response = await fetch(`/api/calibrations/${encodeURIComponent(filename)}/details`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not load calibration artifact.");
      state.activeHistoryFilename = filename;
      renderHistory();
      renderReport({ ...payload, _filename: filename });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error), true);
    }
  }

  async function refreshAll() {
    try {
      await Promise.all([loadCandidates(), loadHistory()]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error), true);
    }
  }

  $("refreshCandidates").addEventListener("click", loadCandidates);
  $("refreshCalibrations").addEventListener("click", loadHistory);
  createButton.addEventListener("click", createCalibration);
  refreshAll();
})();
