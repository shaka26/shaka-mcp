# GNews MCP Server

An MCP (Model Context Protocol) server exposing GNews Search and Top Headlines endpoints via FastMCP tools.

## Features
* `search_news` – wraps `https://gnews.io/api/v4/search`
* `top_headlines` – wraps `https://gnews.io/api/v4/top-headlines`
* Basic in-memory caching to reduce duplicate requests.
* Optional persistent disk cache if `GNEWS_CACHE_DIR` is set (uses `diskcache`).
* Input validation for `max` (1–100) and query sanitization/length limit (≤300 chars).

## Setup
1. Obtain an API key from https://gnews.io/
2. Set environment variable `GNEWS_API_KEY` (or create a `.env` file):
	 ```env
	 GNEWS_API_KEY=your_key_here
	 ```
3. Install dependencies (with uv or pip):
	 ```bash
	 pip install .
	 ```

## Running the Server
This process is intended to be launched by an MCP-compatible client. For manual smoke test:
```bash
python main.py
```
(It will wait for MCP JSON-RPC over stdio.)

## Tool Schemas (Summary)

### search_news
Inputs:
* `q` (str, required) – search query (sanitized, trimmed, max 300 chars)
* `lang` (str, optional) – language code
* `country` (str, optional) – 2-letter country code
* `max` (int, default 10) – number of articles (1–100)
* `in_title` (bool, default false) – restrict search to titles

### top_headlines
Inputs:
* `lang` (str, optional)
* `country` (str, optional)
* `category` (str, optional) – one of documented categories
* `max` (int, default 10)

### Output Format
```json
{
	"total": 123,
	"articles": [
		{
			"title": "...",
			"description": "...",
			"url": "https://...",
			"source": "Reuters",
			"published_at": "2025-11-17T10:00:00Z",
			"image": "https://..."
		}
	]
}
```

## Extending
Add more parameters (e.g. `from`, `to`, `sortBy`) by editing the tool function signatures and passing them through to `_fetch`.

## Persistent Caching
Set `GNEWS_CACHE_DIR` to a directory path to enable disk-backed caching. If not set, only in-memory TTL caches are used.


## License
MIT (adjust as needed).

