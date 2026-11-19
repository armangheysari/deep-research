import os
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled

load_dotenv(override=True)

for name in ("httpx", "httpcore", "httpx2", "httpcore2", "h2", "openai"):
    logging.getLogger(name).setLevel(logging.WARNING)

set_tracing_disabled(True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "nvidia/nemotron-3-ultra-550b-a55b:free")
HOW_MANY_SEARCHES = int(os.getenv("HOW_MANY_SEARCHES", "5"))

try:
    import httpx2 as _httpx
except ImportError:
    import httpx as _httpx

_http_client = _httpx.AsyncClient(
    http2=False,
    timeout=_httpx.Timeout(120.0, connect=30.0),
)

_openrouter_client = AsyncOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
    http_client=_http_client,
    max_retries=3,
    timeout=120.0,
)

model = OpenAIChatCompletionsModel(
    model=MODEL_NAME,
    openai_client=_openrouter_client,
)

# tweak: bump timeout to 120s
