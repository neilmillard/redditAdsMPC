# reddit-ads-mcp

A Python MCP (Model Context Protocol) server for the Reddit Ads API. Provides
read-only tools for listing accounts, campaigns, ad groups, ads, and pulling
performance reports.

Built with Python 3.13+, [httpx](https://www.python-httpx.org/), and the
official [`mcp`](https://pypi.org/project/mcp/) Python SDK. Ported from the
C# reference implementation at
[mkerchenski/RedditAdsMcp](https://github.com/mkerchenski/RedditAdsMcp).

## Available tools

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

## Prerequisites

1. A Reddit account with an active [Reddit Ads](https://ads.reddit.com) advertiser account
2. Python 3.13+ and [uv](https://docs.astral.sh/uv/)

## Setup

### 1. Create a Reddit Ads API app

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
5. Copy your **App ID** and **Secret** — you'll need both below

### 2. Authorize the app

Open this URL in your browser, replacing `YOUR_APP_ID` and `YOUR_REDIRECT_URI`:

```
https://www.reddit.com/api/v1/authorize?client_id=YOUR_APP_ID&response_type=code&state=mcp&redirect_uri=YOUR_REDIRECT_URI&duration=permanent&scope=adsread
```

Click **Allow**. Reddit redirects to your redirect URI with a `code` query parameter — copy it.

### 3. Exchange the code for a refresh token

```bash
curl -X POST https://www.reddit.com/api/v1/access_token \
  -u "YOUR_APP_ID:YOUR_SECRET" \
  -A "reddit-ads-mcp-python/1.0" \
  -d "grant_type=authorization_code&code=YOUR_AUTHORIZATION_CODE&redirect_uri=YOUR_REDIRECT_URI"
```

> `redirect_uri` must match exactly what you entered in Step 1.

The response JSON contains a `refresh_token` field — it's permanent until revoked.

### 4. Find your account ID

1. Go to [ads.reddit.com](https://ads.reddit.com) and click **All accounts** (top-left dropdown)
2. Select your business — your ad account appears on the right
3. The account ID is the value under the account name (e.g. `a2_eaf73mplhhps`)

### 5. Install and configure

```bash
git clone git@github.com:neilmillard/redditAdsMPC.git
cd redditAdsMPC
uv sync
```

Add to your MCP client config (e.g. `.mcp.json`), replacing the four placeholder values:

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

Verify with your client's MCP inspector — the `reddit-ads` server should appear with 6 tools.

## Development

```bash
uv sync                 # install deps (including dev group)
uv run pytest           # run tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run reddit-ads-mcp   # start the MCP server on stdio
```

## License

MIT
