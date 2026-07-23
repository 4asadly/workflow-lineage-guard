const elements = Object.fromEntries([
  "modeBadge", "loadDemo", "datasetUrn", "currentSchema", "proposedSchema", "renameMap",
  "lineagePath", "workflow", "allowWriteback", "runScan", "formError", "results",
  "riskScore", "gaugeValue",
  "verdict", "resultSummary", "agentNarrative", "findingCount", "patchCount",
  "lineageCount", "findings", "patches", "writeback", "writebackStatus", "downloadPatch"
].map((id) => [id, document.getElementById(id)]));

let latestResult = null;

function pretty(value) { return JSON.stringify(value, null, 2); }
function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function loadStatus() {
  const status = await fetch("/api/status").then((response) => response.json());
  elements.modeBadge.classList.toggle("live", status.mode === "live-agent");
  elements.modeBadge.lastChild.textContent = status.mode === "live-agent" ? " Live agent" : " Demo mode";
  elements.allowWriteback.disabled = !status.writeback_server_enabled;
  elements.allowWriteback.title = status.writeback_server_enabled ? "" : "Enable DATAHUB_ENABLE_WRITEBACK in live mode";
}

async function loadDemo() {
  const demo = await fetch("/api/demo").then((response) => response.json());
  elements.datasetUrn.value = demo.dataset_urn;
  elements.currentSchema.value = pretty(demo.current_schema);
  elements.proposedSchema.value = pretty(demo.proposed_schema);
  elements.renameMap.value = pretty(demo.rename_map || {});
  elements.lineagePath.value = pretty(demo.lineage_path || []);
  elements.workflow.value = pretty(demo.workflow);
  elements.allowWriteback.checked = false;
  elements.formError.textContent = "";
}

function parsedInput(element, label) {
  try { return JSON.parse(element.value); }
  catch (error) { throw new Error(`${label} is not valid JSON: ${error.message}`); }
}

function renderFindings(findings) {
  elements.findings.replaceChildren();
  if (!findings.length) {
    elements.findings.append(make("div", "empty", "No referenced breaking changes found."));
    return;
  }
  findings.forEach((finding) => {
    const card = make("div", "finding");
    const head = make("div", "finding-head");
    head.append(make("h4", "", finding.title), make("span", "severity", finding.severity.toUpperCase()));
    card.append(head, make("p", "", finding.explanation));
    finding.references.forEach((reference) => {
      card.append(make("div", "pointer", `${reference.node_name || "unnamed"} · ${reference.json_pointer}`));
    });
    elements.findings.append(card);
  });
}

function renderPatches(patches) {
  elements.patches.replaceChildren();
  if (!patches.length) {
    elements.patches.append(make("div", "empty", "No safe automatic patch available or required."));
    return;
  }
  patches.forEach((patch) => {
    const card = make("div", "patch");
    card.append(make("h4", "", patch.node_name || patch.json_pointer));
    const diff = make("pre");
    diff.append(make("span", "before", `− ${patch.before}\n`), make("span", "after", `+ ${patch.after}`));
    card.append(diff);
    elements.patches.append(card);
  });
}

function renderResult(result) {
  latestResult = result;
  elements.results.classList.remove("hidden");
  elements.riskScore.textContent = result.risk_score;
  elements.gaugeValue.style.strokeDashoffset = String(314 - (314 * result.risk_score / 100));
  elements.gaugeValue.style.stroke = result.risk_score >= 70 ? "var(--red)" : result.risk_score ? "var(--amber)" : "var(--mint)";
  elements.verdict.textContent = result.verdict.replaceAll("_", " ").toUpperCase();
  elements.resultSummary.textContent = result.summary;
  elements.agentNarrative.textContent = result.agent.warning || result.agent.narrative;
  elements.findingCount.textContent = result.findings.length;
  elements.patchCount.textContent = result.patches.length;
  elements.lineageCount.textContent = result.provenance.lineage_path.length;
  elements.writeback.textContent = result.writeback_markdown;
  elements.writebackStatus.textContent = result.agent.writeback_status.replaceAll("_", " ");
  renderFindings(result.findings);
  renderPatches(result.patches);
  elements.results.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runScan() {
  elements.formError.textContent = "";
  elements.runScan.disabled = true;
  elements.runScan.firstElementChild.textContent = "Tracing lineage…";
  try {
    const payload = {
      dataset_urn: elements.datasetUrn.value.trim(),
      current_schema: parsedInput(elements.currentSchema, "Current schema"),
      proposed_schema: parsedInput(elements.proposedSchema, "Proposed schema"),
      workflow: parsedInput(elements.workflow, "Workflow"),
      rename_map: parsedInput(elements.renameMap, "Approved rename map"),
      lineage_path: parsedInput(elements.lineagePath, "Lineage path"),
      allow_writeback: elements.allowWriteback.checked
    };
    const response = await fetch("/api/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Analysis failed");
    renderResult(result);
  } catch (error) {
    elements.formError.textContent = error.message;
  } finally {
    elements.runScan.disabled = false;
    elements.runScan.firstElementChild.textContent = "Run impact scan";
  }
}

function downloadPatch() {
  if (!latestResult) return;
  const blob = new Blob([pretty(latestResult.fixed_workflow)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "workflow-lineage-guard-fixed.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

elements.loadDemo.addEventListener("click", loadDemo);
elements.runScan.addEventListener("click", runScan);
elements.downloadPatch.addEventListener("click", downloadPatch);
Promise.all([loadDemo(), loadStatus()]).catch((error) => { elements.formError.textContent = error.message; });
