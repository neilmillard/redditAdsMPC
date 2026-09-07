"""MCP server exposing read-only Reddit Ads API tools over stdio."""

import logging
import sys

import httpx
from mcp.server.fastmcp import FastMCP

from reddit_ads_mcp import tools
from reddit_ads_mcp.auth import USER_AGENT, RedditAuthService
from reddit_ads_mcp.client import RedditAdsClient

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP("reddit-ads")


def build_client() -> RedditAdsClient:
  http_client = httpx.AsyncClient()
  http_client.headers["User-Agent"] = USER_AGENT
  auth = RedditAuthService.from_env(http_client=http_client)
  return RedditAdsClient(auth=auth, http_client=http_client)


_client: RedditAdsClient | None = None


def get_client() -> RedditAdsClient:
  global _client
  if _client is None:
    _client = build_client()
  return _client


@mcp.tool()
async def list_accounts() -> list[dict]:
  """List all Reddit ad accounts accessible with the current credentials.

  Discovers accounts via /me/businesses and then fetches ad accounts for each business.
  """
  return await tools.list_accounts(get_client())


@mcp.tool()
async def list_campaigns(account_id: str | None = None) -> dict:
  """List campaigns for a Reddit ad account.

  If account_id is omitted, uses the default account from REDDIT_ACCOUNT_ID.
  """
  return await tools.list_campaigns(get_client(), account_id=account_id)


@mcp.tool()
async def list_ad_groups(account_id: str | None = None, campaign_id: str | None = None) -> dict:
  """List ad groups for a Reddit ad account, optionally filtered by campaign.

  If account_id is omitted, uses the default account from REDDIT_ACCOUNT_ID.
  """
  return await tools.list_ad_groups(get_client(), account_id=account_id, campaign_id=campaign_id)


@mcp.tool()
async def list_ads(account_id: str | None = None, ad_group_id: str | None = None) -> dict:
  """List ads for a Reddit ad account, optionally filtered by ad group.

  If account_id is omitted, uses the default account from REDDIT_ACCOUNT_ID.
  """
  return await tools.list_ads(get_client(), account_id=account_id, ad_group_id=ad_group_id)


@mcp.tool()
async def get_performance_report(
  start_date: str,
  end_date: str,
  account_id: str | None = None,
  fields: list[str] | None = None,
  breakdowns: list[str] | None = None,
) -> dict:
  """Get a performance report for a Reddit ad account.

  start_date/end_date are YYYY-MM-DD. Returns fields like impressions, clicks,
  spend, CTR, CPC, and eCPM broken down by the specified breakdowns.
  """
  return await tools.get_performance_report(
    get_client(),
    start_date=start_date,
    end_date=end_date,
    account_id=account_id,
    fields=fields,
    breakdowns=breakdowns,
  )


@mcp.tool()
async def get_daily_performance(account_id: str | None = None, days: int = 7) -> dict:
  """Get daily performance for the last N days (default 7).

  Convenience wrapper returning impressions, clicks, spend, CTR, CPC, and eCPM
  broken down by DATE and CAMPAIGN_ID.
  """
  return await tools.get_daily_performance(get_client(), account_id=account_id, days=days)


def main() -> None:
  mcp.run(transport="stdio")


if __name__ == "__main__":
  main()
