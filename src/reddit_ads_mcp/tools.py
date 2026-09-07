"""Tool implementations backing the MCP server, independent of the MCP SDK."""

from datetime import datetime, timedelta, timezone
from typing import Any

from reddit_ads_mcp.client import RedditAdsClient

DEFAULT_FIELDS = ["IMPRESSIONS", "CLICKS", "SPEND", "CTR", "CPC", "ECPM"]
DEFAULT_BREAKDOWNS = ["DATE"]

# Statuses that make a campaign/ad group/ad eligible to spend money once created
# or updated. Anything else (e.g. PAUSED) is considered additive-but-inert.
LIVE_STATUSES = {"ACTIVE", "ENABLED", "RUNNING"}


class GuardrailError(RuntimeError):
  """Raised when a write call would go live and spend money without explicit confirmation."""


def _check_confirm(*, configured_status: str | None, confirm: bool, action: str) -> None:
  if configured_status is None:
    return
  if configured_status.upper() not in LIVE_STATUSES:
    return
  if confirm:
    return

  raise GuardrailError(
    f"{action} with configured_status={configured_status!r} would make it eligible to spend "
    "money. Pass confirm=True to proceed, or omit configured_status / use 'PAUSED' to leave it "
    "inert."
  )


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


async def create_campaign(
  client: RedditAdsClient,
  *,
  name: str,
  objective: str,
  funding_instrument_id: str,
  account_id: str | None = None,
  configured_status: str = "PAUSED",
  confirm: bool = False,
  dry_run: bool = False,
  **extra_fields: Any,
) -> dict[str, Any]:
  _check_confirm(configured_status=configured_status, confirm=confirm, action="create_campaign")
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/campaigns"
  body = {
    "data": {
      "name": name,
      "objective": objective,
      "funding_instrument_id": funding_instrument_id,
      "configured_status": configured_status,
      **extra_fields,
    }
  }

  if dry_run:
    return {"dry_run": True, "method": "POST", "path": path, "body": body}
  return await client.post(path, body)


async def update_campaign(
  client: RedditAdsClient,
  campaign_id: str,
  *,
  account_id: str | None = None,
  confirm: bool = False,
  dry_run: bool = False,
  **fields: Any,
) -> dict[str, Any]:
  _check_confirm(
    configured_status=fields.get("configured_status"), confirm=confirm, action="update_campaign"
  )
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/campaigns/{campaign_id}"
  body = {"data": fields}

  if dry_run:
    return {"dry_run": True, "method": "PATCH", "path": path, "body": body}
  return await client.patch(path, body)


async def create_ad_group(
  client: RedditAdsClient,
  *,
  campaign_id: str,
  name: str,
  account_id: str | None = None,
  configured_status: str = "PAUSED",
  confirm: bool = False,
  dry_run: bool = False,
  **extra_fields: Any,
) -> dict[str, Any]:
  _check_confirm(configured_status=configured_status, confirm=confirm, action="create_ad_group")
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/ad_groups"
  body = {
    "data": {
      "campaign_id": campaign_id,
      "name": name,
      **extra_fields,
      "configured_status": configured_status,
    }
  }

  if dry_run:
    return {"dry_run": True, "method": "POST", "path": path, "body": body}
  return await client.post(path, body)


async def update_ad_group(
  client: RedditAdsClient,
  ad_group_id: str,
  *,
  account_id: str | None = None,
  confirm: bool = False,
  dry_run: bool = False,
  **fields: Any,
) -> dict[str, Any]:
  _check_confirm(
    configured_status=fields.get("configured_status"), confirm=confirm, action="update_ad_group"
  )
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/ad_groups/{ad_group_id}"
  body = {"data": fields}

  if dry_run:
    return {"dry_run": True, "method": "PATCH", "path": path, "body": body}
  return await client.patch(path, body)


async def create_ad(
  client: RedditAdsClient,
  *,
  ad_group_id: str,
  name: str,
  creative_id: str,
  account_id: str | None = None,
  configured_status: str = "PAUSED",
  confirm: bool = False,
  dry_run: bool = False,
  **extra_fields: Any,
) -> dict[str, Any]:
  _check_confirm(configured_status=configured_status, confirm=confirm, action="create_ad")
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/ads"
  body = {
    "data": {
      "ad_group_id": ad_group_id,
      "name": name,
      "creative_id": creative_id,
      **extra_fields,
      "configured_status": configured_status,
    }
  }

  if dry_run:
    return {"dry_run": True, "method": "POST", "path": path, "body": body}
  return await client.post(path, body)


async def update_ad(
  client: RedditAdsClient,
  ad_id: str,
  *,
  account_id: str | None = None,
  confirm: bool = False,
  dry_run: bool = False,
  **fields: Any,
) -> dict[str, Any]:
  _check_confirm(
    configured_status=fields.get("configured_status"), confirm=confirm, action="update_ad"
  )
  resolved = client.resolve_account_id(account_id)
  path = f"ad_accounts/{resolved}/ads/{ad_id}"
  body = {"data": fields}

  if dry_run:
    return {"dry_run": True, "method": "PATCH", "path": path, "body": body}
  return await client.patch(path, body)
