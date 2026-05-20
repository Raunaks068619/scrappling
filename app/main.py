"""FastAPI wrapper around Scrapling's fetchers.

Exposes a single generic POST /scrape endpoint that takes a URL plus a list of
CSS / XPath selectors and returns extracted data as JSON. Three fetchers are
selectable per-request:

    "http"    -> Fetcher          (plain HTTP, no browser)
    "stealth" -> StealthyFetcher  (Camoufox + anti-bot bypass)
    "dynamic" -> DynamicFetcher   (Playwright Chromium, full JS)

The endpoint is intentionally unauthenticated — see boltic.yaml. Add a bearer
check in `verify_auth` if/when that changes.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, HttpUrl

from .agent_docs import AGENTS_MD, LLMS_FULL_TXT, LLMS_TXT

# Lazy-import the heavy scrapling fetchers inside the dispatch so cold start of
# /health stays fast and an import failure on a single fetcher doesn't kill the
# whole app.

logger = logging.getLogger("scrappling")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="Scrappling",
    description="Scrapling-as-a-service. POST /scrape with a URL + selectors.",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

FetcherName = Literal["http", "stealth", "dynamic"]


class ScrapeRequest(BaseModel):
    url: HttpUrl
    fetcher: FetcherName = "http"
    css: list[str] | None = Field(default=None, description="CSS selectors to extract")
    xpath: list[str] | None = Field(default=None, description="XPath expressions to extract")
    return_html: bool = Field(default=False, description="Include the full page HTML in the response")
    timeout: int = Field(default=30, ge=1, le=120, description="Request timeout in seconds (http fetcher only)")
    headless: bool = Field(default=True, description="Headless mode for stealth/dynamic fetchers")
    network_idle: bool = Field(default=False, description="Wait for network idle (stealth/dynamic only)")
    user_agent: str | None = Field(default=None, description="Override User-Agent (http fetcher only)")


class ScrapeResponse(BaseModel):
    url: str
    status: int | None
    fetcher: FetcherName
    results: dict[str, dict[str, Any]]
    html: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "scrappling",
        "endpoints": {
            "GET /health": "liveness probe",
            "GET /llms.txt": "agent-readable discovery",
            "GET /agents.md": "agent API guide",
            "POST /scrape": "scrape a URL — see example below",
        },
        "example_request": {
            "url": "https://quotes.toscrape.com/",
            "fetcher": "http",
            "css": [".quote .text::text", ".author::text"],
        },
    }


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt() -> str:
    return LLMS_TXT


@app.get("/llms-full.txt", response_class=PlainTextResponse)
def llms_full_txt() -> str:
    return LLMS_FULL_TXT


@app.get("/agents.md", response_class=PlainTextResponse)
def agents_md() -> str:
    return AGENTS_MD


@app.get("/skill.md", response_class=PlainTextResponse)
def skill_md() -> str:
    return AGENTS_MD


@app.get("/developers.md", response_class=PlainTextResponse)
def developers_md() -> str:
    return AGENTS_MD


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest) -> ScrapeResponse:
    url = str(req.url)
    logger.info("scrape url=%s fetcher=%s css=%d xpath=%d",
                url, req.fetcher,
                len(req.css or []), len(req.xpath or []))

    try:
        page = _fetch(url, req)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — surface any fetch failure as 502
        logger.exception("fetch failed")
        raise HTTPException(status_code=502, detail={"error": str(exc), "fetcher": req.fetcher}) from exc

    results: dict[str, dict[str, Any]] = {"css": {}, "xpath": {}}

    for sel in req.css or []:
        results["css"][sel] = _eval_selector(page, sel, kind="css")
    for sel in req.xpath or []:
        results["xpath"][sel] = _eval_selector(page, sel, kind="xpath")

    return ScrapeResponse(
        url=url,
        status=getattr(page, "status", None),
        fetcher=req.fetcher,
        results=results,
        html=_safe_html(page) if req.return_html else None,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _fetch(url: str, req: ScrapeRequest):
    """Dispatch to the requested Scrapling fetcher and return the page object."""
    if req.fetcher == "http":
        from scrapling.fetchers import Fetcher  # type: ignore

        kwargs: dict[str, Any] = {"timeout": req.timeout}
        if req.user_agent:
            kwargs["headers"] = {"User-Agent": req.user_agent}
        return Fetcher.get(url, **kwargs)

    if req.fetcher == "stealth":
        from scrapling.fetchers import StealthyFetcher  # type: ignore

        return StealthyFetcher.fetch(
            url,
            headless=req.headless,
            network_idle=req.network_idle,
        )

    if req.fetcher == "dynamic":
        from scrapling.fetchers import DynamicFetcher  # type: ignore

        return DynamicFetcher.fetch(
            url,
            headless=req.headless,
            network_idle=req.network_idle,
        )

    raise HTTPException(status_code=422, detail=f"unknown fetcher: {req.fetcher}")


def _eval_selector(page, selector: str, *, kind: Literal["css", "xpath"]) -> Any:
    """Evaluate one selector and serialize results. Errors are returned in-band."""
    try:
        nodes = page.css(selector) if kind == "css" else page.xpath(selector)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{kind} selector failed: {exc}"}

    out: list[Any] = []
    # Scrapling returns an Adaptors-like list. If the selector ends in ::text or
    # is a text/attribute xpath, items are already strings. Otherwise we get
    # element wrappers — serialize text content.
    for node in nodes:
        if isinstance(node, str):
            out.append(node)
            continue
        text = getattr(node, "text", None)
        if text is None and hasattr(node, "get_all_text"):
            try:
                text = node.get_all_text(strip=True)
            except Exception:  # noqa: BLE001
                text = None
        if text is None:
            text = str(node)
        out.append(text)
    return out


def _safe_html(page) -> str | None:
    html = getattr(page, "html_content", None) or getattr(page, "body", None)
    if html is None:
        return None
    if isinstance(html, bytes):
        try:
            html = html.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return None
    # Cap returned HTML so we never echo back a 10MB page.
    MAX = 1_000_000
    if len(html) > MAX:
        return html[:MAX] + "\n<!-- truncated by scrappling -->"
    return html


# ---------------------------------------------------------------------------
# Friendly 404 / 500 JSON
# ---------------------------------------------------------------------------


@app.exception_handler(404)
async def _not_found(_, __):
    return JSONResponse(status_code=404, content={"error": "not found", "try": ["GET /health", "POST /scrape"]})
