(() => {
  "use strict";

  const state = {
    candidates: [],
    selected: new Set(),
    activeCompatibilityKey: null,
    history: [],
    activeHistoryFilename: null,
    disagreementRequest: 0,
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

  function preferenceLabel(value) {
    if (value === "a") return "A";
    if (value === "b") return "B";
    if (value === "tie") return "Tie";
    return String(value || "—");
  }

  function formatTimestampMs(value) {
    const milliseconds = Math.max(0, Number(value) || 0);
    const totalSeconds = milliseconds / 1000;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds - minutes * 60;
    return `${String(minutes).padStart(2, "0")}:${seconds.toFixed(3).padStart(6, "0")}`;
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

  function resetDisagreementExplorer() {
    state.disagreementRequest += 1;
    $("disagreementExplorerSection").classList.add("hidden");
    $("disagreementStatus").textContent = "";
    $("disagreementStatus").classList.remove("error");
    $("disagreementSummary").replaceChildren();
    $("disputedCriteria").replaceChildren();
    $("overallPreferenceRows").replaceChildren();
    $("audioEvidencePairs").replaceChildren();
    $("overallPreferenceDifferences").classList.add("hidden");
    $("audioEvidenceDifferences").classList.add("hidden");
  }

  function observationCard(observation) {
    const card = document.createElement("div");
    card.className = "observation-detail";
    const head = document.createElement("div");
    head.className = "observation-detail-head";
    const evaluator = document.createElement("strong");
    evaluator.textContent = observation.evaluator_id;
    const value = document.createElement("span");
    value.className = "observation-value";
    value.textContent = preferenceLabel(observation.value);
    head.append(evaluator, value);
    const note = document.createElement("p");
    note.textContent = observation.note || "No criterion-specific evidence note.";
    if (!observation.note) note.classList.add("muted-copy");
    card.append(head, note);
    return card;
  }

  function pairDifferenceRow(pair) {
    const row = document.createElement("div");
    row.className = "pair-difference";
    const head = document.createElement("strong");
    head.textContent = `${pair.evaluator_a} ↔ ${pair.evaluator_b}`;
    const values = document.createElement("span");
    const gap = pair.gap === null || pair.gap === undefined ? "" : ` · gap ${pair.gap}`;
    values.textContent = `${preferenceLabel(pair.value_a)} ↔ ${preferenceLabel(pair.value_b)}${gap}`;
    row.append(head, values);
    if (pair.note_a || pair.note_b) {
      const notes = document.createElement("div");
      notes.className = "pair-note-grid";
      const left = document.createElement("p");
      left.textContent = pair.note_a || "No note.";
      const right = document.createElement("p");
      right.textContent = pair.note_b || "No note.";
      notes.append(left, right);
      row.appendChild(notes);
    }
    return row;
  }

  function renderCriterionDrilldown(report) {
    const target = $("disputedCriteria");
    target.replaceChildren();
    const disputed = (report.criteria || []).filter((item) => item.disagreement_pair_count > 0);
    if (!disputed.length) {
      target.appendChild(emptyState("No criterion-level disagreement was observed in this calibration."));
      return;
    }

    for (const criterion of disputed) {
      const card = document.createElement("article");
      card.className = "disagreement-card";
      const head = document.createElement("div");
      head.className = "disagreement-card-head";
      const titleWrap = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = criterion.criterion_label || criterion.criterion_id;
      const id = document.createElement("code");
      id.textContent = criterion.criterion_id;
      titleWrap.append(title, id);
      const stats = document.createElement("span");
      stats.textContent = `${criterion.disagreement_pair_count}/${criterion.total_pair_count} pairs differ · exact ${formatPercent(criterion.exact_agreement_rate)}`;
      head.append(titleWrap, stats);

      const observations = document.createElement("div");
      observations.className = "observation-detail-grid";
      for (const observation of criterion.observations || []) {
        observations.appendChild(observationCard(observation));
      }

      const pairList = document.createElement("div");
      pairList.className = "difference-list";
      for (const pair of criterion.pair_disagreements || []) {
        pairList.appendChild(pairDifferenceRow(pair));
      }
      card.append(head, observations, pairList);
      target.appendChild(card);
    }
  }

  function renderOverallDifferences(report) {
    const section = $("overallPreferenceDifferences");
    const target = $("overallPreferenceRows");
    target.replaceChildren();
    const rows = report.overall_preference_differences || [];
    section.classList.toggle("hidden", rows.length === 0);
    for (const item of rows) {
      const row = document.createElement("div");
      row.className = "pair-difference";
      const head = document.createElement("strong");
      head.textContent = `${item.evaluator_a} ↔ ${item.evaluator_b}`;
      const values = document.createElement("span");
      values.textContent = `${preferenceLabel(item.preference_a)} (strength ${item.strength_a}) ↔ ${preferenceLabel(item.preference_b)} (strength ${item.strength_b})`;
      const meta = document.createElement("small");
      meta.textContent = item.preference_changed
        ? `Overall direction differs · strength gap ${item.strength_gap}`
        : `Same overall direction · strength gap ${item.strength_gap}`;
      row.append(head, values, meta);
      target.appendChild(row);
    }
  }

  function audioEvidenceCard(evidence) {
    const card = document.createElement("div");
    card.className = "audio-evidence-card";
    const head = document.createElement("div");
    head.className = "audio-evidence-head";
    const category = document.createElement("strong");
    category.textContent = evidence.category;
    const time = document.createElement("span");
    const range = evidence.start_ms === evidence.end_ms
      ? formatTimestampMs(evidence.start_ms)
      : `${formatTimestampMs(evidence.start_ms)}–${formatTimestampMs(evidence.end_ms)}`;
    time.textContent = `${range} · ${evidence.severity}`;
    head.append(category, time);
    const note = document.createElement("p");
    note.textContent = evidence.note;
    card.append(head, note);
    return card;
  }

  function evidenceGroup(titleText, evidence) {
    const group = document.createElement("div");
    group.className = "audio-evidence-group";
    const title = document.createElement("strong");
    title.textContent = titleText;
    group.appendChild(title);
    for (const item of evidence) group.appendChild(audioEvidenceCard(item));
    return group;
  }

  function renderAudioEvidenceDifferences(report) {
    const section = $("audioEvidenceDifferences");
    const target = $("audioEvidencePairs");
    target.replaceChildren();
    const pairs = report.audio_pair_disagreements || [];
    section.classList.toggle("hidden", pairs.length === 0);

    for (const pair of pairs) {
      const card = document.createElement("article");
      card.className = "disagreement-card audio-disagreement-card";
      const head = document.createElement("div");
      head.className = "disagreement-card-head";
      const title = document.createElement("strong");
      title.textContent = `${pair.evaluator_a} ↔ ${pair.evaluator_b}`;
      const stats = document.createElement("span");
      stats.textContent = `${pair.unmatched_a.length + pair.unmatched_b.length} unmatched · ${pair.matched_variances.length} matched variance`;
      head.append(title, stats);
      card.appendChild(head);

      const unmatchedGrid = document.createElement("div");
      unmatchedGrid.className = "audio-unmatched-grid";
      if (pair.unmatched_a.length) {
        unmatchedGrid.appendChild(evidenceGroup(`Only ${pair.evaluator_a}`, pair.unmatched_a));
      }
      if (pair.unmatched_b.length) {
        unmatchedGrid.appendChild(evidenceGroup(`Only ${pair.evaluator_b}`, pair.unmatched_b));
      }
      if (unmatchedGrid.childElementCount) card.appendChild(unmatchedGrid);

      for (const variance of pair.matched_variances || []) {
        const varianceCard = document.createElement("div");
        varianceCard.className = "matched-variance";
        const varianceHead = document.createElement("div");
        varianceHead.className = "matched-variance-head";
        const titleText = document.createElement("strong");
        titleText.textContent = `Matched ${variance.left.category} evidence`;
        const meta = document.createElement("span");
        meta.textContent = `Temporal ${formatPercent(variance.temporal_similarity)} · ${variance.severity_match ? "same severity" : "severity differs"}`;
        varianceHead.append(titleText, meta);
        const pairGrid = document.createElement("div");
        pairGrid.className = "audio-unmatched-grid";
        pairGrid.append(
          evidenceGroup(variance.left.evaluator_id, [variance.left]),
          evidenceGroup(variance.right.evaluator_id, [variance.right])
        );
        varianceCard.append(varianceHead, pairGrid);
        card.appendChild(varianceCard);
      }
      target.appendChild(card);
    }
  }

  function renderDisagreementExplorer(report) {
    const section = $("disagreementExplorerSection");
    section.classList.remove("hidden");
    $("disagreementStatus").textContent = "";
    $("disagreementStatus").classList.remove("error");
    $("disagreementSummary").replaceChildren(
      metricCard("Disputed criteria", `${report.disputed_criterion_count}/${report.criterion_count}`),
      metricCard("Differing criterion pairs", String(report.disputed_criterion_pair_count ?? 0)),
      metricCard(
        "Holistic pairwise differences",
        String((report.overall_preference_differences || []).length)
      ),
      metricCard("Audio evidence pairs", String((report.audio_pair_disagreements || []).length))
    );
    renderCriterionDrilldown(report);
    renderOverallDifferences(report);
    renderAudioEvidenceDifferences(report);
  }

  async function loadDisagreements(filename) {
    resetDisagreementExplorer();
    if (!filename) return;
    const requestId = ++state.disagreementRequest;
    const section = $("disagreementExplorerSection");
    const status = $("disagreementStatus");
    section.classList.remove("hidden");
    status.textContent = "Loading evidence-level disagreement details…";
    try {
      const response = await fetch(
        `/api/calibrations/${encodeURIComponent(filename)}/disagreements`
      );
      const payload = await response.json();
      if (requestId !== state.disagreementRequest) return;
      if (!response.ok) {
        throw new Error(payload.error || "Disagreement details are unavailable.");
      }
      renderDisagreementExplorer(payload);
    } catch (error) {
      if (requestId !== state.disagreementRequest) return;
      status.textContent = error instanceof Error ? error.message : String(error);
      status.classList.add("error");
      $("disagreementSummary").replaceChildren();
      $("disputedCriteria").replaceChildren();
      $("overallPreferenceDifferences").classList.add("hidden");
      $("audioEvidenceDifferences").classList.add("hidden");
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
    void loadDisagreements(filename);
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