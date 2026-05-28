"""HTTP retry classification for exchange API clients."""

from __future__ import annotations

import json

import requests

TRANSIENT_HTTP_STATUSES = frozenset({429, 502, 503, 504})


def is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUSES


def is_retryable_exchange_request_error(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return is_transient_http_status(exc.response.status_code)
    return False


def should_retry_exchange_attempt(exc: Exception) -> bool:
    """Return True only for transient transport/HTTP errors worth retrying."""
    if isinstance(exc, (json.JSONDecodeError, ValueError, TypeError, KeyError)):
        return False
    return is_retryable_exchange_request_error(exc)
