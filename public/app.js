import {
  analyzeLogs,
  chatAssistant,
  getIncidents,
  getLogs,
  getProjectStats,
  getProjects,
  getService,
  getServiceNames,
} from "./api.js?v=chat-upload-2";

const state = {
  projects: [],
  projectId: "ecommerce",
  serviceId: "payment-api",
  logs: [],
  incidents: [],
  logFilter: "ALL",
  selectedIncidentId: null,
  checklist: [],
  chatHistory: [],
  latestAnalysis: null,
  chatLog: null,
};

const elements = {
  projects: document.querySelector("#project-list"),
  projectSelect: document.querySelector("#project-select"),
  serviceSelect: document.querySelector("#service-select"),
  stats: {
    totalLogs: document.querySelector("#stat-total-logs"),
    errors: document.querySelector("#stat-errors"),
    warnings: document.querySelector("#stat-warnings"),
    incidents: document.querySelector("#stat-incidents"),
  },
  analysis: {
    severity: document.querySelector("#analysis-severity"),
    title: document.querySelector("#analysis-title"),
    service: document.querySelector("#analysis-service"),
    project: document.querySelector("#analysis-project"),
    summary: document.querySelector("#analysis-summary"),
    rootCause: document.querySelector("#analysis-root-cause"),
    evidence: document.querySelector("#analysis-evidence"),
    recommendations: document.querySelector("#analysis-recommendations"),
    confidence: document.querySelector("#analysis-confidence"),
    confidenceBar: document.querySelector("#confidence-bar"),
  },
  assistantService: document.querySelector("#assistant-service"),
  logRows: document.querySelector("#log-rows"),
  logCount: document.querySelector("#log-count"),
  incidents: document.querySelector("#incident-list"),
  activity: document.querySelector("#activity-list"),
  toast: document.querySelector("#toast"),
  checklist: {
    items: document.querySelector("#checklist-items"),
    progress: document.querySelector("#checklist-progress"),
    progressBar: document.querySelector("#checklist-progress-bar"),
    progressTrack: document.querySelector(".checklist-progress-track"),
    complete: document.querySelector("#checklist-complete"),
  },
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function currentProject() {
  return state.projects.find((project) => project.id === state.projectId);
}

function renderProjects() {
  elements.projects.innerHTML = state.projects
    .map(
      (project) => `
        <button class="project-link ${project.id === state.projectId ? "selected" : ""}" type="button" data-project-id="${escapeHtml(project.id)}" aria-current="${project.id === state.projectId ? "true" : "false"}">
          <span class="project-initials project-${escapeHtml(project.color)}">${escapeHtml(project.initials)}</span>
          <span class="project-name">${escapeHtml(project.name)}</span>
          ${project.id === state.projectId ? '<span class="project-arrow">↗</span>' : ""}
        </button>
      `,
    )
    .join("");
}

function renderServiceOptions() {
  const services = getServiceNames(state.projectId);
  elements.serviceSelect.innerHTML = services
    .map(
      (service) =>
        `<option value="${escapeHtml(service.id)}" ${service.id === state.serviceId ? "selected" : ""}>${escapeHtml(service.name)}</option>`,
    )
    .join("");
}

function renderProjectOptions() {
  elements.projectSelect.innerHTML = state.projects
    .map(
      (project) =>
        `<option value="${escapeHtml(project.id)}" ${project.id === state.projectId ? "selected" : ""}>${escapeHtml(project.name)}</option>`,
    )
    .join("");
}

function renderStats() {
  const stats = getProjectStats(state.projectId);
  elements.stats.totalLogs.textContent = stats.totalLogs.toLocaleString("en-US");
  elements.stats.errors.textContent = stats.errors.toLocaleString("en-US");
  elements.stats.warnings.textContent = stats.warnings.toLocaleString("en-US");
  elements.stats.incidents.textContent = stats.incidents.toLocaleString("en-US");
  document.querySelector("#nav-incident-count").textContent = stats.incidents;
}

function renderAnalysis(analysis, incident = null) {
  const service = getService(state.projectId, state.serviceId);
  const severity = incident?.severity ?? analysis.severity ?? "LOW";
  elements.analysis.severity.className = `severity-badge severity-${severity.toLowerCase()}`;
  elements.analysis.severity.innerHTML = `<span></span> ${escapeHtml(severity)}`;
  elements.analysis.title.textContent = incident?.analysisTitle ?? analysis.incident_type ?? analysis.title;
  elements.analysis.service.textContent = service.name;
  elements.analysis.project.textContent = currentProject().name;
  elements.analysis.summary.textContent = analysis.summary;
  elements.analysis.rootCause.textContent = analysis.probable_root_cause ?? analysis.rootCause;
  const evidence = analysis.observed_evidence ?? analysis.evidence ?? [];
  elements.analysis.evidence.innerHTML = evidence.length
    ? evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>No concrete log evidence was returned.</li>";
  const recommendations = analysis.recommended_actions ?? analysis.recommendations ?? [];
  elements.analysis.recommendations.innerHTML = recommendations
    .map((recommendation, index) => `<li><span>${index + 1}</span>${escapeHtml(recommendation)}</li>`)
    .join("");
  const confidence = analysis.confidence <= 1
    ? Math.round(analysis.confidence * 100)
    : analysis.confidence;
  elements.analysis.confidence.textContent = `${confidence}%`;
  elements.analysis.confidenceBar.style.width = `${confidence}%`;
  document.querySelector(".analysis-detected").innerHTML =
    `<span class="detected-dot"></span>${escapeHtml(analysis.status === "INSUFFICIENT_CONTEXT" ? "Insufficient context" : incident?.timeAgo ? `Detected ${incident.timeAgo}` : analysis.detected ? `Detected ${analysis.detected}` : "Live analysis")}`;
  elements.assistantService.textContent = service.name;
  state.checklist = (analysis.checklist ?? []).map((item) => ({ ...item }));
  renderChecklist();
}

function renderChecklist() {
  const completed = state.checklist.filter((item) => item.status === "completed").length;
  const total = state.checklist.length;
  elements.checklist.progress.textContent = `${completed} / ${total} completed`;
  elements.checklist.progressTrack.setAttribute("aria-valuemax", String(total));
  elements.checklist.progressTrack.setAttribute("aria-valuenow", String(completed));
  elements.checklist.progressBar.style.width = total ? `${(completed / total) * 100}%` : "0%";
  elements.checklist.complete.hidden = total === 0 || completed !== total;
  elements.checklist.items.innerHTML = state.checklist
    .map((item) => `
      <li class="checklist-item checklist-${escapeHtml(item.status)}">
        <label class="checklist-item-main">
          <input type="checkbox" data-checklist-id="${escapeHtml(item.id)}" ${item.status === "completed" ? "checked" : ""} />
          <span class="checklist-item-copy">
            <strong>${escapeHtml(item.title)}</strong>
            <span>${escapeHtml(item.description)}</span>
            <small><b>WHY</b> ${escapeHtml(item.reason)}</small>
          </span>
        </label>
        ${item.status === "skipped"
          ? `<button type="button" class="checklist-item-action" data-reset-checklist-id="${escapeHtml(item.id)}">Undo skip</button>`
          : `<button type="button" class="checklist-item-action" data-skip-checklist-id="${escapeHtml(item.id)}">Skip</button>`}
      </li>
    `)
    .join("");
}

function renderChatMessages(pendingText = null, pendingQuestion = null) {
  const container = document.querySelector("#chat-messages");
  container.replaceChildren();
  if (!state.chatHistory.length && pendingText === null && pendingQuestion === null) {
    const empty = document.createElement("p");
    empty.className = "chat-empty";
    empty.textContent = "Ask a troubleshooting question after adding a log.";
    container.append(empty);
    return;
  }
  for (const message of state.chatHistory) {
    const bubble = document.createElement("div");
    bubble.className = `chat-message chat-message-${message.role}`;
    bubble.textContent = message.content;
    container.append(bubble);
  }
  if (pendingQuestion !== null) {
    const bubble = document.createElement("div");
    bubble.className = "chat-message chat-message-user";
    bubble.textContent = pendingQuestion;
    container.append(bubble);
  }
  if (pendingText !== null) {
    const pending = document.createElement("div");
    pending.className = "chat-message chat-message-assistant chat-message-pending";
    pending.textContent = pendingText;
    container.append(pending);
  }
  container.scrollTop = container.scrollHeight;
}

function resetChat(clearAnalysis = true) {
  state.chatHistory = [];
  if (clearAnalysis) {
    state.latestAnalysis = null;
    state.chatLog = null;
  }
  renderChatMessages();
}

function renderLogs() {
  const visibleLogs =
    state.logFilter === "ALL"
      ? state.logs
      : state.logs.filter((log) => log.level === state.logFilter);
  elements.logRows.innerHTML = visibleLogs
    .slice(0, 4)
    .map(
      (log) => `
        <tr>
          <td class="log-time">${escapeHtml(log.time)}</td>
          <td><span class="log-level level-${escapeHtml(log.level.toLowerCase())}"><span></span>${escapeHtml(log.level)}</span></td>
          <td class="log-service">${escapeHtml(log.service)}</td>
          <td class="log-message">${escapeHtml(log.message)}</td>
        </tr>
      `,
    )
    .join("");
  elements.logCount.textContent = `Showing ${Math.min(visibleLogs.length, 4)} of ${getProjectStats(state.projectId).totalLogs} events`;
}

function renderIncidents() {
  const serviceIncidents = state.incidents.filter(
    (incident) => incident.serviceId === state.serviceId,
  );
  elements.incidents.innerHTML = serviceIncidents.length
    ? serviceIncidents
    .map(
      (incident) => `
        <article class="incident-card ${state.selectedIncidentId === incident.id ? "incident-selected" : ""}">
          <div class="incident-card-top">
            <span class="incident-severity incident-${escapeHtml(incident.severity.toLowerCase())}"><span></span>${escapeHtml(incident.severity)}</span>
            <span class="incident-age">${escapeHtml(incident.timeAgo)}</span>
          </div>
          <h3>${escapeHtml(incident.title)}</h3>
          <div class="incident-card-meta"><span class="incident-service-icon">⌘</span>${escapeHtml(getService(state.projectId, incident.serviceId).name)}<span class="meta-divider">·</span><span class="incident-state">${escapeHtml(incident.status)}</span></div>
          <button class="text-action incident-view-button" type="button" data-incident-id="${escapeHtml(incident.id)}">View analysis <span>→</span></button>
        </article>
      `,
    )
    .join("")
    : '<div class="empty-incidents"><span>✓</span><strong>No active incidents</strong><p>This service is looking healthy right now.</p></div>';
}

function addActivity(message) {
  const item = document.createElement("div");
  item.className = "activity-item activity-new";
  item.innerHTML = `<span class="activity-check">✓</span><p></p><time>now</time>`;
  item.querySelector("p").textContent = message;
  elements.activity.prepend(item);
  while (elements.activity.children.length > 3) {
    elements.activity.lastElementChild.remove();
  }
}

function announce(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("toast-visible");
  window.clearTimeout(announce.timeout);
  announce.timeout = window.setTimeout(() => {
    elements.toast.classList.remove("toast-visible");
  }, 2600);
}

async function updateDashboard({ resetIncident = true } = {}) {
  const project = currentProject();
  if (!project) {
    throw new Error(`Project "${state.projectId}" is unavailable.`);
  }
  if (resetIncident) {
    state.selectedIncidentId = null;
  }
  renderProjects();
  renderProjectOptions();
  renderServiceOptions();
  renderStats();
  const service = getService(state.projectId, state.serviceId);
  state.logs = (await getLogs(state.projectId, state.serviceId)).map((log) => ({
    ...log,
    serviceId: state.serviceId,
  }));
  state.incidents = await getIncidents(state.projectId);
  renderAnalysis(service.analysis);
  renderLogs();
  renderIncidents();
}

function navToSection(section) {
  const target =
    section === "overview"
      ? document.querySelector("#overview")
      : document.querySelector(`#${section}`);
  target?.scrollIntoView({ behavior: "smooth", block: section === "overview" ? "start" : "center" });
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.section === section);
  });
}

async function selectProject(projectId) {
  if (projectId === state.projectId) {
    return;
  }
  try {
    state.projectId = projectId;
    state.serviceId = getServiceNames(state.projectId)[0].id;
    state.logFilter = "ALL";
    resetChat();
    await updateDashboard();
  } catch (error) {
    announce(error.message);
  }
}

document.querySelector("#project-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-project-id]");
  if (button) {
    await selectProject(button.dataset.projectId);
  }
});

elements.projectSelect.addEventListener("change", (event) => {
  selectProject(event.target.value);
});

elements.serviceSelect.addEventListener("change", async (event) => {
  try {
    state.serviceId = event.target.value;
    state.logFilter = "ALL";
    resetChat();
    await updateDashboard();
  } catch (error) {
    announce(error.message);
  }
});

document.querySelector(".primary-nav").addEventListener("click", (event) => {
  const link = event.target.closest("[data-section]");
  if (link) {
    event.preventDefault();
    navToSection(link.dataset.section);
  }
});

elements.incidents.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-incident-id]");
  if (!button) {
    return;
  }
  const incident = state.incidents.find((item) => item.id === button.dataset.incidentId);
  if (!incident) {
    return;
  }
  try {
    state.serviceId = incident.serviceId;
    resetChat();
    state.selectedIncidentId = incident.id;
    renderServiceOptions();
    const service = getService(state.projectId, state.serviceId);
    state.logs = (await getLogs(state.projectId, state.serviceId)).map((log) => ({
      ...log,
      serviceId: state.serviceId,
    }));
    state.incidents = await getIncidents(state.projectId);
    renderAnalysis(service.analysis, incident);
    renderLogs();
    renderIncidents();
    document.querySelector("#analysis-panel").scrollIntoView({ behavior: "smooth", block: "center" });
    announce(`Showing analysis for ${incident.title}`);
  } catch (error) {
    announce(error.message);
  }
});

const demoLogs = {
  kubernetes: {
    projectId: "ecommerce",
    serviceId: "payment-api",
    log: "2026-10-08T12:31:42Z ERROR payment-api-7f8d CrashLoopBackOff after the readiness probe failed repeatedly",
  },
  container: {
    projectId: "ecommerce",
    serviceId: "order-service",
    log: "[ERROR] Container exited during startup: configured entrypoint /app/start.sh was not found",
  },
  database: {
    projectId: "ecommerce",
    serviceId: "payment-api",
    log: "Payment API startup failed: connection refused by database endpoint on port 5432",
  },
  environment: {
    projectId: "hr-portal",
    serviceId: "employee-api",
    log: "Required EMPLOYEE_DIRECTORY_URL setting is absent from the pod environment",
  },
  dependency: {
    projectId: "banking",
    serviceId: "transfer-api",
    log: "Build resolver rejected release: package requires cryptolib >=4.0 but the lockfile pins cryptolib 3.2",
  },
};

const logInput = document.querySelector("#assistant-log");
const fileInput = document.querySelector("#log-file-input");
const fileDrop = document.querySelector("#log-file-drop");
const fileName = document.querySelector("#log-file-name");

async function loadLogFile(file) {
  if (file.size > 1024 * 1024) {
    announce("Choose a text log file no larger than 1 MB.");
    return;
  }
  const extension = file.name.split(".").pop().toLowerCase();
  if (!["log", "txt", "out", "json", "yaml", "yml", "csv"].includes(extension)) {
    announce("Unsupported file type. Choose a .log, .txt, .out, .json, .yaml, .yml, or .csv file.");
    return;
  }
  try {
    const content = await file.text();
    if (!content.trim() || content.includes("\0")) {
      announce("The selected file is empty or is not a readable text log.");
      return;
    }
    if (content.length > 20000) {
      announce("This log exceeds the 20,000 character analysis limit. Select a smaller file.");
      return;
    }
    logInput.value = content;
    fileName.textContent = `Loaded ${file.name}`;
    document.querySelector("#demo-log-select").value = "";
    resetChat();
    announce(`Loaded ${file.name}. Choose Analyze Logs to run the analysis.`);
  } catch (error) {
    announce(`Could not read the selected file: ${error.message}`);
  }
}

fileInput.addEventListener("change", async () => {
  const [file] = fileInput.files;
  if (file) await loadLogFile(file);
  fileInput.value = "";
});

for (const eventName of ["dragenter", "dragover"]) {
  fileDrop.addEventListener(eventName, (event) => {
    event.preventDefault();
    fileDrop.classList.add("is-dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  fileDrop.addEventListener(eventName, (event) => {
    event.preventDefault();
    fileDrop.classList.remove("is-dragging");
  });
}
fileDrop.addEventListener("drop", async (event) => {
  const [file] = event.dataTransfer.files;
  if (file) await loadLogFile(file);
});
logInput.addEventListener("input", () => {
  if (state.chatLog && logInput.value.trim() !== state.chatLog) {
    resetChat();
  }
});

document.querySelector("#demo-log-select").addEventListener("change", async (event) => {
  const sample = demoLogs[event.target.value];
  if (!sample) {
    return;
  }
  try {
    if (state.projectId !== sample.projectId) {
      state.projectId = sample.projectId;
      state.serviceId = sample.serviceId;
      await updateDashboard();
    } else if (state.serviceId !== sample.serviceId) {
      state.serviceId = sample.serviceId;
      await updateDashboard();
    }
    document.querySelector("#assistant-log").value = sample.log;
    fileName.textContent = "";
    resetChat();
  } catch (error) {
    announce(error.message);
  }
});

document.querySelector("#assistant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.querySelector("#assistant-log");
  const log = input.value.trim();
  if (!log) {
    announce("Paste a deployment log or choose a demo log first.");
    return;
  }
  const button = event.currentTarget.querySelector('button[type="submit"]');
  const buttonText = button.querySelector("span");
  resetChat();
  button.disabled = true;
  buttonText.textContent = "Analyzing…";
  document.querySelector(".assistant-status-line span:last-child").textContent = "Running local AI analysis";
  try {
    const analysis = await analyzeLogs({
      project: currentProject().name === "Banking" ? "Banking Platform" : currentProject().name,
      service: getService(state.projectId, state.serviceId).name,
      log,
    });
    renderAnalysis(analysis);
    state.latestAnalysis = analysis;
    state.chatLog = log;
    addActivity(`Analyzed ${analysis.incident_type || "deployment log"} for ${getService(state.projectId, state.serviceId).name}.`);
    announce("Live AI analysis complete.");
  } catch (error) {
    announce(error.message);
    addActivity(`Analysis unavailable: ${error.message}`);
  } finally {
    button.disabled = false;
    buttonText.textContent = "Analyze Logs";
    document.querySelector(".assistant-status-line span:last-child").textContent = "Analyzing incoming service logs";
  }
});

document.querySelector("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const questionInput = document.querySelector("#chat-question");
  const question = questionInput.value.trim();
  const log = logInput.value.trim();
  if (!log) {
    announce("Add or analyze a log before asking a troubleshooting question.");
    return;
  }
  if (!question) return;

  const button = event.currentTarget.querySelector("button[type='submit']");
  button.disabled = true;
  renderChatMessages("Thinking through the log and related examples…", question);
  try {
    const result = await chatAssistant({
      project: currentProject().name === "Banking" ? "Banking Platform" : currentProject().name,
      service: getService(state.projectId, state.serviceId).name,
      log,
      question,
      history: state.chatHistory.slice(-12),
      analysis: state.latestAnalysis,
    });
    state.chatHistory.push(
      { role: "user", content: question },
      { role: "assistant", content: result.answer },
    );
    state.chatHistory = state.chatHistory.slice(-12);
    state.chatLog = log;
    questionInput.value = "";
    renderChatMessages();
    addActivity("Answered a follow-up question using the current log and retrieved examples.");
  } catch (error) {
    renderChatMessages();
    const failure = document.createElement("div");
    failure.className = "chat-message chat-message-assistant";
    failure.setAttribute("role", "alert");
    failure.textContent = `Unable to answer: ${error.message}`;
    document.querySelector("#chat-messages").append(failure);
    announce(error.message);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#chat-question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.querySelector("#chat-form").requestSubmit();
  }
});

document.querySelector("#chat-clear").addEventListener("click", () => {
  resetChat(false);
  announce("Started a new chat for the current log.");
});

elements.checklist.items.addEventListener("change", (event) => {
  const id = event.target.dataset.checklistId;
  if (!id) return;
  const item = state.checklist.find((entry) => entry.id === id);
  if (item) {
    item.status = event.target.checked ? "completed" : "pending";
    renderChecklist();
  }
});

elements.checklist.items.addEventListener("click", (event) => {
  const skipId = event.target.dataset.skipChecklistId;
  const resetId = event.target.dataset.resetChecklistId;
  const id = skipId || resetId;
  if (!id) return;
  const item = state.checklist.find((entry) => entry.id === id);
  if (item) {
    item.status = skipId ? "skipped" : "pending";
    renderChecklist();
  }
});

document.querySelector("#log-filter-button").addEventListener("click", () => {
  const filters = ["ALL", "ERROR", "WARN", "INFO"];
  state.logFilter = filters[(filters.indexOf(state.logFilter) + 1) % filters.length];
  renderLogs();
  announce(state.logFilter === "ALL" ? "Showing all log levels." : `Showing ${state.logFilter} logs.`);
});

document.querySelector("#notifications-button").addEventListener("click", () => {
  announce(`${getProjectStats(state.projectId).incidents} active incidents need attention.`);
});

document.querySelector("#analysis-details-button").addEventListener("click", () => {
  announce("You’re viewing the latest AI-generated incident analysis.");
});

document.querySelector("#view-all-logs").addEventListener("click", () => {
  announce("Showing the latest events for the selected service.");
});

document.querySelector("#view-all-incidents").addEventListener("click", () => {
  announce(`${state.incidents.length} incidents in ${currentProject().name}.`);
});

document.querySelector(".add-project-button").addEventListener("click", () => {
  announce("Choose a project from your workspace list.");
});

document.querySelector(".more-button").addEventListener("click", () => {
  announce("Profile settings will be available soon.");
});

document.querySelector(".assistant-menu").addEventListener("click", () => {
  announce("Assistant is monitoring the selected service.");
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", (event) => {
    if (link.dataset.section === "projects") {
      event.preventDefault();
      document.querySelectorAll(".nav-link").forEach((navLink) => navLink.classList.remove("active"));
      link.classList.add("active");
      document.querySelector("#projects").scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
});

try {
  state.projects = await getProjects();
  await updateDashboard();
} catch (error) {
  document.querySelector(".dashboard-content").innerHTML =
    `<section class="load-error" role="alert"><h1>Dashboard data unavailable</h1><p>${escapeHtml(error.message)}</p></section>`;
}
