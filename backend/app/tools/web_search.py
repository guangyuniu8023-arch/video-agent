"""网络搜索工具 — Planner 用于获取风格参考、场景描述等创作灵感

当前实现: DuckDuckGo 免费搜索 (无需 API Key)
备选: Tavily / SerpAPI (需配置 key)
"""

import logging
from app.tools import register_tool

logger = logging.getLogger(__name__)


@register_tool("web_search")
async def web_search(query: str, max_results: int = 5) -> dict:
    """搜索互联网获取参考信息。输入搜索关键词，返回相关结果摘要。"""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: _duckduckgo_search(query, max_results))
        return {"query": query, "results": results, "count": len(results)}
    except ImportError:
        logger.warning("duckduckgo_search not installed, returning mock results")
        return {
            "query": query,
            "results": [{"title": "搜索功能需要安装 duckduckgo-search", "snippet": "pip install duckduckgo-search", "url": ""}],
            "count": 1,
        }
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return {"query": query, "results": [], "count": 0, "error": str(e)}


def _duckduckgo_search(query: str, max_results: int) -> list[dict]:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = []
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", ""),
            })
        return results
