const STAGE_ORDER = ["discovery", "vuln", "exploit"];
const STAGE_LABEL = { discovery: "Discovery", vuln: "Vulnerability Analysis", exploit: "Exploitation" };

let stream = null;
let running = false;

document.addEventListener("DOMContentLoaded", () => {
  setupTopTabs();
  setupContentTabs();
  document.getElementById("start-btn").addEventListener("click", startRun);
  bootstrap();
});

/* ---------- Tab navigation ---------- */
function setupTopTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      if (tab.disabled) return;
      activateTab(tab.dataset.tab);
    });
  });
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
}

function setupContentTabs() {
  document.querySelectorAll(".ct").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      const container = btn.closest(".content");
      container.querySelectorAll(".ct").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      container.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.dataset.view === view));
    });
  });
}

function showContentView(stage, suffix) {
  const container = document.getElementById(`log-${stage}`).closest(".content");
  container.querySelectorAll(".ct").forEach((b) => b.classList.toggle("active", b.dataset.view === `${stage}-${suffix}`));
  container.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.dataset.view === `${stage}-${suffix}`));
}

/* ---------- Bootstrap: reconnect to an in-progress or finished run ---------- */
async function bootstrap() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.target) document.getElementById("target-input").value = data.target;
    if (data.status === "running") {
      running = true;
      document.getElementById("start-btn").disabled = true;
      openStream();
    } else if (data.status === "done" && data.report_ready) {
      // Replay a finished run so the tabs are populated after a refresh.
      openStream();
    }
  } catch (e) {
    console.error(e);
  }
}

/* ---------- Start a run ---------- */
async function startRun() {
  if (running) return;
  const target = document.getElementById("target-input").value.trim() || "metasploitable";
  resetAll();
  document.getElementById("start-btn").disabled = true;
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      document.getElementById("start-btn").disabled = false;
      logRow("discovery", "ERR", body.error || "Could not start the pipeline.");
      return;
    }
    running = true;
    openStream();
  } catch (e) {
    document.getElementById("start-btn").disabled = false;
    logRow("discovery", "ERR", "Network error starting the pipeline.");
  }
}

function resetAll() {
  STAGE_ORDER.forEach((stage) => {
    document.getElementById(`log-${stage}`).innerHTML = "";
    document.getElementById(`output-${stage}`).innerHTML = '<div class="log-empty">Agent is running…</div>';
    setPill(stage, "idle");
    setDot(stage, "");
    setSteps(stage, "");
  });
  ["metric-ports", "metric-vulns", "metric-attempts", "metric-confirmed"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = "–";
  });
  ["vuln", "exploit", "report"].forEach(lockTab);
  const fr = document.getElementById("final-report");
  fr.innerHTML = '<div class="log-empty">The final report will appear here once the pipeline completes.</div>';
  setDot("report", "");
  activateTab("discovery");
}

/* ---------- SSE stream ---------- */
function openStream() {
  if (stream) stream.close();
  stream = new EventSource("/api/stream");
  stream.onmessage = (evt) => {
    let msg;
    try { msg = JSON.parse(evt.data); } catch { return; }
    handleEvent(msg);
  };
  stream.onerror = () => { /* browser auto-reconnects */ };
}

function handleEvent(msg) {
  switch (msg.type) {
    case "status":
      if (msg.target) document.getElementById("target-input").value = msg.target;
      break;
    case "stage_start":
      onStageStart(msg.stage);
      break;
    case "trace":
      logRow(msg.stage, msg.phase, msg.text);
      break;
    case "stage_output":
      onStageOutput(msg.stage, msg.output);
      break;
    case "stage_end":
      onStageEnd(msg.stage, msg.status, msg.error);
      break;
    case "pipeline_end":
      onPipelineEnd(msg.report);
      break;
    case "pipeline_error":
      onPipelineError(msg.error);
      break;
  }
}

function onStageStart(stage) {
  unlockTab(stage);
  setPill(stage, "running");
  setDot(stage, "running");
  setSteps(stage, "running");
  const feed = document.getElementById(`log-${stage}`);
  if (feed.querySelector(".log-empty")) feed.innerHTML = "";
  showContentView(stage, "logs");
  activateTab(stage);
}

function onStageOutput(stage, output) {
  renderStageOutput(stage, output);
  updateMetrics(stage, output);
}

function onStageEnd(stage, status, error) {
  setPill(stage, status === "done" ? "done" : "error");
  setDot(stage, status === "done" ? "done" : "error");
  setSteps(stage, status === "done" ? "done" : "error");
  if (error) logRow(stage, "ERR", error);
}

function onPipelineEnd(report) {
  running = false;
  document.getElementById("start-btn").disabled = false;
  unlockTab("report");
  setDot("report", "done");
  renderFinalReport(report);
  activateTab("report");
  if (stream) { stream.close(); stream = null; }
}

function onPipelineError(error) {
  running = false;
  document.getElementById("start-btn").disabled = false;
  STAGE_ORDER.forEach((stage) => {
    const pill = document.getElementById(`pill-${stage}`);
    if (pill && pill.textContent === "running") { setPill(stage, "error"); setDot(stage, "error"); setSteps(stage, "error"); }
  });
  const active = document.querySelector(".tab.active")?.dataset.tab || "discovery";
  if (STAGE_ORDER.includes(active)) logRow(active, "ERR", error);
}

/* ---------- Log rendering ---------- */
function logRow(stage, phase, text) {
  const feed = document.getElementById(`log-${stage}`);
  if (!feed) return;
  if (feed.querySelector(".log-empty")) feed.innerHTML = "";
  const p = (phase || "log").toLowerCase();
  const row = document.createElement("div");
  row.className = "log-row";
  if (p === "tool" || p === "report") row.classList.add("tool-row");
  if (p === "out") row.classList.add("out-row");
  row.innerHTML =
    `<span class="log-time">${nowTime()}</span>` +
    `<span class="log-phase ${p}">${escapeHtml(phase || "LOG")}</span>` +
    `<span class="log-msg">${escapeHtml(text || "")}</span>`;
  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 80;
  feed.appendChild(row);
  if (atBottom) feed.scrollTop = feed.scrollHeight;
}

/* ---------- Stage output rendering ---------- */
function renderStageOutput(stage, output) {
  const el = document.getElementById(`output-${stage}`);
  if (!output) { el.innerHTML = '<div class="empty-note">No structured output.</div>'; return; }
  if (stage === "discovery") el.innerHTML = openPortsSection(output) + summaryPara(output.summary) + rawJson(output);
  else if (stage === "vuln") el.innerHTML = vulnSection(output) + summaryPara(output.summary) + rawJson(output);
  else if (stage === "exploit") el.innerHTML = exploitSection(output) + summaryPara(output.summary) + rawJson(output);
}

function openPortsSection(output) {
  const ports = output.open_ports || [];
  let h = `<h2>Open Ports</h2><p class="muted">${ports.length} open port(s) on ${escapeHtml(output.target || "")}</p>`;
  if (!ports.length) return h + '<div class="empty-note">No open ports were found.</div>';
  h += `<table class="data-table"><thead><tr><th>Port</th><th>Proto</th><th>Service</th><th>Version</th><th>Notes</th></tr></thead><tbody>`;
  ports.forEach((p) => {
    h += `<tr><td class="mono">${escapeHtml(String(p.port))}</td><td class="mono">${escapeHtml(p.protocol || "")}</td>` +
      `<td>${escapeHtml(p.service || "")}</td><td class="mono">${escapeHtml(p.version || "")}</td><td>${escapeHtml(p.notes || "")}</td></tr>`;
  });
  return h + "</tbody></table>";
}

function vulnSection(output) {
  const vulns = output.vulnerabilities || [];
  let h = `<h2>Vulnerabilities</h2><p class="muted">${vulns.length} finding(s)</p>`;
  if (!vulns.length) return h + '<div class="empty-note">No vulnerabilities were confirmed.</div>';
  h += `<table class="data-table"><thead><tr><th>Port</th><th>Service</th><th>NSE Script</th><th>Severity</th><th>CVE</th><th>Evidence</th></tr></thead><tbody>`;
  vulns.forEach((v) => {
    h += `<tr><td class="mono">${escapeHtml(String(v.port))}</td><td>${escapeHtml(v.service || "")}</td>` +
      `<td class="mono">${escapeHtml(v.nse_script || "")}</td><td>${sevBadge(v.severity)}</td>` +
      `<td class="mono">${escapeHtml(v.cve || "")}</td><td class="evidence">${escapeHtml(v.evidence || "")}</td></tr>`;
  });
  return h + "</tbody></table>";
}

function exploitSection(output) {
  const attempts = output.exploit_attempts || [];
  let h = `<h2>Exploit Attempts</h2><p class="muted">${attempts.length} attempt(s), ${attempts.filter((a) => a.outcome === "confirmed").length} confirmed</p>`;
  if (!attempts.length) return h + '<div class="empty-note">No exploit attempts were made.</div>';
  h += `<table class="data-table"><thead><tr><th>Port</th><th>Service</th><th>Technique (NSE)</th><th>Outcome</th><th>CVE</th><th>Evidence</th></tr></thead><tbody>`;
  attempts.forEach((a) => {
    h += `<tr><td class="mono">${escapeHtml(String(a.port))}</td><td>${escapeHtml(a.service || "")}</td>` +
      `<td class="mono">${escapeHtml(a.technique || "")}</td><td>${outcomeBadge(a.outcome)}</td>` +
      `<td class="mono">${escapeHtml(a.cve || "")}</td><td class="evidence">${escapeHtml(a.evidence || "")}</td></tr>`;
  });
  return h + "</tbody></table>";
}

/* ---------- Final report ---------- */
function renderFinalReport(report) {
  const el = document.getElementById("final-report");
  const confirmed = (report.exploit_attempts || []).filter((a) => a.outcome === "confirmed").length;
  let h = `<h2>Assessment Report</h2><p class="muted">Target <b>${escapeHtml(report.target || "")}</b> &middot; ${escapeHtml(report.scanned_at || "")}</p>`;
  h += `<p class="muted">${escapeHtml(report.scan_type || "")}</p>`;
  h += `<div class="summary-cards">` +
    card((report.open_ports || []).length, "open ports") +
    card((report.vulnerabilities || []).length, "vulnerabilities") +
    card((report.exploit_attempts || []).length, "exploit attempts") +
    card(confirmed, "confirmed", confirmed > 0 ? "var(--red)" : null) +
    `</div>`;
  h += `<h3>Summary</h3><p>${escapeHtml(report.summary || "")}</p>`;
  h += `<h3>Open Ports</h3>` + openPortsSection(report);
  h += `<h3>Vulnerabilities</h3>` + vulnSection(report);
  h += `<h3>Exploitation</h3>` + exploitSection(report);
  h += `<h3>Findings</h3>` + findingsSection(report.findings || []);
  h += rawJson(report, "Raw report JSON");
  el.innerHTML = h;
}

function findingsSection(findings) {
  if (!findings.length) return '<div class="empty-note">No findings.</div>';
  let h = `<table class="data-table"><thead><tr><th>Finding</th><th>Severity</th><th>Evidence</th><th>Recommendation</th></tr></thead><tbody>`;
  findings.forEach((f) => {
    h += `<tr><td>${escapeHtml(f.title || "")}</td><td>${sevBadge(f.severity)}</td>` +
      `<td class="evidence">${escapeHtml(f.evidence || "")}</td><td>${escapeHtml(f.recommendation || "")}</td></tr>`;
  });
  return h + "</tbody></table>";
}

/* ---------- Small helpers ---------- */
function card(num, label, color) {
  const style = color ? ` style="color:${color}"` : "";
  return `<div class="summary-card"><div class="sc-num"${style}>${escapeHtml(String(num))}</div><div class="sc-label">${escapeHtml(label)}</div></div>`;
}
function summaryPara(text) { return text ? `<h3>Summary</h3><p>${escapeHtml(text)}</p>` : ""; }
function rawJson(obj, label) {
  return `<details class="raw-json"><summary>${escapeHtml(label || "Raw JSON")}</summary><pre>${escapeHtml(JSON.stringify(obj, null, 2))}</pre></details>`;
}
function sevBadge(sev) {
  const s = (sev || "").toLowerCase();
  const cls = s === "high" ? "sev-high" : s === "medium" ? "sev-medium" : s === "low" ? "sev-low" : "";
  return `<span class="badge ${cls}">${escapeHtml(sev || "n/a")}</span>`;
}
function outcomeBadge(outcome) {
  const o = (outcome || "").toLowerCase();
  const cls = o === "confirmed" ? "out-confirmed" : o === "inconclusive" ? "out-inconclusive" : o === "failed" ? "out-failed" : "";
  return `<span class="badge ${cls}">${escapeHtml(outcome || "n/a")}</span>`;
}
function updateMetrics(stage, output) {
  if (stage === "discovery") setMetric("metric-ports", (output.open_ports || []).length);
  else if (stage === "vuln") setMetric("metric-vulns", (output.vulnerabilities || []).length);
  else if (stage === "exploit") {
    const attempts = output.exploit_attempts || [];
    setMetric("metric-attempts", attempts.length);
    setMetric("metric-confirmed", attempts.filter((a) => a.outcome === "confirmed").length);
  }
}
function setMetric(id, val) { const el = document.getElementById(id); if (el) el.textContent = String(val); }
function setPill(stage, status) {
  const pill = document.getElementById(`pill-${stage}`);
  if (!pill) return;
  const labels = { idle: "idle", running: "running", done: "complete", error: "failed" };
  pill.textContent = labels[status] || status;
  pill.className = "pill " + (status === "idle" ? "" : status);
}
function setDot(stage, cls) { const d = document.getElementById(`dot-${stage}`); if (d) d.className = "tab-dot " + cls; }
function setSteps(stage, cls) {
  const panel = document.querySelector(`.panel[data-panel="${stage}"]`);
  if (!panel) return;
  panel.querySelectorAll(".stage-steps li").forEach((li) => { li.className = cls; });
}
function unlockTab(stage) {
  const tab = document.getElementById(`tab-${stage}`);
  if (tab) tab.disabled = false;
  const lock = document.getElementById(`lock-${stage}`);
  if (lock) lock.style.display = "none";
}
function lockTab(stage) {
  const tab = document.getElementById(`tab-${stage}`);
  if (tab) tab.disabled = true;
  const lock = document.getElementById(`lock-${stage}`);
  if (lock) lock.style.display = "";
}
function nowTime() {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}
function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
