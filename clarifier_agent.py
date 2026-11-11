from pydantic import BaseModel, Field
from agents import Agent
from model_config import model


INSTRUCTIONS = """
You are a research clarifier. Given the user's initial research question, produce
2 to 3 short clarifying questions that will help narrow down what the user is
really looking for.

Ask about things like:
- Time period of interest (e.g. this year, last 5 years, historical)
- Industry or domain (e.g. finance, healthcare, general)
- Audience for the report (e.g. technical, executive, general)
- Depth or length preference

Keep each question short and specific. Do not ask more than 3 questions.
"""


class ClarifyingQuestion(BaseModel):
    question: str = Field(description="A short clarifying question to ask the user.")
    reason: str = Field(description="Why this question helps refine the research.")


class ClarifierResult(BaseModel):
    questions: list[ClarifyingQuestion] = Field(
        description="A list of 2-3 clarifying questions for the user."
    )


clarifier_agent = Agent(
    name="Clarifier Agent",
    instructions=INSTRUCTIONS,
    model=model,
    output_type=ClarifierResult,
)
