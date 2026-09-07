# reddit-ads-mcp

A Python MCP (Model Context Protocol) server for the Reddit Ads API. Provides
read-only reporting tools plus write tools for campaign/ad group/ad
management, with guardrails against accidentally spending money.

Built with Python 3.13+, [httpx](https://www.python-httpx.org/), and the
official [`mcp`](https://pypi.org/project/mcp/) Python SDK. Ported from the
C# reference implementation at
[mkerchenski/RedditAdsMcp](https://github.com/mkerchenski/RedditAdsMcp)
(read-only tools only — the write tools below have no reference to port from).

## Available tools

### Reporting (read-only)

| Tool | Description |
|------|-------------|
| `list_accounts` | List all Reddit ad accounts accessible with current credentials |
| `list_campaigns` | List campaigns for an account |
| `list_ad_groups` | List ad groups, optionally filtered by campaign |
| `list_ads` | List ads, optionally filtered by ad group |
| `get_performance_report` | Get a performance report with custom date range, fields, and breakdowns |
| `get_daily_performance` | Convenience wrapper — last N days of impressions, clicks, spend, CTR, CPC, eCPM |

All tools accept an optional `account_id` parameter. If omitted, the default
account from `REDDIT_ACCOUNT_ID` is used.

### Campaign management (write)

| Tool | Description |
|------|-------------|
| `create_campaign` | Create a campaign (name, objective, funding_instrument_id) |
| `update_campaign` | Update a campaign's name and/or status |
| `create_ad_group` | Create an ad group under a campaign, with an optional daily/lifetime budget |
| `update_ad_group` | Update an ad group's name, budget, and/or status |
| `create_ad` | Create an ad within an ad group (name, creative_id) |
| `update_ad` | Update an ad's name and/or status |

These write tools require an OAuth token authorized with the `adsedit` scope
(see [Setup](#setup) below) — a token with only `adsread` will fail.

**Spend guardrail.** Every create/update tool defaults new campaigns, ad
groups, and ads to `configured_status="PAUSED"`, and budget-only updates
never require confirmation. Setting `configured_status` to a live value
(`ACTIVE`, `ENABLED`, `RUNNING`) — on create or update — raises a
`GuardrailError` unless you also pass `confirm=True`. This means creating or
editing something paused (including setting its budget) "just works", but
making something eligible to spend money is always an explicit, separate
step.

Every write tool also accepts `dry_run=True`, which returns the HTTP
method/path/body that would be sent instead of calling the API — use it to
preview a change before committing to it.

## Prerequisites

1. A Reddit account with an active [Reddit Ads](https://ads.reddit.com) advertiser account
2. Python 3.13+ and [uv](https://docs.astral.sh/uv/)

## Setup

### 1. Install

```bash
git clone git@github.com:neilmillard/redditAdsMPC.git
cd redditAdsMPC
uv sync
```

### 2. Create a Reddit Ads API app

1. Go to [ads.reddit.com](https://ads.reddit.com)
2. In the left sidebar, click **Developer Applications** (under your account/business settings)
3. Click **Create a new app** and fill in:

| Field | Value |
|-------|-------|
| **App name** | `Reddit Ads MCP` |
| **Description** | `MCP server for Reddit Ads reporting` |
| **About url** | leave blank or link to your fork |
| **Redirect URI** | any HTTPS URL you control (Reddit rejects `localhost`) |

4. Click **Create app**
5. Copy your **App ID** and **Secret** — the onboarding helper below asks for both

### 3. Run the onboarding helper

```bash
uv run reddit-ads-mcp-init
```

This walks you through the rest in one guided command:

- asks for the OAuth scope(s) to request (space or comma separated), defaulting to `adsread`
  (read-only reporting) if you just press enter — pass e.g. `adsread, adsedit` if you also need
  write access
- prints the authorize URL to open in your browser — after you click **Allow**, Reddit redirects
  your browser to a URL like `https://your-redirect-uri/?state=mcp&code=830775384-AbCdEf...`
  (Reddit often tacks a stray `#_` onto the end — that's not part of the code, ignore it); paste
  that whole URL back (or just the `code=` value if you'd rather copy less) — the helper parses
  either and strips the `#_` for you
- exchanges that code for a permanent refresh token
- discovers your ad account(s) automatically, prompting you to pick if you have more than one
- prints a ready-to-paste `.env` block and an MCP client config snippet with every value filled in

No more hand-building the authorize URL, no `curl` for the token exchange, no digging through the
Reddit Ads UI for your account ID.

Paste the printed MCP config block into your MCP client config (e.g. `.mcp.json`):

```json
"reddit-ads": {
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--project", "/path/to/redditAdsMPC", "reddit-ads-mcp"],
  "env": {
    "REDDIT_CLIENT_ID": "your_app_id",
    "REDDIT_CLIENT_SECRET": "your_secret",
    "REDDIT_REFRESH_TOKEN": "your_refresh_token",
    "REDDIT_ACCOUNT_ID": "your_account_id"
  }
}
```

Verify with your client's MCP inspector — the `reddit-ads` server should appear with 12 tools.

<details>
<summary>Doing it manually (if you'd rather not run the helper)</summary>

Open this URL in your browser, replacing `YOUR_APP_ID` and `YOUR_REDIRECT_URI`:

```
https://www.reddit.com/api/v1/authorize?client_id=YOUR_APP_ID&response_type=code&state=mcp&redirect_uri=YOUR_REDIRECT_URI&duration=permanent&scope=adsread
```

Click **Allow** — Reddit redirects to your redirect URI with a `code` query parameter.

```bash
curl -X POST https://www.reddit.com/api/v1/access_token \
  -u "YOUR_APP_ID:YOUR_SECRET" \
  -A "reddit-ads-mcp-python/1.0" \
  -d "grant_type=authorization_code&code=YOUR_AUTHORIZATION_CODE&redirect_uri=YOUR_REDIRECT_URI"
```

The response JSON contains a `refresh_token` field — it's permanent until revoked. `redirect_uri`
must match exactly what you entered when creating the app.

Find your account ID at [ads.reddit.com](https://ads.reddit.com) → **All accounts** (top-left
dropdown) → select your business → the ID is under the account name (e.g. `a2_eaf73mplhhps`).

</details>

## Development

```bash
uv sync                 # install deps (including dev group)
uv run pytest           # run tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run reddit-ads-mcp   # start the MCP server on stdio
uv run reddit-ads-mcp-init  # guided onboarding (authorize, get refresh token, find account ID)
```

## License

MIT
