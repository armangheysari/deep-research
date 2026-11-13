import warnings
warnings.filterwarnings("ignore", message=".*renamed.*")

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from agents import function_tool


@function_tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return a combined summary of results.

    Args:
        query: The search term to look up on the web.
        max_results: Maximum number of results to fetch (default 5).
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        return f"Search error for '{query}': {exc}"

    if not results:
        return f"No results found for: {query}"

    parts = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, start=1):
        title = r.get("title", "")
        body = r.get("body", "")
        href = r.get("href") or r.get("link", "")
        parts.append(f"{i}. {title}\n   {body}\n   Source: {href}\n")
    return "\n".join(parts)
