# scrappling

A Boltic serverless service that wraps [Scrapling](https://github.com/D4Vinci/Scrapling)
behind a small FastAPI HTTP API. Send a URL + selectors, get JSON back.

## Endpoints

- `GET /health` — liveness probe
- `GET /` — self-doc
- `POST /scrape` — see below

### `POST /scrape`

```json
{
  "url": "https://quotes.toscrape.com/",
  "fetcher": "http",          // "http" | "stealth" | "dynamic"
  "css": [".quote .text::text", ".author::text"],
  "xpath": null,
  "return_html": false,
  "timeout": 30,              // http fetcher only
  "headless": true,           // stealth/dynamic
  "network_idle": false       // stealth/dynamic
}
```

Response:

```json
{
  "url": "https://quotes.toscrape.com/",
  "status": 200,
  "fetcher": "http",
  "results": {
    "css": { ".quote .text::text": ["...", "..."], ".author::text": ["...", "..."] },
    "xpath": {}
  },
  "html": null
}
```

## Fetcher cheat-sheet

| fetcher   | Uses                       | Speed     | Bypasses CF / JS |
| --------- | -------------------------- | --------- | ---------------- |
| `http`    | plain HTTP request         | ⚡ fast    | ❌                |
| `stealth` | Camoufox + anti-bot tricks | 🐢 slow   | ✅                |
| `dynamic` | Playwright Chromium        | 🐢 slow   | partial          |

## Local dev

```bash
docker build -t scrappling .
docker run --rm -p 8080:8080 scrappling

curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/scrape \
  -H 'content-type: application/json' \
  -d '{"url":"https://quotes.toscrape.com/","fetcher":"http","css":[".quote .text::text"]}'
```

The first stealth/dynamic request after a cold start is slow (~10–20 s) while
Chromium boots; subsequent requests reuse the launched browser context.

## Deploy

This repo is wired to [Boltic](https://docs.boltic.io). `boltic.yaml` controls
the deployed instance: image build, port mapping (`8080`), resources (1 vCPU /
~1.5 GB RAM), and request timeout (120 s). Push to the configured remote and
Boltic builds + redeploys automatically.

> ⚠️ The `/scrape` endpoint is **unauthenticated**. Anyone with the deployed URL
> can use it. If that's not what you want, add a bearer-token check in
> `app/main.py` and set the secret as an env var in `boltic.yaml`.
