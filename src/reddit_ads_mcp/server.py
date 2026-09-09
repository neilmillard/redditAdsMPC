"""MCP server exposing Reddit Ads API reporting and campaign-management tools over stdio."""

import logging
import sys

import httpx
from mcp.server.mcpserver import MCPServer

from reddit_ads_mcp import content_tools, tools
from reddit_ads_mcp.auth import USER_AGENT, RedditAuthService
from reddit_ads_mcp.client import RedditAdsClient
from reddit_ads_mcp.content_auth import RedditContentAuthService
from reddit_ads_mcp.content_client import RedditContentClient

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = MCPServer("reddit-ads")


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


def build_content_client() -> RedditContentClient:
  http_client = httpx.AsyncClient()
  http_client.headers["User-Agent"] = USER_AGENT
  auth = RedditContentAuthService.from_env(http_client=http_client)
  return RedditContentClient(auth=auth, http_client=http_client)


_content_client: RedditContentClient | None = None


def get_content_client() -> RedditContentClient:
  global _content_client
  if _content_client is None:
    _content_client = build_content_client()
  return _content_client


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


@mcp.tool()
async def create_campaign(
  name: str,
  objective: str,
  funding_instrument_id: str,
  account_id: str | None = None,
  configured_status: str = "PAUSED",
  confirm: bool = False,
  dry_run: bool = False,
) -> dict:
  """Create a Reddit Ads campaign.

  Defaults to configured_status="PAUSED" so the campaign is created inert.
  Passing a live status (e.g. "ACTIVE") without confirm=True raises a
  GuardrailError instead of calling the API — pass confirm=True once you've
  reviewed the details. Set dry_run=True to preview the request body without
  sending it.
  """
  return await tools.create_campaign(
    get_client(),
    name=name,
    objective=objective,
    funding_instrument_id=funding_instrument_id,
    account_id=account_id,
    configured_status=configured_status,
    confirm=confirm,
    dry_run=dry_run,
  )


@mcp.tool()
async def update_campaign(
  campaign_id: str,
  account_id: str | None = None,
  name: str | None = None,
  configured_status: str | None = None,
  confirm: bool = False,
  dry_run: bool = False,
) -> dict:
  """Update a Reddit Ads campaign.

  Changing configured_status to a live status (e.g. "ACTIVE") without
  confirm=True raises a GuardrailError instead of calling the API.
  """
  fields = {
    k: v for k, v in {"name": name, "configured_status": configured_status}.items() if v is not None
  }
  return await tools.update_campaign(
    get_client(), campaign_id, account_id=account_id, confirm=confirm, dry_run=dry_run, **fields
  )


@mcp.tool()
async def create_ad_group(
  campaign_id: str,
  name: str,
  account_id: str | None = None,
  daily_budget: int | None = None,
  lifetime_budget: int | None = None,
  configured_status: str = "PAUSED",
  confirm: bool = False,
  dry_run: bool = False,
) -> dict:
  """Create a Reddit Ads ad group under a campaign.

  Budgets are in the account's currency micros. Defaults to
  configured_status="PAUSED"; a live status without confirm=True raises a
  GuardrailError.
  """
  extra = {
    k: v
    for k, v in {"daily_budget": daily_budget, "lifetime_budget": lifetime_budget}.items()
    if v is not None
  }
  return await tools.create_ad_group(
    get_client(),
    campaign_id=campaign_id,
    name=name,
    account_id=account_id,
    configured_status=configured_status,
    confirm=confirm,
    dry_run=dry_run,
    **extra,
  )


@mcp.tool()
async def update_ad_group(
  ad_group_id: str,
  account_id: str | None = None,
  name: str | None = None,
  daily_budget: int | None = None,
  lifetime_budget: int | None = None,
  configured_status: str | None = None,
  confirm: bool = False,
  dry_run: bool = False,
) -> dict:
  """Update a Reddit Ads ad group.

  Changing configured_status to a live status (e.g. "ACTIVE") without
  confirm=True raises a GuardrailError instead of calling the API.
  """
  fields = {
    k: v
    for k, v in {
      "name": name,
      "daily_budget": daily_budget,
      "lifetime_budget": lifetime_budget,
      "configured_status": configured_status,
    }.items()
    if v is not None
  }
  return await tools.update_ad_group(
    get_client(), ad_group_id, account_id=account_id, confirm=confirm, dry_run=dry_run, **fields
  )


@mcp.tool()
async def create_ad(
  ad_group_id: str,
  name: str,
  creative_id: str,
  account_id: str | None = None,
  configured_status: str = "PAUSED",
  confirm: bool = False,
  dry_run: bool = False,
) -> dict:
  """Create a Reddit Ads ad within an ad group.

  Defaults to configured_status="PAUSED"; a live status without confirm=True
  raises a GuardrailError.
  """
  return await tools.create_ad(
    get_client(),
    ad_group_id=ad_group_id,
    name=name,
    creative_id=creative_id,
    account_id=account_id,
    configured_status=configured_status,
    confirm=confirm,
    dry_run=dry_run,
  )


@mcp.tool()
async def update_ad(
  ad_id: str,
  account_id: str | None = None,
  name: str | None = None,
  configured_status: str | None = None,
  confirm: bool = False,
  dry_run: bool = False,
) -> dict:
  """Update a Reddit Ads ad.

  Changing configured_status to a live status (e.g. "ACTIVE") without
  confirm=True raises a GuardrailError instead of calling the API.
  """
  fields = {
    k: v for k, v in {"name": name, "configured_status": configured_status}.items() if v is not None
  }
  return await tools.update_ad(
    get_client(), ad_id, account_id=account_id, confirm=confirm, dry_run=dry_run, **fields
  )


@mcp.tool()
async def browse_subreddit(
  subreddit: str,
  sort: str = "hot",
  time: str | None = None,
  limit: int = 25,
) -> list[dict]:
  """Browse posts in a subreddit (general Reddit content, read-only).

  subreddit is the name without "r/" (e.g. "technology"), or "all"/"popular".
  sort is one of hot, new, top, rising, controversial. time (hour/day/week/
  month/year/all) only applies to top/controversial sorts.
  """
  return await content_tools.browse_subreddit(
    get_content_client(), subreddit, sort=sort, time=time, limit=limit
  )


@mcp.tool()
async def search_reddit(
  query: str,
  subreddits: list[str] | None = None,
  sort: str = "relevance",
  time: str = "all",
  limit: int = 25,
) -> list[dict]:
  """Search posts across Reddit or within specific subreddits (max 10).

  sort is one of relevance, hot, top, new, comments.
  """
  return await content_tools.search_reddit(
    get_content_client(), query, subreddits=subreddits, sort=sort, time=time, limit=limit
  )


@mcp.tool()
async def get_post_details(
  post_id: str | None = None,
  url: str | None = None,
  subreddit: str | None = None,
  comment_limit: int = 20,
  comment_sort: str = "best",
) -> dict:
  """Fetch a Reddit post with its top-level comments.

  Provide either post_id or url. Passing subreddit alongside post_id saves an
  extra lookup. comment_sort is one of best, top, new, controversial, qa.
  """
  return await content_tools.get_post_details(
    get_content_client(),
    post_id=post_id,
    url=url,
    subreddit=subreddit,
    comment_limit=comment_limit,
    comment_sort=comment_sort,
  )


@mcp.tool()
async def user_analysis(
  username: str,
  posts_limit: int = 10,
  comments_limit: int = 10,
  time_range: str = "month",
  top_subreddits_limit: int = 10,
) -> dict:
  """Analyze a Reddit user's recent posting/commenting activity and karma.

  username is without the "u/" prefix. time_range is one of day, week, month,
  year, all.
  """
  return await content_tools.user_analysis(
    get_content_client(),
    username,
    posts_limit=posts_limit,
    comments_limit=comments_limit,
    time_range=time_range,
    top_subreddits_limit=top_subreddits_limit,
  )


@mcp.tool()
def reddit_explain(term: str) -> dict:
  """Explain a Reddit term, slang word, or cultural reference (e.g. "karma", "AMA")."""
  return content_tools.reddit_explain(term)


def main() -> None:
  mcp.run(transport="stdio")


if __name__ == "__main__":
  main()
