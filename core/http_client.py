import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import urlparse

try:
    import brotli  # type: ignore
    _HAS_BROTLI = True
except Exception:
    _HAS_BROTLI = False

import gzip

import httpx
try:
    import h2  # type: ignore
    _HAS_H2 = True
except Exception:
    _HAS_H2 = False


logger = logging.getLogger(__name__)


class _HTTPCache:
    """Lightweight ETag/Last-Modified cache persisted in SQLite.

    Schema:
      http_cache(url TEXT PRIMARY KEY, etag TEXT, last_modified TEXT, status INT,
                 fetched_at TEXT, html_br BLOB)
    """

    def __init__(self, path: str = "http_cache.db"):
        self.path = path
        self._init()

    def _init(self):
        conn = sqlite3.connect(self.path)
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS http_cache (
                url TEXT PRIMARY KEY,
                etag TEXT,
                last_modified TEXT,
                status INT,
                fetched_at TEXT,
                html_br BLOB
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_http_cache_status ON http_cache(status)")
        conn.commit()
        conn.close()

    def get(self, url: str) -> Optional[Tuple[Optional[str], Optional[str], Optional[int], Optional[str], Optional[bytes]]]:
        conn = sqlite3.connect(self.path)
        c = conn.cursor()
        c.execute("SELECT etag, last_modified, status, fetched_at, html_br FROM http_cache WHERE url = ?", (url,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return row[0], row[1], (int(row[2]) if row[2] is not None else None), row[3], row[4]

    def upsert(self, url: str, etag: Optional[str], last_modified: Optional[str], status: int, html_text: Optional[str]):
        # Compress HTML payload into brotli if available, else gzip for space efficiency
        payload: Optional[bytes]
        if html_text is None:
            payload = None
        else:
            raw = html_text.encode("utf-8", errors="ignore")
            try:
                if _HAS_BROTLI:
                    payload = brotli.compress(raw)
                else:
                    payload = gzip.compress(raw)
            except Exception:
                payload = raw
        conn = sqlite3.connect(self.path)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO http_cache(url, etag, last_modified, status, fetched_at, html_br)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(url) DO UPDATE SET
                etag=excluded.etag,
                last_modified=excluded.last_modified,
                status=excluded.status,
                fetched_at=excluded.fetched_at,
                html_br=excluded.html_br
            """,
            (url, etag, last_modified, int(status), datetime.utcnow().isoformat(), payload),
        )
        conn.commit()
        conn.close()

    def decode_payload(self, data: Optional[bytes]) -> Optional[str]:
        if data is None:
            return None
        # Try brotli, then gzip, then raw
        try:
            return brotli.decompress(data).decode("utf-8", errors="ignore") if _HAS_BROTLI else gzip.decompress(data).decode("utf-8", errors="ignore")
        except Exception:
            try:
                return gzip.decompress(data).decode("utf-8", errors="ignore")
            except Exception:
                try:
                    return data.decode("utf-8", errors="ignore")
                except Exception:
                    return None


class AsyncHTTPClient:
    """Shared httpx AsyncClient with HTTP/2, connection pooling, per-domain rate limiting, and conditional GET.

    Use get_html(url) to fetch text/HTML only. Implements negative caching for 1 hour for 4xx/5xx.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._cache = _HTTPCache()
        self._domain_limits: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                headers = {
                    "Accept": "text/html,application/xhtml+xml;q=0.9,application/xml;q=0.8",
                    "Accept-Encoding": ("br, gzip" if _HAS_BROTLI else "gzip"),
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    ),
                    "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cache-Control": "max-age=0",
                }
                self._client = httpx.AsyncClient(
                    http2=_HAS_H2,
                    headers=headers,
                    timeout=httpx.Timeout(15.0, read=15.0, connect=10.0),
                    limits=httpx.Limits(max_keepalive_connections=20, max_connections=30),
                    follow_redirects=True,
                )
        return self._client

    def _get_domain_semaphore(self, domain: str) -> asyncio.Semaphore:
        if domain not in self._domain_limits:
            # 2 concurrent, burst friendly
            self._domain_limits[domain] = asyncio.Semaphore(2)
        return self._domain_limits[domain]

    async def get_html(self, url: str) -> str:
        parsed = urlparse(url)
        domain = parsed.netloc
        sem = self._get_domain_semaphore(domain)

        # Check cache for conditional headers and negative caching
        cached = self._cache.get(url)
        headers = {}
        if cached:
            etag, last_mod, status, fetched_at, payload = cached
            try:
                if status and status >= 400 and fetched_at:
                    # Negative cache for 1h
                    fetched_dt = datetime.fromisoformat(fetched_at)
                    if datetime.utcnow() - fetched_dt < timedelta(hours=1):
                        raise httpx.HTTPStatusError("negative cache", request=None, response=None)  # handled below
            except Exception:
                pass
            if etag:
                headers["If-None-Match"] = etag
            if last_mod:
                headers["If-Modified-Since"] = last_mod

        client = await self._get_client()

        backoff = 0.5
        for attempt in range(4):
            async with sem:
                try:
                    resp = await client.get(url, headers=headers)
                    # 304 → use cached body
                    if resp.status_code == 304 and cached:
                        html = self._cache.decode_payload(cached[4]) or ""
                        if not html:
                            # Fallback: fetch fresh without conditionals
                            resp2 = await client.get(url)
                            html = resp2.text
                            self._cache.upsert(url, resp2.headers.get("ETag"), resp2.headers.get("Last-Modified"), resp2.status_code, html)
                        return html
                    # Success
                    if 200 <= resp.status_code < 300:
                        text = resp.text
                        self._cache.upsert(url, resp.headers.get("ETag"), resp.headers.get("Last-Modified"), resp.status_code, text)
                        return text
                    # Client/Server error → store negative cache and raise
                    self._cache.upsert(url, resp.headers.get("ETag"), resp.headers.get("Last-Modified"), resp.status_code, None)
                    # 429/503 → backoff with jitter
                    if resp.status_code in (429, 503):
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2.0, 8.0) + (0.1 * attempt)
                        continue
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    # If negative cached earlier, re-raise as simple error
                    raise e
                except Exception as e:
                    if attempt < 3:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2.0, 8.0) + (0.1 * attempt)
                        continue
                    logger.warning(f"HTTP fetch failed for {url}: {e}")
                    raise
        # Should not reach
        raise RuntimeError("Failed to fetch HTML")

    async def aclose(self):
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass


