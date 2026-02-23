"""网络搜索工具 — DuckDuckGo 免费搜索"""
import logging
import asyncio
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

@tool
async def web_search(query: str, max_results: int = 5) -> dict:
    """搜索互联网获取参考信息。输入搜索关键词，返回相关结果摘要。"""
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: _duckduckgo_search(query, max_results))
        return {"query": query, "results": results, "count": len(results)}
    except ImportError:
        return {"query": query, "results": [{"title": "需安装 duckduckgo-search", "snippet": "pip install duckduckgo-search", "url": ""}], "count": 1}
    except Exception as e:
        return {"query": query, "results": [], "count": 0, "error": str(e)}

def _duckduckgo_search(query: str, max_results: int) -> list[dict]:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return [{"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")} for r in ddgs.text(query, max_results=max_results)]
