const state = {
  mode: "agent",
  busy: false,
  testCases: [],
};

const elements = {
  form: document.querySelector("#chatForm"),
  input: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  charCount: document.querySelector("#charCount"),
  messages: document.querySelector("#messages"),
  quickPrompts: document.querySelector("#quickPrompts"),
  modeButtons: [...document.querySelectorAll(".mode-button")],
  modeNote: document.querySelector("#modeNote"),
  traceContent: document.querySelector("#traceContent"),
  traceStatus: document.querySelector("#traceStatus"),
  traceSummary: document.querySelector("#traceSummary"),
  iterationCount: document.querySelector("#iterationCount"),
  toolCallCount: document.querySelector("#toolCallCount"),
  resultStatus: document.querySelector("#resultStatus"),
  evaluateButton: document.querySelector("#evaluateButton"),
  evaluationMetrics: document.querySelector("#evaluationMetrics"),
  evaluationResults: document.querySelector("#evaluationResults"),
  toolGrid: document.querySelector("#toolGrid"),
  toast: document.querySelector("#toast"),
};

const toolDescriptions = {
  lookup_order: "Tra cứu trạng thái, sản phẩm và thông tin cơ bản của đơn.",
  track_delivery: "Theo dõi đơn vị vận chuyển, mã vận đơn và ngày giao.",
  check_return_eligibility: "Đối chiếu thời hạn và điều kiện đổi trả của sản phẩm.",
  get_return_policy: "Đọc chính sách đổi trả theo từng danh mục sản phẩm.",
  create_return_request: "Tạo mã RMA sau khi đủ điều kiện và được xác nhận.",
};

function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => elements.toast.classList.remove("show"), 2800);
}

function setTraceStatus(type, label) {
  elements.traceStatus.className = `trace-status ${type}`;
  elements.traceStatus.innerHTML = "";
  elements.traceStatus.append(createElement("span"), document.createTextNode(` ${label}`));
}

function addMessage(role, text, stats = null, loading = false) {
  const message = createElement("div", `message ${role === "user" ? "user-message" : "assistant-message"}`);
  if (role !== "user") {
    message.append(createElement("div", "avatar ai-avatar", "✦"));
  }

  const body = createElement("div", "message-body");
  const meta = createElement("div", "message-meta");
  meta.append(
    createElement("strong", "", role === "user" ? "Bạn" : "OrderCare"),
    createElement("span", "", "vừa xong"),
  );
  body.append(meta);

  if (loading) {
    const dots = createElement("div", "loading-dots");
    dots.append(createElement("span"), createElement("span"), createElement("span"));
    body.append(dots);
    message.dataset.loading = "true";
  } else {
    body.append(createElement("p", "", text));
    if (stats) {
      const statsRow = createElement("div", "message-stats");
      statsRow.append(
        createElement("span", "", `${stats.iterations} iteration${stats.iterations === 1 ? "" : "s"}`),
        createElement("span", "", `${stats.tool_calls} tool call${stats.tool_calls === 1 ? "" : "s"}`),
        createElement("span", "", stats.mode === "agent" ? "ReAct Agent" : "Baseline"),
      );
      body.append(statsRow);
    }
  }

  message.append(body);
  elements.messages.append(message);
  elements.messages.scrollTo({ top: elements.messages.scrollHeight, behavior: "smooth" });
  return message;
}

function setMode(mode) {
  state.mode = mode;
  elements.modeButtons.forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  if (mode === "agent") {
    elements.modeNote.innerHTML = '<span class="mode-note-icon" aria-hidden="true">⌁</span><span><strong>Agent mode</strong> — có thể suy luận và gọi tool để lấy bằng chứng.</span>';
  } else {
    elements.modeNote.innerHTML = '<span class="mode-note-icon" aria-hidden="true">◌</span><span><strong>Baseline mode</strong> — một LLM call, không có quyền gọi tool.</span>';
    renderTrace([], { iterations: 1, tool_calls: 0, status: "baseline", guardrail_triggered: false });
  }
}

function traceKind(event) {
  if (event.type === "final") return ["Final", "final"];
  if (["error", "provider_error", "repeated_action"].includes(event.type)) return ["Guardrail", "error"];
  return ["Action", ""];
}

function addTraceBlock(card, label, value, asCode = false) {
  if (!value) return;
  const block = createElement("div", "trace-block");
  block.append(createElement("label", "", label));
  block.append(createElement(asCode ? "code" : "p", "", value));
  card.append(block);
}

function renderTrace(trace = [], result = {}) {
  elements.traceContent.innerHTML = "";
  elements.traceSummary.hidden = false;
  elements.iterationCount.textContent = result.iterations ?? 0;
  elements.toolCallCount.textContent = result.tool_calls ?? 0;
  elements.resultStatus.textContent = result.guardrail_triggered ? "Safe" : result.status === "baseline" ? "N/A" : "Done";

  if (!trace.length) {
    const empty = createElement("div", "trace-empty");
    const orbit = createElement("div", "orbit");
    orbit.setAttribute("aria-hidden", "true");
    orbit.append(createElement("span", "", state.mode === "baseline" ? "◌" : "✦"));
    empty.append(
      orbit,
      createElement("h3", "", state.mode === "baseline" ? "Baseline không có trace" : "Không có bước tool nào"),
      createElement("p", "", state.mode === "baseline"
        ? "Đây là điểm khác biệt cốt lõi: Baseline trả lời bằng một LLM call và không có Action/Observation."
        : "Câu hỏi được trả lời trực tiếp mà không cần gọi công cụ."),
    );
    elements.traceContent.append(empty);
    setTraceStatus("success", state.mode === "baseline" ? "Baseline" : "Hoàn tất");
    return;
  }

  trace.forEach((event, index) => {
    const row = createElement("div", "trace-step");
    row.append(createElement("div", "trace-index", String(event.step ?? index + 1)));

    const card = createElement("div", "trace-step-card");
    const top = createElement("div", "trace-step-top");
    const [kindLabel, kindClass] = traceKind(event);
    top.append(
      createElement("strong", "", `Step ${event.step ?? index + 1}`),
      createElement("span", `trace-kind ${kindClass}`, kindLabel),
    );
    card.append(top);

    addTraceBlock(card, "Thought", event.thought);
    if (event.tool) {
      const args = Array.isArray(event.args) ? event.args.map((arg) => JSON.stringify(arg)).join(", ") : "";
      addTraceBlock(card, "Action", `${event.tool}[${args}]`, true);
    }
    addTraceBlock(card, "Observation", event.observation, true);
    addTraceBlock(card, "Final answer", event.answer);
    row.append(card);
    elements.traceContent.append(row);
  });

  setTraceStatus(result.guardrail_triggered ? "warning" : "success", result.guardrail_triggered ? "Đã bảo vệ" : "Hoàn tất");
}

function updateComposerState() {
  const length = elements.input.value.length;
  elements.charCount.textContent = `${length} / 2000`;
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 120)}px`;
}

async function sendMessage(message) {
  if (state.busy) return;
  state.busy = true;
  elements.sendButton.disabled = true;
  setTraceStatus("running", "Đang suy luận");
  addMessage("user", message);
  const loader = addMessage("assistant", "", null, true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, mode: state.mode }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Không thể xử lý câu hỏi.");

    loader.remove();
    addMessage("assistant", payload.answer, payload);
    renderTrace(payload.trace, payload);
  } catch (error) {
    loader.remove();
    addMessage("assistant", `Mình gặp sự cố: ${error.message}`);
    setTraceStatus("warning", "Có lỗi");
    showToast(error.message);
  } finally {
    state.busy = false;
    elements.sendButton.disabled = false;
    elements.input.focus();
  }
}

function renderQuickPrompts() {
  elements.quickPrompts.innerHTML = "";
  state.testCases.forEach((testCase) => {
    const button = createElement("button", "quick-prompt", testCase.question);
    button.type = "button";
    button.title = testCase.question;
    button.addEventListener("click", () => {
      elements.input.value = testCase.question;
      updateComposerState();
      elements.input.focus();
    });
    elements.quickPrompts.append(button);
  });
}

function renderTools(tools) {
  elements.toolGrid.innerHTML = "";
  tools.forEach((tool, index) => {
    const card = createElement("article", "tool-card");
    card.append(
      createElement("div", "tool-number", String(index + 1).padStart(2, "0")),
      createElement("h3", "", tool),
      createElement("p", "", toolDescriptions[tool] || "Công cụ đã đăng ký trong Agent registry."),
    );
    elements.toolGrid.append(card);
  });
}

function renderEvaluation(payload) {
  const { summary, results } = payload;
  elements.evaluationMetrics.hidden = false;
  elements.evaluationMetrics.innerHTML = "";
  [
    [summary.total, "Test cases"],
    [summary.completed, "Hoàn thành"],
    [summary.tool_calls, "Tool calls"],
    [summary.guardrails, "Hard guardrails"],
  ].forEach(([value, label]) => {
    const card = createElement("div", "metric-card");
    card.append(createElement("strong", "", String(value)), createElement("span", "", label));
    elements.evaluationMetrics.append(card);
  });

  elements.evaluationResults.innerHTML = "";
  results.forEach((result) => {
    const card = createElement("article", "result-card");
    const top = createElement("div", "result-card-top");
    top.append(
      createElement("strong", "", `Test #${result.id}`),
      createElement("span", "result-badge", result.status === "completed" ? "PASS" : "SAFE"),
    );
    const path = result.trace.filter((event) => event.tool).map((event) => event.tool).join(" → ") || "Không cần tool";
    card.append(top, createElement("p", "", result.question), createElement("span", "result-path", path));
    elements.evaluationResults.append(card);
  });
}

async function runEvaluation() {
  elements.evaluateButton.disabled = true;
  const original = elements.evaluateButton.innerHTML;
  elements.evaluateButton.textContent = "Đang chạy 5 test…";
  try {
    const response = await fetch("/api/evaluate", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Không chạy được đánh giá.");
    renderEvaluation(payload);
    showToast(`Đã hoàn thành ${payload.summary.completed}/${payload.summary.total} test cases.`);
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.evaluateButton.disabled = false;
    elements.evaluateButton.innerHTML = original;
  }
}

async function bootstrap() {
  try {
    const [healthResponse, testsResponse] = await Promise.all([
      fetch("/api/health"),
      fetch("/api/test-cases"),
    ]);
    const health = await healthResponse.json();
    const tests = await testsResponse.json();
    state.testCases = tests.test_cases || [];
    renderQuickPrompts();
    renderTools(health.tools || []);
  } catch (_error) {
    elements.quickPrompts.innerHTML = '<span class="quick-label">Không tải được câu hỏi gợi ý.</span>';
    elements.toolGrid.innerHTML = '<div class="tool-card"><h3>Không tải được tool registry</h3><p>Hãy tải lại trang sau ít phút.</p></div>';
  }
}

elements.modeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
elements.input.addEventListener("input", updateComposerState);
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});
elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = elements.input.value.trim();
  if (!message) {
    showToast("Hãy nhập một câu hỏi trước khi gửi.");
    return;
  }
  elements.input.value = "";
  updateComposerState();
  sendMessage(message);
});
elements.evaluateButton.addEventListener("click", runEvaluation);

updateComposerState();
bootstrap();
