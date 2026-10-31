from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import os

DEFAULT_USER_AGENT = os.environ.get(
    "DATA_FETCHER_USER_AGENT",
    "SesameKiller-CompassBot/0.1 (+https://github.com/SesameKiller113/SesameKiller-Compass)",
)


@dataclass(frozen=True)
class FetchTextResult:
    status: int
    final_url: str
    content_type: str | None
    body: str


class FetchHttpError(Exception):
    def __init__(self, url: str, status: int, body: str):
        preview = body[:180]
        super().__init__(f"GET/POST {url} failed with HTTP {status}: {preview}")
        self.url = url
        self.status = status
        self.body_preview = body[:500]


def fetch_text(
    url: str,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    method: str = "GET",
    data: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: float = 30,
) -> FetchTextResult:
    request_headers = {
        "User-Agent": user_agent,
        "Accept": "text/plain, text/csv, text/html, application/json;q=0.9, */*;q=0.5",
    }
    if headers:
        request_headers.update(headers)

    request = Request(url, data=data, headers=request_headers, method=method)

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read()
            content_type = response.headers.get("content-type")
            charset = response.headers.get_content_charset() or "utf-8"
            return FetchTextResult(
                status=response.status,
                final_url=response.geturl(),
                content_type=content_type,
                body=raw_body.decode(charset, errors="replace"),
            )
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise FetchHttpError(url, error.code, body) from error
    except URLError as error:
        raise RuntimeError(f"GET/POST {url} failed: {error.reason}") from error
