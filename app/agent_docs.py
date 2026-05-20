"""Agent-readable documentation served from the API host."""

LLMS_TXT = """# Scrappling API

> Scrappling is a FastAPI wrapper around Scrapling. It accepts public URLs plus selectors and returns extracted JSON.

Use this API for publicly accessible pages only. Do not use it to bypass login, paywall, CAPTCHA, private-content, or site access controls.

## Agent docs

- [Full agent guide](/llms-full.txt): Complete request examples, response shape, and safe-use notes.
- [Quick agent guide](/agents.md): Compact Markdown instructions for agent context.
- [OpenAPI schema](/openapi.json): Machine-readable FastAPI schema.

## API

- [GET /health](/health): Liveness probe.
- [POST /scrape](/scrape): Scrape a URL with `http`, `stealth`, or `dynamic` fetcher options.

## Optional

- [Scrapling project](https://github.com/D4Vinci/Scrapling): Upstream scraping library.
"""

AGENTS_MD = """# Scrappling API Agent Guide

Use Scrappling API when you need to scrape a public webpage with explicit CSS or XPath selectors.

## Endpoint

```text
POST /scrape
Content-Type: application/json
```

```json
{
  "url": "https://quotes.toscrape.com/",
  "fetcher": "http",
  "css": [".quote .text::text", ".author::text"],
  "xpath": null,
  "return_html": false,
  "timeout": 30,
  "headless": true,
  "network_idle": false
}
```

## Fetchers

- `http`: Fast plain HTTP fetch.
- `stealth`: Browser-backed Scrapling fetcher.
- `dynamic`: Playwright Chromium fetcher.

## Response

```json
{
  "url": "https://quotes.toscrape.com/",
  "status": 200,
  "fetcher": "http",
  "results": {
    "css": {
      ".quote .text::text": ["..."],
      ".author::text": ["..."]
    },
    "xpath": {}
  },
  "html": null
}
```

## Rules

- Scrape public pages only.
- Do not bypass login, paywalls, CAPTCHA, private pages, or access controls.
- Keep request volume polite.
- Use `/openapi.json` for the complete machine-readable schema.
"""

LLMS_FULL_TXT = AGENTS_MD + """

## Notes

The higher-level Scrappling UI proxy can turn a URL into cleaned Markdown and JSON at `/api/scrape` on the frontend host. This raw backend API is lower-level: it fetches the page and evaluates the selectors you provide.
"""
