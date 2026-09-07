"""Tool implementations backing the MCP server, independent of the MCP SDK."""

from datetime import datetime, timedelta, timezone
from typing import Any

from reddit_ads_mcp.client import RedditAdsClient

DEFAULT_FIELDS = ["IMPRESSIONS", "CLICKS", "SPEND", "CTR", "CPC", "ECPM"]
DEFAULT_BREAKDOWNS = ["DATE"]


async def list_accounts(client: RedditAdsClient) -> list[dict[str, Any]]:
  businesses = (await client.get("me/businesses"))["data"]

  accounts: list[dict[str, Any]] = []
  for business in businesses:
    ad_accounts = await client.get(f"businesses/{business['id']}/ad_accounts")
    accounts.extend(ad_accounts["data"])

  return accounts


async def list_campaigns(client: RedditAdsClient, account_id: str | None = None) -> dict[str, Any]:
  resolved = client.resolve_account_id(account_id)
  return await client.get(f"ad_accounts/{resolved}/campaigns")


async def list_ad_groups(
  client: RedditAdsClient,
  account_id: str | None = None,
  campaign_id: str | None = None,
) -> dict[str, Any]:
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/ad_groups"
  if campaign_id is not None:
    path += f"?campaign_id={campaign_id}"

  return await client.get(path)


async def list_ads(
  client: RedditAdsClient,
  account_id: str | None = None,
  ad_group_id: str | None = None,
) -> dict[str, Any]:
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/ads"
  if ad_group_id is not None:
    path += f"?ad_group_id={ad_group_id}"

  return await client.get(path)


async def get_performance_report(
  client: RedditAdsClient,
  *,
  start_date: str,
  end_date: str,
  account_id: str | None = None,
  fields: list[str] | None = None,
  breakdowns: list[str] | None = None,
) -> dict[str, Any]:
  resolved = client.resolve_account_id(account_id)
  body = {
    "data": {
      "starts_at": _normalize_date(start_date),
      "ends_at": _normalize_date(end_date),
      "fields": fields or DEFAULT_FIELDS,
      "breakdowns": breakdowns or DEFAULT_BREAKDOWNS,
    }
  }

  return await client.post(f"ad_accounts/{resolved}/reports", body)


async def get_daily_performance(
  client: RedditAdsClient,
  account_id: str | None = None,
  days: int = 7,
) -> dict[str, Any]:
  now = datetime.now(timezone.utc)
  end_date = now.strftime("%Y-%m-%d")
  start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")

  return await get_performance_report(
    client,
    start_date=start_date,
    end_date=end_date,
    account_id=account_id,
    fields=None,
    breakdowns=["DATE", "CAMPAIGN_ID"],
  )


def _normalize_date(date: str) -> str:
  # Reddit's v3 API requires ISO 8601 datetimes; accept YYYY-MM-DD for convenience.
  return date if "T" in date else f"{date}T00:00:00Z"
