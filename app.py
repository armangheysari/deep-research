import asyncio
import json
import os
import threading
import queue as _queue

from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv

from research_manager import ResearchManager

load_dotenv(override=True)

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

_bg_loop = asyncio.new_event_loop()
_bg_thread = threading.Thread(
    target=_bg_loop.run_forever,
    daemon=True,
    name="deep-research-loop",
)
_bg_thread.start()


def _submit(coro):
    return asyncio.run_coroutine_threadsafe(coro, _bg_loop)


def _run_sync(coro, timeout=300):
    return _submit(coro).result(timeout=timeout)


manager = ResearchManager()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/clarify", methods=["POST"])
def clarify():
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        result = _run_sync(manager.clarify(query))
        return jsonify({
            "questions": [q.question for q in result.questions],
            "reasons": [q.reason for q in result.questions],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/research", methods=["POST"])
def research():
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get("query") or "").strip()
    clarifications = data.get("clarifications") or ""

    if not query:
        return jsonify({"error": "Query is required"}), 400

    updates: "_queue.Queue[object]" = _queue.Queue()
    SENTINEL = object()

    async def produce():
        try:
            async for update in manager.run(query, clarifications):
                updates.put(update)
        except Exception as exc:
            updates.put({"error": str(exc)})
        finally:
            updates.put(SENTINEL)

    _submit(produce())

    def event_stream():
        while True:
            item = updates.get()
            if item is SENTINEL:
                yield "data: [DONE]\n\n"
                break
            payload = item if not isinstance(item, str) else {"status": item}
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

# tweak: route order cleanup
