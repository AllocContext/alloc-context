from __future__ import annotations

import pytest

from alloccontext.mcp.handlers import validate_scope


def test_validate_scope_daily() -> None:
    assert validate_scope("daily") == "daily"


def test_validate_scope_weekly() -> None:
    assert validate_scope("weekly") == "weekly"


def test_validate_scope_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="scope must be"):
        validate_scope("monthly")


def test_mcp_server_import() -> None:
    pytest.importorskip("mcp")
    from alloccontext.mcp.server import create_server

    server = create_server()
    assert server.name == "alloc-context"
