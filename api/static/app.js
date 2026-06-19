"use strict";

const SEV_COLOR = {
  critical: "var(--critical)",
  high: "var(--high)",
  medium: "var(--medium)",
  low: "var(--low)",
};

const state = { filter: "all", alerts: [] };

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json();
  if (!body.success) throw new Error(body.error || "request failed");
  return body.data;
}

function pct(x) {
  return `${Math.round((x || 0) * 100)}%`;
}

async function loadStats() {
  const s = await api("/api/stats");
  const kpis = [
    { k: "Active alerts", v: s.total_alerts },
    { k: "Needs review", v: s.flagged_for_review, cls: "warn" },
    { k: "AI-only catches", v: s.ai_only_catches, cls: "accent" },
    { k: "Reviewed", v: s.reviewed },
  ];
  document.getElementById("kpis").innerHTML = kpis
    .map(
      (i) =>
        `<div class="kpi ${i.cls || ""}"><dt>${i.k}</dt><dd>${i.v}</dd></div>`
    )
    .join("");
  const hint = document.getElementById("llm-hint");
  hint.textContent = s.llm_enabled
    ? "Gemini summaries enabled · click ✦ Explain with AI"
    : "LLM key not set · using deterministic template summaries (set GEMINI_API_KEY for Gemini)";
}

async function loadAlerts() {
  const q = state.filter === "flagged" ? "?flagged=true" : "";
  state.alerts = await api(`/api/alerts${q}`);
  render();
}

function render() {
  const feed = document.getElementById("feed");
  const tpl = document.getElementById("alert-template");
  feed.innerHTML = "";
  if (state.alerts.length === 0) {
    feed.innerHTML = `<p class="empty">No alerts match this filter.</p>`;
    return;
  }
  for (const a of state.alerts) {
    feed.appendChild(buildCard(tpl, a));
  }
  document.getElementById("footer-meta").textContent =
    `${state.alerts.length} shown`;
}

function buildCard(tpl, a) {
  const node = tpl.content.firstElementChild.cloneNode(true);
  const color = SEV_COLOR[a.severity] || "var(--line)";
  node.style.setProperty("--sev-color", color);
  if (a.flagged_for_review) node.classList.add("is-flagged");
  if (a.review_decision) node.classList.add("is-reviewed");

  node.querySelector(".sev").textContent = a.severity;
  node.querySelector(".category").textContent = a.category;
  const flag = node.querySelector(".flag");
  flag.hidden = !a.flagged_for_review;

  node.querySelector(".suspect").innerHTML =
    `Suspect: <span class="svc">${esc(a.suspect_service)}</span> · session ${esc(a.session_id)}`;
  node.querySelector(".summary").textContent = a.summary;

  const bars = node.querySelectorAll(".bar");
  setBar(bars[0], a.confidence);
  setBar(bars[1], a.anomaly_score);

  node.querySelector(".detectors").innerHTML = a.detectors
    .map((d) => `<span class="badge ${d}">${esc(d)}</span>`)
    .join("");
  node.querySelector(".commit").textContent = a.suspect_commit || "—";

  const reasons = node.querySelector(".reasons");
  if (a.flag_reasons && a.flag_reasons.length) {
    reasons.hidden = false;
    node.querySelector(".reason-tags").innerHTML = a.flag_reasons
      .map((r) => `<span class="reason-tag">${esc(r)}</span>`)
      .join("");
  }

  node.querySelector(".loglines").textContent =
    (a.sample_messages || []).join("\n");
  const redaction = node.querySelector(".redaction");
  redaction.textContent = a.redaction_categories && a.redaction_categories.length
    ? `🔒 redacted before model: ${a.redaction_categories.join(", ")}`
    : "🔒 no secrets detected in evidence";

  wireActions(node, a);
  return node;
}

function setBar(bar, value) {
  bar.querySelector(".bar-fill").style.width = pct(value);
  bar.querySelector(".bar-val").textContent = pct(value);
}

function wireActions(node, a) {
  const accept = node.querySelector('[data-action="accept"]');
  const reject = node.querySelector('[data-action="reject"]');
  const explain = node.querySelector('[data-action="explain"]');
  const verdict = node.querySelector(".verdict");

  if (a.review_decision) showVerdict(verdict, a.review_decision, accept, reject);

  accept.addEventListener("click", () => sendFeedback(a, "accept", verdict, accept, reject));
  reject.addEventListener("click", () => sendFeedback(a, "reject", verdict, accept, reject));
  explain.addEventListener("click", async () => {
    explain.disabled = true;
    explain.textContent = "✦ thinking…";
    try {
      const data = await api(`/api/alerts/${encodeURIComponent(a.alert_id)}/explain`, { method: "POST" });
      node.querySelector(".summary").textContent = data.summary;
      explain.textContent = data.llm_enabled ? "✦ AI explained" : "✦ template (no LLM key)";
    } catch (e) {
      explain.textContent = "✦ failed";
    } finally {
      setTimeout(() => { explain.disabled = false; explain.textContent = "✦ Explain with AI"; }, 1600);
    }
  });
}

async function sendFeedback(a, decision, verdict, accept, reject) {
  try {
    await api("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alert_id: a.alert_id, decision, reviewer: "on-call" }),
    });
    showVerdict(verdict, decision, accept, reject);
    loadStats();
  } catch (e) {
    verdict.hidden = false;
    verdict.textContent = "error";
  }
}

function showVerdict(verdict, decision, accept, reject) {
  verdict.hidden = false;
  verdict.className = `verdict ${decision}`;
  verdict.textContent = decision === "accept" ? "✓ confirmed incident" : "✕ marked false positive";
  accept.disabled = true;
  reject.disabled = true;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("is-active"));
    chip.classList.add("is-active");
    state.filter = chip.dataset.filter;
    loadAlerts();
  });
});

(async function init() {
  try {
    await loadStats();
    await loadAlerts();
  } catch (e) {
    document.getElementById("empty").textContent = `Failed to load: ${e.message}`;
  }
})();
