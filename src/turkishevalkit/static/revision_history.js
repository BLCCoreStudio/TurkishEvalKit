"use strict";

const baseLoadHistoryItemForRevision = loadHistoryItem;
loadHistoryItem = async function loadHistoryItemWithRevision(filename) {
  setWorkflowMessage("");
  try {
    const response = await fetch(`/api/history/${encodeURIComponent(filename)}/details`);
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Evaluation details could not be loaded.");
    }
    state.revisionDetails = body;
    renderResult(body.evaluation, filename);
    renderWorkflow(body.workflow, filename);
    if (body.revision) {
      byId("workflowTitle").textContent =
        `${body.workflow.task_id} · Revision ${body.revision.revision_number}`;
      setWorkflowMessage(
        `Supersedes ${body.revision.supersedes_artifact_id} · root ${body.revision.root_artifact_id}`,
      );
    } else if (body.superseded_by) {
      setWorkflowMessage(`Original artifact · superseded by ${body.superseded_by}`);
    }
    byId("resultCard").scrollIntoView({behavior: "smooth", block: "nearest"});
  } catch (error) {
    setMessage(error.message, "error");
  }
};

const baseRefreshHistoryForRevision = refreshHistory;
byId("refreshHistory").removeEventListener("click", baseRefreshHistoryForRevision);

refreshHistory = async function refreshHistoryWithRevision() {
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
      const revisionLabel = item.revision_number > 0 ? ` · r${item.revision_number}` : "";
      title.textContent = `${item.task_id || item.filename}${revisionLabel}`;
      const meta = document.createElement("span");
      if (item.evaluation_type === "pairwise") {
        const preference = preferenceLabel(item.overall_preference);
        meta.textContent =
          `pairwise · ${preference} · ${formatSigned(Number(item.preference_score))} A↔B`;
      } else {
        const score = Number(item.normalized_score);
        meta.textContent =
          `${item.evaluation_type || "evaluation"} · ` +
          `${Number.isFinite(score) ? score.toFixed(2) : "—"}/100`;
      }
      if (item.superseded_by) {
        meta.textContent += " · superseded";
      }
      open.append(title, meta);
      open.addEventListener("click", () => loadHistoryItem(item.filename));

      const footer = document.createElement("div");
      footer.className = "history-footer";
      const workflow = document.createElement("span");
      workflow.className = `history-workflow ${item.workflow_state || "untracked"}`;
      workflow.textContent = item.workflow_state
        ? workflowStateLabel(item.workflow_state)
        : "Untracked";
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
};

byId("refreshHistory").addEventListener("click", refreshHistory);
