"""GNews MCP Server using FastMCP.

Provides two MCP tools:
1. search_news - wraps the GNews Search endpoint
2. top_headlines - wraps the GNews Top Headlines endpoint

Environment:
  GNEWS_API_KEY must be set (optionally via a .env file).

Notes:
  - This server focuses on the essential parameters. Extend as needed.
  - Network errors and non-200 responses are surfaced as MCP tool errors.
"""

from __future__ import annotations

import os
import re
import asyncio  # (Reserved for future async expansions)
from typing import Any, Dict, Optional

import httpx
from cachetools import TTLCache
try:
    from diskcache import Cache as DiskCache  # persistent cache
except ImportError:  # pragma: no cover
    DiskCache = None  # type: ignore
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from dotenv import load_dotenv

try:
    # FastMCP high-level server interface
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise RuntimeError("FastMCP not available. Ensure 'mcp' package >= 1.21.2 is installed.") from e


load_dotenv()  # Load .env if present

API_BASE = "https://gnews.io/api/v4"
API_KEY_ENV = "GNEWS_API_KEY"  # Name of the environment variable holding your API key

# Simple in-memory cache (avoid hammering API for identical queries)
search_cache: TTLCache = TTLCache(maxsize=256, ttl=60)  # 1 minute TTL (in-memory)
headline_cache: TTLCache = TTLCache(maxsize=64, ttl=30)  # 30 seconds TTL (in-memory)

DISK_CACHE_DIR = os.getenv("GNEWS_CACHE_DIR")
disk_cache = None  # type: ignore
if DISK_CACHE_DIR and DiskCache:
    try:
        disk_cache = DiskCache(DISK_CACHE_DIR)
    except Exception:  # pragma: no cover
        disk_cache = None


class Article(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    source: Optional[str] = Field(None, description="Source name")
    published_at: Optional[str] = Field(None, description="ISO8601 timestamp")
    image: Optional[str] = None


def get_api_key() -> str:
    key = os.getenv(API_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"Missing {API_KEY_ENV} environment variable. Obtain an API key from https://gnews.io/"
        )
    return key


MAX_QUERY_LEN = 300

def sanitize_query(q: str) -> str:
    # Remove control characters except common whitespace, collapse spaces
    q = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", q)
    q = q.strip()
    # Collapse multiple spaces
    q = re.sub(r"\s+", " ", q)
    if not q:
        raise ValueError("Query must not be empty after sanitization")
    if len(q) > MAX_QUERY_LEN:
        raise ValueError(f"Query too long (>{MAX_QUERY_LEN} chars)")
    return q

def validate_max(m: int | FieldInfo) -> int:
    # Allow pydantic FieldInfo default objects
    if isinstance(m, FieldInfo):
        m = m.default  # type: ignore
    if not isinstance(m, int):
        raise ValueError("Parameter 'max' must be an integer")
    if not (1 <= m <= 100):
        raise ValueError("Parameter 'max' must be between 1 and 100 inclusive")
    return m


async def _fetch(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    api_key = get_api_key()
    merged = {"apikey": api_key, **{k: v for k, v in params.items() if v is not None}}
    url = f"{API_BASE}/{endpoint}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=merged)
        if resp.status_code != 200:
            raise RuntimeError(f"GNews API error {resp.status_code}: {resp.text[:300]}")
        return resp.json()


def _normalize_articles(raw: Dict[str, Any]) -> Dict[str, Any]:
    articles = []
    for a in raw.get("articles", []):
        articles.append(
            Article(
                title=a.get("title", ""),
                description=a.get("description"),
                url=a.get("url", ""),
                source=(a.get("source", {}) or {}).get("name"),
                published_at=a.get("publishedAt"),
                image=a.get("image"),
            ).model_dump()
        )
    return {"total": raw.get("totalArticles", len(articles)), "articles": articles}


mcp = FastMCP(
    name="gnews",
    instructions="MCP server providing GNews Search and Top Headlines tools",
)


@mcp.tool()
async def search_news(
    q: str = Field(..., description="Search query text"),
    lang: Optional[str] = Field(None, description="Language code, e.g. 'en'"),
    country: Optional[str] = Field(None, description="2-letter country code"),
    max: int = Field(10, description="Max articles (1-100)"),
    in_title: bool = Field(False, description="If true restrict search to titles"),
) -> Dict[str, Any]:
    """Search news articles via GNews.

    Mirrors https://docs.gnews.io/endpoints/search-endpoint (subset of params).
    """
    q = sanitize_query(q)
    max = validate_max(max)
    cache_key = (q, lang, country, max, in_title)
    if cache_key in search_cache:
        return search_cache[cache_key]
    if disk_cache is not None:
        disk_key = ("search", cache_key)
        cached = disk_cache.get(disk_key)
        if cached is not None:
            return cached
    params = {
        "q": q,
        "lang": lang,
        "country": country,
        "max": max,
        "in": "title" if in_title else None,
    }
    data = await _fetch("search", params)
    normalized = _normalize_articles(data)
    search_cache[cache_key] = normalized
    if disk_cache is not None:
        disk_cache.set(("search", cache_key), normalized, expire=60)
    return normalized


@mcp.tool()
async def top_headlines(
    lang: Optional[str] = Field(None, description="Language code, e.g. 'en'"),
    country: Optional[str] = Field(None, description="2-letter country code"),
    category: Optional[str] = Field(None, description="Category: general, world, nation, business, technology, entertainment, sports, science, health"),
    max: int = Field(10, description="Max articles (1-100)"),
) -> Dict[str, Any]:
    """Fetch top headlines via GNews.

    Mirrors https://docs.gnews.io/endpoints/top-headlines-endpoint (subset).
    """
    max = validate_max(max)
    cache_key = (lang, country, category, max)
    if cache_key in headline_cache:
        return headline_cache[cache_key]
    if disk_cache is not None:
        disk_key = ("headlines", cache_key)
        cached = disk_cache.get(disk_key)
        if cached is not None:
            return cached
    params = {
        "lang": lang,
        "country": country,
        "category": category,
        "max": max,
    }
    data = await _fetch("top-headlines", params)
    normalized = _normalize_articles(data)
    headline_cache[cache_key] = normalized
    if disk_cache is not None:
        disk_cache.set(("headlines", cache_key), normalized, expire=30)
    return normalized


# def run() -> None:  # Entry point for starting MCP server
#     # Run the server using stdio transport (default)
#     mcp.run("stdio")
    


# if __name__ == "__main__":
#     run()
