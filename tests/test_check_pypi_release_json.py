from __future__ import annotations

from scripts.check_pypi_release_json import pypi_release_is_ready


def _payload(*, version: str = "0.2.2", urls: list[dict] | None = None) -> dict:
    if urls is None:
        urls = [
            {"packagetype": "bdist_wheel", "filename": "alloc_context-0.2.2-py3-none-any.whl"},
            {"packagetype": "sdist", "filename": "alloc_context-0.2.2.tar.gz"},
        ]
    return {
        "info": {"name": "alloc-context", "version": version},
        "urls": urls,
    }


def test_pypi_release_is_ready_accepts_wheel_and_sdist() -> None:
    ready, reason = pypi_release_is_ready(
        _payload(),
        package="alloc-context",
        version="0.2.2",
    )
    assert ready is True
    assert reason == "ok"


def test_pypi_release_is_ready_rejects_version_mismatch() -> None:
    ready, reason = pypi_release_is_ready(
        _payload(version="0.2.1"),
        package="alloc-context",
        version="0.2.2",
    )
    assert ready is False
    assert "expected '0.2.2'" in reason


def test_pypi_release_is_ready_rejects_empty_urls() -> None:
    ready, reason = pypi_release_is_ready(
        _payload(urls=[]),
        package="alloc-context",
        version="0.2.2",
    )
    assert ready is False
    assert "empty" in reason


def test_pypi_release_is_ready_rejects_missing_wheel() -> None:
    ready, reason = pypi_release_is_ready(
        _payload(urls=[{"packagetype": "sdist"}]),
        package="alloc-context",
        version="0.2.2",
    )
    assert ready is False
    assert "bdist_wheel" in reason
