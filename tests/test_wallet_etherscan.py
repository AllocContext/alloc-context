from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from alloccontext.ingest.wallet.etherscan import EtherscanClient, EtherscanError


def test_etherscan_native_balance_parses_wei() -> None:
    client = EtherscanClient("test-key", max_retries=0)
    payload = {"status": "1", "message": "OK", "result": "1500000000000000000"}
    with patch("alloccontext.ingest.wallet.etherscan.requests.get") as get:
        get.return_value = MagicMock(
            status_code=200,
            json=lambda: payload,
            raise_for_status=lambda: None,
        )
        assert client.native_balance_eth(1, "0xabc") == 1.5


def test_etherscan_token_balance_parses_wei() -> None:
    from alloccontext.ingest.wallet.curated_tokens import CuratedToken

    client = EtherscanClient("test-key", max_retries=0)
    token = CuratedToken("0xabc", "USDC", 6)
    payload = {"status": "1", "message": "OK", "result": "2500000"}
    with patch("alloccontext.ingest.wallet.etherscan.requests.get") as get:
        get.return_value = MagicMock(
            status_code=200,
            json=lambda: payload,
            raise_for_status=lambda: None,
        )
        assert client.token_balance(1, "0xwallet", token) == 2.5


def test_etherscan_raises_on_notok() -> None:
    client = EtherscanClient("test-key", max_retries=0)
    payload = {"status": "0", "message": "NOTOK", "result": "Invalid API Key"}
    with patch("alloccontext.ingest.wallet.etherscan.requests.get") as get:
        get.return_value = MagicMock(
            status_code=200,
            json=lambda: payload,
            raise_for_status=lambda: None,
        )
        with pytest.raises(EtherscanError, match="Invalid API Key"):
            client.native_balance_eth(1, "0xabc")
