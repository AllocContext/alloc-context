from __future__ import annotations

import re
import urllib.error
import urllib.request

CF_BENCHMARKS_BASE = "https://www.cfbenchmarks.com/data/indices"
_USER_AGENT = "Mozilla/5.0 (compatible; alloc-context/0.1)"
_VALUE_PATTERN = re.compile(r'"value"\s*:\s*"?([0-9.]+)')


class CFBenchmarksPriceError(RuntimeError):
    pass


def parse_index_value(html: str) -> float:
    match = _VALUE_PATTERN.search(html)
    if not match:
        raise CFBenchmarksPriceError("Could not parse CF Benchmarks index value")
    return float(match.group(1))


def fetch_index_price(index: str, *, timeout: float = 20.0) -> float:
    url = f"{CF_BENCHMARKS_BASE}/{index}"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CFBenchmarksPriceError(f"CF Benchmarks fetch failed for {index}: {exc}") from exc
    return parse_index_value(html)


def fetch_prices(indices: list[str], *, timeout: float = 20.0) -> dict[str, float]:
    out: dict[str, float] = {}
    for index in indices:
        out[index] = fetch_index_price(index, timeout=timeout)
    return out
