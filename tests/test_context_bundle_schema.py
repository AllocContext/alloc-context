from __future__ import annotations

import json
from pathlib import Path

from alloccontext.mcp.instructions import PRODUCT_INSTRUCTIONS
from alloccontext.mcp.setup import upstream_payment_required
from alloccontext.mcp.upstream import call_upstream_tool
from alloccontext.user_config import UserConfig, load_user_config


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_V2 = REPO_ROOT / "schemas" / "context-bundle.v2.json"


def test_context_bundle_v2_schema_is_valid_json() -> None:
    data = json.loads(SCHEMA_V2.read_text(encoding="utf-8"))
    assert data["$id"].endswith("context-bundle.v2.json")
    assert "allocation_analysis" in data["properties"]
    assert "holdings" in data["$defs"]["portfolioBlock"]["properties"]


def test_product_instructions_mention_privacy_and_holdings() -> None:
    lowered = PRODUCT_INSTRUCTIONS.lower()
    assert "holdings" in lowered
    assert "nothing stored" in lowered
    assert "allocation_analysis" in lowered or "opt-in" in lowered


def test_path_b_hosted_only_returns_payment_setup() -> None:
    user = UserConfig.empty()
    result = call_upstream_tool(user, "get_market_context", {"scope": "daily"})
    assert result["available"] is False
    assert result["reason"] == "upstream_payment_required"


def test_path_a_bridge_user_without_payer_gets_upstream_setup(
    tmp_path: Path,
) -> None:
    path = tmp_path / "user.yaml"
    path.write_text(
        """
exchanges:
  primary: kraken
  kraken:
    api_key: test
    api_secret: dGVzdA==
""",
        encoding="utf-8",
    )
    user = load_user_config(path)
    result = call_upstream_tool(user, "get_context_bundle", {"scope": "daily"})
    assert result["reason"] == "upstream_payment_required"
    assert result["setup"]["path"] == "bridge"
