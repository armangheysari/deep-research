from agents import Agent, ModelSettings
from web_search_tool import web_search
from model_config import model

INSTRUCTIONS = """
You are a research assistant. Given a search term, use your web search tool to
search the web and produce a concise summary of the results.
The summary must be 2-3 paragraphs and less than 300 words.
Capture the main points and be succinct. Reply only with the summary.
"""

settings = ModelSettings(tool_choice="required")
tools = [web_search]

search_agent = Agent(
    name="Search Agent",
    instructions=INSTRUCTIONS,
    tools=tools,
    model=model,
    model_settings=settings,
)
