// Deep Research — initial single-step front-end
const $ = (sel) => document.querySelector(sel);

$("#btn-research").addEventListener("click", async () => {
  const query = $("#query").value.trim();
  if (!query) { alert("لطفاً سوال خود را وارد کنید"); return; }

  $("#status").innerHTML = "";
  $("#report").innerHTML = "";

  const resp = await fetch("/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
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
        if (obj.report) {
          $("#report").innerHTML = "<p>" + obj.report + "</p>";
        } else if (obj.status) {
          const div = document.createElement("div");
          div.className = "line";
          div.textContent = obj.status;
          $("#status").appendChild(div);
        }
      } catch {}
    }
  }
});
