import os
import tempfile
import pytest
from unittest.mock import AsyncMock, patch
import main

@pytest.mark.asyncio
async def test_search_news_basic():
    mock_response = {
        "totalArticles": 1,
        "articles": [
            {
                "title": "Hello",
                "description": "Desc",
                "url": "http://example.com",
                "source": {"name": "Example"},
                "publishedAt": "2025-11-17T00:00:00Z",
                "image": None,
            }
        ],
    }
    with patch("main._fetch", AsyncMock(return_value=mock_response)):
        r1 = await main.search_news(q="  hello  ")  # test trimming
        r2 = await main.search_news(q="hello")  # cached (sanitized equivalent)
        assert r1 == r2
        assert r1["total"] == 1
        assert len(r1["articles"]) == 1
        assert r1["articles"][0]["title"] == "Hello"

@pytest.mark.asyncio
async def test_top_headlines_basic():
    mock_response = {
        "totalArticles": 2,
        "articles": [
            {
                "title": "Headline1",
                "description": None,
                "url": "http://example.com/1",
                "source": {"name": "Src1"},
                "publishedAt": None,
                "image": None,
            },
            {
                "title": "Headline2",
                "description": "Desc2",
                "url": "http://example.com/2",
                "source": {"name": "Src2"},
                "publishedAt": "2025-11-17T01:00:00Z",
                "image": None,
            },
        ],
    }
    with patch("main._fetch", AsyncMock(return_value=mock_response)):
        r = await main.top_headlines(lang="en")
        assert r["total"] == 2
        assert len(r["articles"]) == 2
        titles = {a["title"] for a in r["articles"]}
        assert {"Headline1", "Headline2"} == titles
@pytest.mark.asyncio
async def test_search_news_validation_errors():
    with pytest.raises(ValueError):
        await main.search_news(q="   ")  # empty after trim
    with pytest.raises(ValueError):
        await main.search_news(q="x" * 301)  # too long
    with patch("main._fetch", AsyncMock(return_value={"totalArticles":0,"articles":[]})):
        with pytest.raises(ValueError):
            await main.search_news(q="ok", max=0)
        with pytest.raises(ValueError):
            await main.search_news(q="ok", max=101)

@pytest.mark.asyncio
async def test_disk_cache_integration():
    mock_response = {"totalArticles":1, "articles": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["GNEWS_CACHE_DIR"] = tmpdir
        # Reload module level disk cache (simulate fresh start)
        from importlib import reload
        reload(main)
        with patch("main._fetch", AsyncMock(return_value=mock_response)):
            r1 = await main.search_news(q="disk")
        # Clear in-memory cache to force disk use
        main.search_cache.clear()
        with patch("main._fetch", AsyncMock(side_effect=AssertionError("Should not refetch"))):
            r2 = await main.search_news(q="disk")
        assert r1 == r2
        # Close disk cache before directory teardown to avoid Windows file lock
        if main.disk_cache:
            main.disk_cache.close()
    os.environ.pop("GNEWS_CACHE_DIR", None)
