import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel

load_dotenv(override=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "nvidia/nemotron-3-ultra-550b-a55b:free")
HOW_MANY_SEARCHES = int(os.getenv("HOW_MANY_SEARCHES", "5"))

_openrouter_client = AsyncOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

model = OpenAIChatCompletionsModel(
    model=MODEL_NAME,
    openai_client=_openrouter_client,
)
