from pydantic import BaseModel, Field
from agents import Agent
from model_config import model


INSTRUCTIONS = """
You are a strict research report evaluator. Given a research query and the
final report, you must rate the report on several quality dimensions.

Be strict and honest. If a dimension is missing or weak, give a low score.
"""


class ReportEvaluation(BaseModel):
    relevance_score: int = Field(description="Score 1-5 on how relevant the report is to the query.")
    accuracy_score: int = Field(description="Score 1-5 on factual accuracy and up-to-date content.")
    depth_score: int = Field(description="Score 1-5 on depth and detail of analysis.")
    structure_score: int = Field(description="Score 1-5 on clarity, formatting and markdown structure.")
    mentions_real_frameworks: bool = Field(description="Whether the report references real, named frameworks/tools.")
    overall_score: int = Field(description="Overall weighted score 1-100.")
    strengths: list[str] = Field(description="What the report did well.")
    weaknesses: list[str] = Field(description="Where the report fell short.")
    suggestion_for_next_iteration: str = Field(description="One concrete tip to improve the prompts next time.")


evaluator_agent = Agent(
    name="Evaluator Agent",
    instructions=INSTRUCTIONS,
    model=model,
    output_type=ReportEvaluation,
)
