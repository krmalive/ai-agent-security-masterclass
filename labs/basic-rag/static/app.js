const $ = (selector) => document.querySelector(selector);
const runButton = $("#run-button");
const objective = $("#objective");
const trace = $("#trace");
const reportSection = $("#report");
const reportContent = $("#report-content");
let source = null;
let currentRun = null;
let currentReport = null;

const eventTypes = [
  "run_started", "agent_started", "task_completed", "code_inventory", "code_search", "code_file_opened",
  "rag_indexing", "rag_ready", "rag_query_started", "rag_results_received", "citation_verified",
  "citation_rejected", "coverage_updated", "report_ready", "run_failed"
];

function esc(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}

async function request(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

async function loadStatus() {
  try {
    const status = await request("/api/status");
    const element = $("#system-status");
    element.classList.toggle("ready", status.ready);
    element.classList.toggle("error", !status.ready);
    element.querySelector("span").textContent = status.ready
      ? `${status.wstg_scenarios} WSTG scenarios ready`
      : status.errors.join(" · ");
    runButton.disabled = !status.ready;
  } catch (error) {
    setFailure(error.message);
  }
}

function resetRunView() {
  trace.innerHTML = '<div class="trace-empty" id="trace-empty"><span>◌</span><p>Connecting to the planning crew…</p></div>';
  reportSection.hidden = true;
  currentReport = null;
  document.querySelectorAll(".agent-card").forEach((card) => {
    card.classList.remove("active", "complete", "failed");
    card.querySelector(".agent-state").textContent = "Waiting";
  });
}

async function startRun() {
  resetRunView();
  runButton.disabled = true;
  runButton.classList.add("loading");
  runButton.querySelector("span").textContent = "Crew is working";
  try {
    currentRun = await request("/api/runs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({objective: objective.value.trim()})
    });
    $("#run-id").textContent = `RUN ${currentRun.id.slice(0, 8).toUpperCase()}`;
    connectEvents(currentRun.id);
  } catch (error) {
    setFailure(error.message);
    finishButton();
  }
}

function connectEvents(runId) {
  if (source) source.close();
  source = new EventSource(`/api/runs/${runId}/events`);
  eventTypes.forEach((type) => source.addEventListener(type, (message) => handleEvent(JSON.parse(message.data))));
  source.onerror = () => {
    if (source?.readyState === EventSource.CLOSED) return;
  };
}

function handleEvent(event) {
  appendTrace(event);
  if (event.type === "agent_started") setAgent(event.agent, "active");
  if (event.type === "task_completed") setAgent(event.agent, "complete");
  if (event.type === "report_ready") {
    source?.close();
    fetchReport(event.run_id);
  }
  if (event.type === "run_failed") {
    source?.close();
    document.querySelector(".agent-card.active")?.classList.add("failed");
    finishButton();
  }
}

function setAgent(name, state) {
  const card = [...document.querySelectorAll(".agent-card")].find((item) => item.dataset.agent === name);
  if (!card) return;
  card.classList.remove("active", "complete");
  card.classList.add(state);
  card.querySelector(".agent-state").textContent = state === "complete" ? "Complete" : "Working";
}

function appendTrace(event) {
  $("#trace-empty")?.remove();
  const node = $("#trace-template").content.cloneNode(true);
  const article = node.querySelector("article");
  article.dataset.type = event.type;
  node.querySelector(".trace-meta b").textContent = event.agent || labelFor(event.type);
  node.querySelector("time").textContent = new Date(event.created_at).toLocaleTimeString([], {hour12: false});
  node.querySelector(".trace-body > p").textContent = event.message;
  const details = node.querySelector("details");
  if (event.data && Object.keys(event.data).length) {
    node.querySelector("pre").textContent = JSON.stringify(event.data, null, 2);
  } else {
    details.remove();
  }
  trace.appendChild(node);
  trace.scrollTop = trace.scrollHeight;
}

function labelFor(type) {
  return type.split("_").map((word) => word[0].toUpperCase() + word.slice(1)).join(" ");
}

async function fetchReport(runId) {
  try {
    currentReport = await request(`/api/runs/${runId}/report`);
    renderReport(currentReport);
    reportSection.hidden = false;
    reportSection.scrollIntoView({behavior: "smooth", block: "start"});
  } catch (error) {
    setFailure(error.message);
  } finally {
    finishButton();
  }
}

function renderReport(report) {
  const dayNumbers = [...new Set(report.tests.map((test) => test.day))].sort((a, b) => a - b);
  const days = dayNumbers.map((day) => {
    const tests = report.tests.filter((test) => test.day === day);
    const hours = tests.reduce((sum, test) => sum + test.estimated_hours, 0);
    return `<section class="day"><div class="day-title"><div><span>DAY ${day}</span><h3>Scheduled testing</h3></div><b>${hours}h</b></div>
      <div class="day-tests">${tests.map(renderTest).join("")}</div></section>`;
  }).join("");
  const coverage = report.coverage.map((item) => `<li class="${esc(item.status)}"><span></span><b>${esc(item.category)}</b><small>${esc(item.status.replace("_", " "))}</small></li>`).join("");
  const constraints = report.scope_and_constraints.map((item) => `<li>${esc(item)}</li>`).join("") || "<li>No additional constraints recorded.</li>";
  const assumptions = report.assumptions.map((item) => `<li>${esc(item)}</li>`).join("") || "<li>None recorded.</li>";
  reportContent.innerHTML = `
    <div class="report-summary"><div><p class="kicker">AGENT OUTPUT</p><h3>${esc(report.title)}</h3><p>${esc(report.executive_summary)}</p></div><div class="metric"><strong>${report.tests.length}</strong><span>selected tests</span></div><div class="metric"><strong>${report.total_hours}</strong><span>planned hours</span></div></div>
    <div class="engagement-details"><div class="requested-objective"><h3>Requested objective</h3><p>${esc(report.requested_objective || "Not recorded")}</p></div><div><h3>Applied scope & constraints</h3><ul>${constraints}</ul></div><div><h3>Assumptions</h3><ul>${assumptions}</ul></div></div>
    <div class="coverage"><h3>Coverage check</h3><ul>${coverage}</ul></div>
    <div class="days">${days}</div>
    <div class="report-tail"><div><h3>Residual gaps</h3><ul>${report.residual_gaps.map((gap) => `<li>${esc(gap)}</li>`).join("")}</ul></div><div><h3>Rejected candidates</h3><ul>${report.rejected_candidates.map((item) => `<li><b>${esc(item.scenario_id)}</b> — ${esc(item.reason)}</li>`).join("") || "<li>None recorded</li>"}</ul></div></div>`;
}

function renderTest(test) {
  const citation = test.citation;
  const citationBlock = citation
    ? `<details class="citation">
        <summary>
          <span class="citation-status">Verified source</span>
          <span class="citation-summary-text"><code>${esc(citation.scenario_id)}</code><b>${esc(citation.title)}</b></span>
          <span class="citation-pages">pp. ${esc(citation.pages)}</span>
        </summary>
        <div class="citation-content">
          <p class="citation-location">OWASP Web Security Testing Guide v4.2 · PDF pages ${esc(citation.pages)}</p>
          <blockquote>${esc(citation.excerpt)}</blockquote>
        </div>
      </details>`
    : `<aside class="citation citation-missing"><b>Source not resolved</b><p>No matching WSTG PDF citation was found for this agent-selected candidate.</p></aside>`;
  return `<article class="test-card"><div class="test-top"><span class="priority ${esc(test.priority)}">${esc(test.priority)}</span><code>${esc(test.scenario_id)}</code><span>${test.estimated_hours}h</span></div><h4>${esc(test.title)}</h4><p>${esc(test.rationale)}</p><details><summary>Procedure and evidence</summary><ol>${test.production_safe_procedure.map((step) => `<li>${esc(step)}</li>`).join("")}</ol><h5>Expected evidence</h5><ul>${test.expected_evidence.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></details>${citationBlock}</article>`;
}

function setFailure(message) {
  appendTrace({type: "run_failed", message, agent: "System", data: {}, created_at: new Date().toISOString()});
}

function finishButton() {
  runButton.disabled = false;
  runButton.classList.remove("loading");
  runButton.querySelector("span").textContent = "Generate another plan";
}

$("#clear-trace").addEventListener("click", () => { trace.innerHTML = '<div class="trace-empty" id="trace-empty"><span>▱</span><p>Trace view cleared. New events will appear here.</p></div>'; });
$("#download-report").addEventListener("click", () => {
  if (!currentReport) return;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([JSON.stringify(currentReport, null, 2)], {type: "application/json"}));
  link.download = "shopfast-wstg-testing-plan.json";
  link.click();
  URL.revokeObjectURL(link.href);
});
runButton.addEventListener("click", startRun);
loadStatus();
