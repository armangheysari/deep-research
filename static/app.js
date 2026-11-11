// Deep Research — hand-made front-end logic
// Talks to the Flask backend (/clarify and /research endpoints).

const $ = (sel) => document.querySelector(sel);
const show = (id) => {
  document.querySelectorAll(".step").forEach((s) => s.classList.remove("active"));
  $("#step-" + id).classList.add("active");
};

$("#btn-clarify").addEventListener("click", async () => {
  const query = $("#query").value.trim();
  if (!query) { alert("Please enter a question first"); return; }

  $("#btn-clarify").textContent = "Preparing…";
  $("#btn-clarify").disabled = true;

  try {
    const resp = await fetch("/clarify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await resp.json();
    if (data.error) { alert(data.error); return; }

    const box = $("#clarify-questions");
    box.innerHTML = "";
    if (!data.questions || data.questions.length === 0) {
      box.innerHTML = "<p>No questions needed — go straight to research.</p>";
    } else {
      data.questions.forEach((q, i) => {
        const div = document.createElement("div");
        div.className = "question-item";
        const reason = (data.reasons && data.reasons[i]) ? `<span class="reason">${data.reasons[i]}</span>` : "";
        div.innerHTML = `<strong>${i + 1}.</strong> ${q}${reason}`;
        box.appendChild(div);
      });
    }
    show("clarify");
  } catch (e) {
    alert("Error: " + e.message);
  } finally {
    $("#btn-clarify").textContent = "Next";
    $("#btn-clarify").disabled = false;
  }
});

$("#btn-back").addEventListener("click", () => show("question"));

$("#btn-research").addEventListener("click", async () => {
  const query = $("#query").value.trim();
  const clarifications = $("#clarifications").value.trim();

  show("research");
  $("#status").innerHTML = "";
  $("#report").innerHTML = "";
  $("#evaluation").classList.add("hidden");

  const resp = await fetch("/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, clarifications }),
  });

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = chunk.trim();
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") continue;
      try {
        const obj = JSON.parse(payload);
        handleUpdate(obj);
      } catch { /* ignore partials */ }
    }
  }
});

function handleUpdate(obj) {
  if (typeof obj === "object" && obj.report) {
    renderReport(obj.report, obj.evaluation, obj.short_summary, obj.follow_up_questions);
  } else if (obj.status) {
    const div = document.createElement("div");
    div.className = "line";
    div.textContent = obj.status;
    $("#status").appendChild(div);
    $("#status").scrollTop = $("#status").scrollHeight;
  }
}

function renderReport(md, evaluation, summary, followUps) {
  // Very small markdown renderer (headings, bold, code, lists, links)
  let html = md
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/^\s*[-*] (.+)$/gim, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
  $("#report").innerHTML = '<p>' + html + '</p>';

  if (summary) {
    const s = document.createElement("div");
    s.className = "question-item";
    s.style.borderColor = "var(--blue)";
    s.innerHTML = "<strong>Summary:</strong> " + summary;
    $("#report").prepend(s);
  }
  if (followUps && followUps.length) {
    const f = document.createElement("div");
    f.className = "question-item";
    f.style.borderColor = "var(--purple)";
    f.innerHTML = "<strong>Suggested follow-up topics:</strong><br>" + followUps.map(q => "• " + q).join("<br>");
    $("#report").append(f);
  }

  if (evaluation) {
    renderEvaluation(evaluation);
  }
}

function renderEvaluation(ev) {
  const box = $("#evaluation");
  box.classList.remove("hidden");
  const scoreCell = (label, val) => `<div class="score-cell"><b>${label}:</b> ${val}</div>`;
  box.innerHTML = `
    <h3>Report evaluation</h3>
    <div class="score-grid">
      ${scoreCell("Relevance", ev.relevance_score + "/5")}
      ${scoreCell("Accuracy", ev.accuracy_score + "/5")}
      ${scoreCell("Depth", ev.depth_score + "/5")}
      ${scoreCell("Structure", ev.structure_score + "/5")}
      ${scoreCell("Overall", ev.overall_score + "/100")}
      ${scoreCell("Real frameworks?", ev.mentions_real_frameworks ? "Yes" : "No")}
    </div>
    <div class="strengths"><strong>Strengths:</strong><ul>${ev.strengths.map(s => "<li>" + s + "</li>").join("")}</ul></div>
    <div class="weaknesses"><strong>Weaknesses:</strong><ul>${ev.weaknesses.map(s => "<li>" + s + "</li>").join("")}</ul></div>
    <p><strong>Suggestion for next run:</strong> ${ev.suggestion_for_next_iteration}</p>
  `;
}
