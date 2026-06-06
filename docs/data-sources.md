# Data sources

All sources are **read-only**. Ingest normalizes to SQLite; rollup never calls
external APIs.

## Data horizon (quarterly)

All stored history uses a single **`horizon.days`** config (default **90**):
F&G rows, Kraken OHLC bars, portfolio snapshots, Kalshi snapshots, macro events,
and rollup snapshots. Ingest prunes aged rows each run. Short narrative windows
(e.g. “since yesterday”, “next 7 days” calendar) stay short; the **store** is
quarter-scoped.

## Sources

| Source | Ingest module | Refresh | Secrets |
|--------|---------------|---------|---------|
| **Kraken** portfolio + OHLC | `ingest/kraken_*.py` | hourly | `KRAKEN_API_*` |
| **Kalshi** sentiment / cluster | `ingest/kalshi.py` | hourly | API or file fallback |
| **Fear & Greed** | `ingest/fear_greed.py` | each ingest cycle | none (public API) |
| **Macro calendar** | `ingest/macro_calendar.py` | daily | none for static YAML; optional free API keys |
| **ETF flows** | `ingest/etf_flows.py` | daily | optional `SOSOVALUE_API_KEY` or JSON fallback |
| **CoinGecko** | `ingest/coingecko.py` | hourly | none (keyless); optional `COINGECKO_API_KEY` demo plan |
| **CoinMarketCap** | `ingest/coinmarketcap.py` | hourly | `COINMARKETCAP_API_KEY` (free Basic plan) |
| **FRED** macro levels | `ingest/fred.py` | daily | `FRED_API_KEY` (free) |

## Macro calendar (free APIs)

Three layers, merged with static curated events winning on duplicates:

| Layer | Cost | Key | What you get |
|-------|------|-----|--------------|
| **Static YAML** | Free, no signup | none | FOMC dates, Jackson Hole, other curated US catalysts (`config/macro-calendar.yaml`) |
| **[Finnhub](https://finnhub.io/register)** | Free plan | `FINNHUB_API_KEY` | US economic calendar (CPI, NFP, claims, etc.) with impact levels |
| **[FMP](https://site.financialmodelingprep.com/developer/docs)** | Free plan | `FMP_API_KEY` | Optional backup feed (`macro.fmp_enabled: true`) |

Without any API keys, daily rollups still list FOMC and other static events. With
Finnhub enabled, dynamic releases fill in between FOMC dates.

## FRED macro levels

Complements the **calendar** (when releases happen) with **levels** (yields,
DXY, CPI index, unemployment). Free API key from
[FRED](https://fred.stlouisfed.org/docs/api/api_key.html).

| Setting | Default | Notes |
|---------|---------|-------|
| `fred.series_catalog` | `config/fred-series.yaml` | Series IDs + labels |
| `fred.lookback_days` | `120` | Fetch window (supports 7d/30d deltas in rollup) |
| `ingest.sources.fred` | `true` | Skips gracefully when `FRED_API_KEY` unset |

Default series: `DGS10`, `DGS2`, `FEDFUNDS`, `DTWEXBGS`, `CPIAUCSL`, `UNRATE`.

Stored table: `fred_observations`. Rollup exposes `macro.indicators.{series_id}`
with latest value, observation date, and 7d/30d absolute and percent changes.

Filter knobs in config:

- `macro.countries` — default `[US]`
- `macro.min_impact` — default `medium` (drops low-impact noise like weekly claims if desired; set `low` to include everything Finnhub marks)

## Market breadth (CoinGecko + CoinMarketCap)

| Provider | Cost | Key | Endpoints used |
|----------|------|-----|----------------|
| **[CoinGecko](https://www.coingecko.com/en/api)** | Free (keyless or Demo) | optional `COINGECKO_API_KEY` | `/global`, `/coins/markets` for BTC/ETH rank, dominance, 24h change |
| **[CoinMarketCap](https://coinmarketcap.com/api/)** | Free Basic plan | `COINMARKETCAP_API_KEY` | `/global-metrics/quotes/latest`, `/cryptocurrency/quotes/latest` |

CoinGecko works without signup (IP rate limits ~5–15 calls/min keyless; ~30/min with
free Demo key). Two calls per ingest cycle fits the hourly timer.

CoinMarketCap skips gracefully when the key is unset. With both feeds, rollup
exposes `market.breadth.feeds.coingecko` and `market.breadth.feeds.coinmarketcap`
plus dominance/rank deltas vs the prior snapshot. The same optional sources also
back **alt holding quotes** (e.g. HYPE) via `ingest/alt_quotes.py` — scheduled on
the hourly ingest timer for a bounded symbol set (portfolio + recent requests),
plus on-demand refresh for `freshness=live` or cache-miss lazy fetch when keys
are present.

**Live vs cached alt quotes:** `freshness=live` with alt assets in the request
**fails closed** when no quote API keys are configured or when the refresh
returns no rows (see `live_alt_quote_refresh_failed`). `freshness=cached` uses
lazy fetch when keys exist but omits uncached alts from the response instead of
failing the whole tool call.

Stored table: `crypto_market_snapshots`.

## ETF flows

| Layer | Cost | Key | What you get |
|-------|------|-----|--------------|
| **[SoSoValue](https://openapi.sosovalue.com)** | Free demo plan | `SOSOVALUE_API_KEY` | Daily BTC/ETH spot ETF net inflows + per-ticker (IBIT, FBTC, ETHA, …) |
| **JSON fallback** | Free | none | `etf.fallback_snapshot` file (same shape as `tests/fixtures/etf_flows.json`) |

Farside Investors publishes similar tables but sits behind Cloudflare — not suitable
for headless ingest. SoSoValue is the recommended free API; use the file fallback
when offline or before you have a key.

Stored tables: `etf_flow_days`, `etf_ticker_flows`.

Rollup exposes under `macro.etf.btc` / `macro.etf.eth`:

- `net_flow_usd_1d` / `net_flow_usd_24h` (daily scope)
- `net_flow_usd_7d` (weekly scope)
- `by_ticker` — issuer breakdown for latest day

## On-chain wallet (EVM, keyless)

MCP live path only (`get_portfolio_state` with `exchange=wallet`). No scheduled
ingest and no stored wallet addresses.

| Item | Detail |
|------|--------|
| **Input** | Public EVM address (`wallet_address`); `api_key` / `api_secret` omitted |
| **Chains** | Ethereum, Arbitrum, Base, Optimism, Polygon (`wallet.chain_ids`) |
| **Provider** | `wallet.provider: alchemy` (default) or `etherscan` |
| **Upstream** | [Alchemy Portfolio API](https://www.alchemy.com/docs/reference/portfolio-apis) (`tokens/by-address`, multichain) or Etherscan v2 fallback |
| **Host env** | `ALCHEMY_API_KEY` (default) or `ETHERSCAN_API_KEY` — server-side only |
| **Etherscan fallback** | Curated tokens only; some L2 chains skipped on free explorer plans |
| **Spam / dust** | Alchemy USD marks + min value filter; top 40 symbols; fake BTC/ETH ERC-20 excluded |
| **Valuation** | Existing quote resolver (CoinGecko / CoinMarketCap when configured) |
| **Dust filter** | `wallet.min_value_usd` (default $1) drops priced dust/spam tokens |

Wrapped assets (e.g. WETH, WBTC) map to band symbols for allocation math. Fail-closed
when the host key is missing, wallet read is disabled, or the explorer errors.

## Kraken contract

Read endpoints only:

- Account balance / trade balance
- Ticker or OHLC for configured pairs
- No `AddOrder`, no withdraw

Stored tables: `portfolio_snapshots`, `market_bars`.

## Coinbase contract

Read endpoints only (Coinbase Advanced Trade / CDP JWT):

- List accounts (balances)
- Product price and candles for configured `pairs` (e.g. `BTC-USD`, `ETH-USD`)
- No order placement or withdraw

Env: `COINBASE_API_KEY` (full CDP key name) and `COINBASE_API_SECRET`
(EC private key PEM; `\n` escapes in a single-line env value are expanded
in code).

Enable with `ingest.sources.coinbase: true` and `exchanges.coinbase.enabled:
true`. Set `exchanges.primary: coinbase` when Coinbase should drive rollup
market bars.

Stored tables: same as Kraken (`portfolio_snapshots`, `market_bars`).

## Kalshi contract

Read-only sentiment telemetry for hourly Kalshi above/below markets and CF Benchmarks
spot drift. **No Kalshi API credentials required** — public `/markets` plus
CF Benchmarks index pages are enough for the default ingest path.

| Mode | Config | Notes |
|------|--------|-------|
| **API (default)** | `kalshi.use_api: true` | Polls KXBTCD/KXETHD + CF indices each ingest |
| **File fallback** | `use_api: false` + snapshot paths | Optional offline JSON snapshots |

Configure series under `kalshi.series` (default KXBTCD/KXETHD). CF price
history accumulates in SQLite meta (`cf_price_history`) for drift/cluster
rollup after a few hourly ingest cycles.

Optional `KALSHI_API_KEY` / `KALSHI_API_SECRET` are reserved for future
authenticated endpoints; sentiment ingest does not use them today.

Stored table: `kalshi_snapshots`. Meta keys: `cf_price_history`,
`kalshi_markets` (alternate meta key `kalshi_markets_15m` is also accepted).

## F&G contract

Alternative.me Crypto Fear & Greed Index — stored in `fear_greed` table.

Ingest fetches up to `horizon.days` (default **90**, quarterly). Older rows are
pruned after each ingest run.

## Macro contract

Stored table: `macro_events`.

Rollup exposes:

- Daily scope: `macro.events.past_24h`, `macro.events.next_7d`
- Weekly scope: `macro.events.past_7d`, `macro.events.next_7d`
- When FRED ingest is active: `macro.indicators` (yields, DXY, CPI level, etc.)

Stored table for FRED: `fred_observations`.

If a source fails, ingest logs error and rollup omits section with
`available: false`. Macro keeps static events when API feeds fail.

## Rate limits

- Kraken: respect public REST limits; cache OHLC between ingest cycles
- Finnhub / FMP: one calendar pull per ingest run; default daily for macro
- SoSoValue: one ETF pull per ingest run when `etf_flows` enabled
- CoinGecko: 2 calls per ingest when enabled; use Demo key if keyless throttles
- CoinMarketCap: 2 calls per ingest when key present
