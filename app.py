import asyncio
import json
import os

from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv

from research_manager import ResearchManager

load_dotenv(override=True)

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

manager = ResearchManager()


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import threading
            result = {}
            def runner():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result["value"] = new_loop.run_until_complete(coro)
                new_loop.close()
            t = threading.Thread(target=runner)
            t.start()
            t.join()
            return result.get("value")
    except RuntimeError:
        loop = None
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/research", methods=["POST"])
def research():
    """Stream the research pipeline as Server-Sent Events."""
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Query is required"}), 400

    def event_stream():
        async def consume():
            async for update in manager.run(query):
                yield update

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        agen = consume()

        try:
            while True:
                try:
                    update = loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    break
                payload = update if not isinstance(update, str) else {"status": update}
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        finally:
            loop.close()
            yield "data: [DONE]\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
