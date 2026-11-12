from agents import Runner, trace, gen_trace_id
from search_agent import search_agent
from planner_agent import planner_agent, WebSearchItem, WebSearchPlan
from writer_agent import writer_agent, ReportData
from email_agent import email_agent
from clarifier_agent import clarifier_agent, ClarifierResult
from evaluator_agent import evaluator_agent, ReportEvaluation
import asyncio
import logging

for name in ("httpx", "httpcore", "httpx2", "httpcore2", "h2", "openai"):
    logging.getLogger(name).setLevel(logging.WARNING)
logging.getLogger("h2").setLevel(logging.ERROR)

MAX_TURNS = 25


class ResearchManager:

    async def clarify(self, query: str) -> ClarifierResult:
        result = await self._run_with_retry(
            clarifier_agent, f"User query: {query}"
        )
        return result.final_output

    async def run(self, query: str, clarifications: str = ""):
        trace_id = gen_trace_id()
        with trace("Research trace", trace_id=trace_id):
            yield f"Starting research. Trace: https://platform.openai.com/traces/trace?trace_id={trace_id}"

            enriched_query = query
            if clarifications.strip():
                enriched_query = (
                    f"Original query: {query}\n"
                    f"Clarifications from user: {clarifications.strip()}"
                )
                yield "Clarifications applied to research plan."

            yield "Planning searches (asking the planner agent)..."
            search_plan = await self.plan_searches(enriched_query)
            yield f"Planner produced {len(search_plan.searches)} search terms:"
            for i, s in enumerate(search_plan.searches, 1):
                q = s.query if len(s.query) <= 80 else s.query[:77] + "..."
                yield f"  {i}. {q}"
            yield f"Launching {len(search_plan.searches)} searches in parallel..."

            progress_q: asyncio.Queue = asyncio.Queue()
            search_task = asyncio.create_task(
                self.perform_searches(search_plan, progress_q)
            )

            while True:
                if search_task.done() and progress_q.empty():
                    break
                try:
                    msg = await asyncio.wait_for(progress_q.get(), timeout=0.5)
                    if msg is not None:
                        yield msg
                except asyncio.TimeoutError:
                    continue

            search_results = await search_task
            yield "All searches complete."

            yield "Writing the report (this can take 20-40 seconds)..."
            report = await self.write_report(enriched_query, search_results)
            yield "Report drafted."

            yield "Evaluating report quality..."
            evaluation = await self.evaluate_report(query, report)
            yield f"Evaluation done. Overall score: {evaluation.overall_score}/100"

            yield "Sending email / push notification..."
            await self.send_email(report)
            yield "Email sent. Research complete."

            yield {
                "report": report.markdown_report,
                "short_summary": report.short_summary,
                "follow_up_questions": report.follow_up_questions,
                "evaluation": evaluation.model_dump(),
            }

    async def _run_with_retry(self, agent, prompt, retries=2):
        last_exc = None
        for attempt in range(retries + 1):
            try:
                return await Runner.run(agent, prompt, max_turns=MAX_TURNS)
            except Exception as exc:
                last_exc = exc
                msg = str(exc)
                if any(s in msg for s in ("429", "Provider returned error",
                                          "connection reset", "Max turns")):
                    if attempt < retries:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                raise
        raise last_exc  # type: ignore[misc]

    async def plan_searches(self, query: str) -> WebSearchPlan:
        result = await self._run_with_retry(planner_agent, f"Query: {query}")
        return result.final_output

    async def perform_searches(self, search_plan: WebSearchPlan, progress_q: asyncio.Queue) -> list[str]:
        total = len(search_plan.searches)
        done = 0
        results: list[str | None] = [None] * total

        async def run_one(idx: int, item: WebSearchItem):
            nonlocal done
            q = item.query if len(item.query) <= 70 else item.query[:67] + "..."
            await progress_q.put(f"  [{idx+1}/{total}] searching: {q}")
            try:
                res = await self.search(item)
            except Exception as exc:
                await progress_q.put(f"  [{idx+1}/{total}] FAILED: {exc}")
                res = f"(search failed: {exc})"
            done += 1
            await progress_q.put(f"  [{done}/{total}] done")
            results[idx] = res

        tasks = [run_one(i, item) for i, item in enumerate(search_plan.searches)]
        await asyncio.gather(*tasks)
        await progress_q.put(None)
        return results  # type: ignore[return-value]

    async def search(self, item: WebSearchItem) -> str | None:
        input_message = f"Search term: {item.query}\nReason for searching: {item.reason}"
        result = await self._run_with_retry(search_agent, input_message)
        return result.final_output

    async def write_report(self, query: str, search_results: list[str]) -> ReportData:
        input_message = f"Original query: {query}\nSummarized search results: {search_results}"
        result = await self._run_with_retry(writer_agent, input_message)
        return result.final_output

    async def evaluate_report(self, original_query: str, report: ReportData) -> ReportEvaluation:
        input_message = (
            f"Original query: {original_query}\n\n"
            f"Report:\n{report.markdown_report[:8000]}"
        )
        result = await self._run_with_retry(evaluator_agent, input_message)
        return result.final_output

    async def send_email(self, report: ReportData) -> None:
        await self._run_with_retry(email_agent, report.markdown_report)

# tweak: pass original_query separately to evaluator
