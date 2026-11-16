# Deep Research

Autonomous multi-agent research assistant that takes a natural-language question,
clarifies intent with the user, runs parallel web searches, synthesises a long-form
report, scores its own quality, and delivers the result via email or push notification.

The whole stack runs on free infrastructure: the LLM comes from OpenRouter's free
tier, web search is powered by DuckDuckGo (no API key), and the UI is a hand-rolled
Flask app — no Gradio, no managed hosting required.

---

## What it does

1. **Clarify** — when the user submits a vague question, a clarifier agent asks 2–3
   focused follow-up questions (timeframe, industry, audience, depth) before any
   search happens. The answers are folded into every downstream prompt.
2. **Plan** — a planner agent decomposes the enriched query into N independent
   search terms (default 5), each with a one-line rationale.
3. **Search** — N search agents run in parallel via `asyncio.gather`. Each one
   calls a DuckDuckGo-backed tool and returns a ≤300-word summary with sources.
4. **Write** — a writer agent turns the query + all summaries into a long Markdown
   report (target 5–10 pages, ≥1000 words), plus a short summary and follow-up
   questions.
5. **Evaluate** — an evaluator agent scores the finished report on relevance,
   accuracy, depth, structure, and whether it cites real frameworks. The score
   and a one-line improvement tip are surfaced in the UI.
6. **Deliver** — an email agent converts the report to clean HTML and sends it
   via SMTP, or falls back to a Pushover push notification if SMTP is unavailable.

Every stage streams live progress to the browser via Server-Sent Events, so the
user sees "planning…", "5 searches running…", "writing report…" as it happens.

---

## Architecture

```
                         ┌─────────────┐
            user query → │  Clarifier  │ → 2-3 questions back to user
                         └─────────────┘
                                │  (user answers)
                                ▼
                         ┌─────────────┐
                        │   Planner   │ → N search terms (Pydantic)
                         └─────────────┘
                                │
                 ┌──────────────┼──────────────┐   (parallel)
                 ▼              ▼              ▼
            ┌─────────┐    ┌─────────┐    ┌─────────┐
            │ Search  │    │ Search  │ …  │ Search  │   (DuckDuckGo)
            └─────────┘    └─────────┘    └─────────┘
                                │
                                ▼
                         ┌─────────────┐
                        │   Writer    │ → Markdown report
                         └─────────────┘
                          │           │
                          ▼           ▼
                  ┌────────────┐  ┌────────────┐
                  │ Evaluator  │  │   Email    │ → SMTP or Pushover
                  └────────────┘  └────────────┘
```

All six agents share one OpenRouter model object, configured once in
`model_config.py` via `OpenAIChatCompletionsModel` + `AsyncOpenAI`. Each agent
gets its own `Runner.run` call — there is no single "manager" LLM deciding the
flow. The flow is plain Python.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Agent framework | OpenAI Agents SDK (`openai-agents`) | Lightweight, no framework voodoo |
| LLM provider | OpenRouter (free tier) | Provider-agnostic, no OpenAI billing |
| Default model | `nvidia/nemotron-3-ultra-550b-a55b:free` | Supports tool calling + structured output |
| Web search | DuckDuckGo via `ddgs` | No API key, no rate limits worth worrying about |
| Structured I/O | Pydantic v2 | Type-safe contracts between agents |
| Web server | Flask | Minimal, no build step |
| Live updates | Server-Sent Events | One-way streaming, no WebSocket needed |
| Styling | Hand-written CSS | No Tailwind, no framework |
| Notifications | SMTP / Pushover | Email when possible, push as fallback |

---

## Project layout

```
deep_research/
├── app.py                  # Flask app: /, /clarify, /research (SSE), /health
├── research_manager.py     # Orchestrator: 6 agents, asyncio.gather, yield
├── model_config.py         # Shared OpenRouter client + model object
├── clarifier_agent.py      # Asks 2-3 clarifying questions
├── planner_agent.py        # Splits query into N search terms
├── search_agent.py         # Runs DuckDuckGo + summarises
├── writer_agent.py         # Writes long-form Markdown report
├── evaluator_agent.py      # Scores the report on 5 dimensions
├── email_agent.py          # Sends report via SMTP or Pushover
├── web_search_tool.py      # @function_tool wrapper around DuckDuckGo
├── messenger.py            # send_email() and push() helpers
├── templates/
│   └── index.html          # 3-step UI: question → clarify → live report
├── static/
│   ├── style.css          # Amber/blue/purple palette, sharp-square design
│   └── app.js             # SSE reader + tiny Markdown renderer
├── .env                    # OpenRouter key, model name, search count, etc.
└── requirements.txt
```

---

## Key implementation details

### Provider-agnostic model setup

`model_config.py` wires the OpenAI Agents SDK to OpenRouter. The SDK depends
on `httpx2` which uses HTTP/2 by default, but OpenRouter resets idle HTTP/2
connections. The client is therefore built with `http2=False` to force plain
HTTP/1.1 and avoid "connection reset" errors during long report generation.

Every agent receives `model=model` instead of `model="gpt-5.4-mini"`. Tracing
is disabled because the trace exporter expects an OpenAI account.

### DuckDuckGo instead of WebSearchTool

OpenAI's hosted `WebSearchTool` only works with OpenAI models and costs ~1¢ per
search. `web_search_tool.py` replaces it with a plain `@function_tool` that
calls DuckDuckGo through the `ddgs` package — free, keyless, and works with any
LLM provider. The tool returns a formatted text block of titles + snippets +
source URLs, which the search agent summarises.

### Structured outputs everywhere

Three Pydantic schemas govern inter-agent contracts:

- `WebSearchPlan` — list of `WebSearchItem(reason, query)` from the planner
- `ReportData` — `short_summary`, `markdown_report`, `follow_up_questions`
- `ReportEvaluation` — 5 numeric scores + strengths/weaknesses + next-iteration tip

Each schema is passed as `output_type=...` to the agent, so the framework
injects the JSON schema into the system prompt and parses the model's JSON
response back into a typed Python object.

### Field-order trick

In `WebSearchItem`, `reason` is declared **before** `query`. LLMs generate
structured-output fields in declaration order, so this forces the model to
justify the search before writing the query — producing higher-quality search
terms than the reverse order would.

### Parallel search with asyncio.gather

`research_manager.perform_searches` builds a list of coroutines (one per
search term) and runs them all at once:

```python
tasks = [self.search(item) for item in search_plan.searches]
return await asyncio.gather(*tasks)
```

With 5 searches this cuts wall time from ~5× the per-search latency down to
~1× — typically 10–20 seconds total instead of a minute.

### Live UI streaming via SSE

The `/research` endpoint returns a `text/event-stream` response. The
`ResearchManager.run` method is an async generator that `yield`s status
strings and finally a dict with the report + evaluation. Flask converts each
yield into an SSE `data:` line, and `static/app.js` reads the stream with the
Fetch API's streaming reader, appending status lines and rendering the final
Markdown report inline.

### tool_choice="required"

Both `search_agent` and `email_agent` set `ModelSettings(tool_choice="required")`
so the model is forced to call its tool at least once. Without this, smaller
models sometimes skip the search/email step entirely and hallucinate a result.

### Clarifying-questions flow

The clarifier agent runs **before** the research pipeline. Its output
(`ClarifierResult`) is just a list of 2–3 questions shown to the user in step
2 of the UI. The user's free-text answers are concatenated into the query
string that gets passed to both `planner_agent` and `writer_agent`, so the
entire pipeline benefits from the clarified intent.

### Self-evaluation

After the writer finishes, the evaluator agent receives the original query and
the report body, and returns a `ReportEvaluation` with:

- 5 individual scores (relevance, accuracy, depth, structure, real-frameworks flag)
- An overall 0–100 score
- Lists of strengths and weaknesses
- A single concrete suggestion for the next iteration

The UI renders this as a coloured panel below the report, so the user can see
at a glance how trustworthy the report is.

---

## Configuration

All runtime knobs live in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | (none) | Required — your OpenRouter key |
| `DEFAULT_MODEL_NAME` | `nvidia/nemotron-3-ultra-550b-a55b:free` | Any OpenRouter model id |
| `HOW_MANY_SEARCHES` | `5` | Number of parallel searches per query |
| `USE_EMAIL` | `false` | `true` = SMTP, `false` = Pushover |
| `PUSHOVER_USER` | (none) | Pushover user id (if `USE_EMAIL=false`) |
| `PUSHOVER_TOKEN` | (none) | Pushover app token |
| `EMAIL_ADDRESS` | (none) | SMTP sender (if `USE_EMAIL=true`) |
| `EMAIL_SMTP_SERVER` | (none) | SMTP host (e.g. `smtp.gmail.com`) |
| `EMAIL_APP_PASSWORD` | (none) | SMTP app-specific password |

---

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`.

---

## Cost

The default model is free on OpenRouter. DuckDuckGo is free. The only limit is
OpenRouter's daily free-model quota (typically ~50 requests/day). A single
research run uses 1 (clarifier) + 1 (planner) + N (searches) + 1 (writer) +
1 (evaluator) + 1 (email) = N+5 LLM calls, so with `HOW_MANY_SEARCHES=5` that's
10 calls per run — roughly 5 runs per day on the free tier.
