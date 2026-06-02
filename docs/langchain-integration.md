# LangChain integration

Use AllocContext as **LangChain tools** against the **hosted x402 MCP** — same
endpoint as [agent-integration.md](agent-integration.md), wrapped for
`create_agent` / tool-calling chains.

**Privacy:** [USE.md](USE.md) — nothing stored · one-time read-only · pass-through only.

> **Not financial advice.** Deterministic JSON facts only.

Prerequisites: [agent-onramp.md](agent-onramp.md) Track B payer setup — fund a
Base wallet and configure via ``EVM_PRIVATE_KEY``, ``user.yaml``
(``x402.payer_private_key_file``), or inline ``x402.payer_private_key``.

## Install

```bash
pip install -e ".[hosted,dev]"
```

For a minimal example-only install:

```bash
pip install -e ".[hosted]"
pip install -r examples/langchain/requirements.txt
```

Payer config (pick one):

```bash
export EVM_PRIVATE_KEY=0x...   # payer wallet, not the seller address
```

Or bridge-style ``user.yaml`` (file key avoids exporting the key in your shell):

```yaml
# ~/.config/alloc-context/user.yaml
x402:
  payer_private_key_file: ~/.config/alloc-context/x402-payer.key
```

The example script and ``build_hosted_langchain_tools()`` load that path automatically
(override with ``ALLOC_CONTEXT_USER_CONFIG``).

## Quick invoke (no LLM)

```bash
python examples/langchain/run_example.py get_market_context
python examples/langchain/run_example.py get_rebalance_plan
```

Uses hosted-safe default args from ``smoke_tool_arguments()`` for each tool.

## Import tools in your agent

Tools are **sync** ``StructuredTool`` wrappers (``invoke`` / ``tool.invoke``).
For async agents, run in an executor or use the Docker +
``langchain-mcp-adapters`` path below.

Illustrative agent wiring (API varies by LangChain version):

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from alloccontext.integrations.langchain import build_hosted_langchain_tools

tools = build_hosted_langchain_tools()
# Default tools: get_market_context, get_context_bundle, get_rebalance_plan,
# check_allocation_band. Pass tool_names=(...) to customize.

agent = create_agent(ChatOpenAI(model="gpt-4.1-mini"), tools)
response = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Summarize BTC/ETH market context from cached facts.",
            }
        ]
    }
)
```

Each tool pays per hosted MCP pricing (**$0.02** cached context/math,
**$0.05** live or portfolio reads). See [mcp.md](mcp.md). Missing payer config
raises ``RuntimeError`` from the tool (not a silent JSON setup payload).

### Custom upstream URL or payer

```python
from alloccontext.integrations.langchain import (
    build_hosted_langchain_tools,
    resolve_hosted_user_config,
)

tools = build_hosted_langchain_tools(
    user=resolve_hosted_user_config(),
    tool_names=("get_market_context",),
)
```

Pass an explicit ``UserConfig`` when you need overrides beyond ``user.yaml``.

## Local Docker (no x402)

For free local evaluation, run `./docker/up.sh` then connect with
[langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
streamable HTTP transport:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "alloc-context": {
            "transport": "http",
            "url": "http://127.0.0.1:8000/mcp",
        }
    }
)
tools = await client.get_tools()
```

See [docker-self-host.md](docker-self-host.md). This path does not exercise
hosted x402 — use it for dev; use ``build_hosted_langchain_tools()`` for production
agents on ``https://mcp.alloc-context.com/mcp``.

## Related

- [agent-integration.md](agent-integration.md) — x402 HTTP client details
- [examples.md](examples.md) — sample tool JSON
- [mcp-discovery.md](mcp-discovery.md) — CDP Bazaar discovery
