from unittest.mock import AsyncMock, MagicMock

import pytest

from reddit_ads_mcp import tools


def make_client(**overrides):
  client = AsyncMock()
  client.resolve_account_id = MagicMock(
    side_effect=overrides.get("resolve_account_id", lambda account_id: account_id or "a2_default")
  )
  client.get.return_value = overrides.get("get_result", {"data": []})
  client.post.return_value = overrides.get("post_result", {"data": {"metrics": []}})
  client.patch.return_value = overrides.get("patch_result", {"data": {}})
  return client


async def test_list_accounts_flattens_businesses_and_ad_accounts():
  client = make_client()
  client.get.side_effect = [
    {"data": [{"id": "biz_1"}, {"id": "biz_2"}]},
    {"data": [{"id": "a2_1"}]},
    {"data": [{"id": "a2_2"}, {"id": "a2_3"}]},
  ]

  result = await tools.list_accounts(client)

  assert result == [{"id": "a2_1"}, {"id": "a2_2"}, {"id": "a2_3"}]
  client.get.assert_any_call("me/businesses")
  client.get.assert_any_call("businesses/biz_1/ad_accounts")
  client.get.assert_any_call("businesses/biz_2/ad_accounts")


async def test_list_campaigns_uses_resolved_account():
  client = make_client(get_result={"data": [{"id": "camp_1"}]})

  result = await tools.list_campaigns(client, account_id=None)

  assert result == {"data": [{"id": "camp_1"}]}
  client.get.assert_called_once_with("ad_accounts/a2_default/campaigns")


async def test_list_ad_groups_filters_by_campaign():
  client = make_client()

  await tools.list_ad_groups(client, account_id="a2_x", campaign_id="camp_1")

  client.get.assert_called_once_with("ad_accounts/a2_x/ad_groups?campaign_id=camp_1")


async def test_list_ad_groups_without_campaign_filter():
  client = make_client()

  await tools.list_ad_groups(client, account_id="a2_x", campaign_id=None)

  client.get.assert_called_once_with("ad_accounts/a2_x/ad_groups")


async def test_list_ads_filters_by_ad_group():
  client = make_client()

  await tools.list_ads(client, account_id="a2_x", ad_group_id="ag_1")

  client.get.assert_called_once_with("ad_accounts/a2_x/ads?ad_group_id=ag_1")


async def test_get_performance_report_normalizes_dates_and_defaults():
  client = make_client()

  await tools.get_performance_report(client, start_date="2026-01-01", end_date="2026-01-31")

  client.post.assert_called_once_with(
    "ad_accounts/a2_default/reports",
    {
      "data": {
        "starts_at": "2026-01-01T00:00:00Z",
        "ends_at": "2026-01-31T00:00:00Z",
        "fields": ["IMPRESSIONS", "CLICKS", "SPEND", "CTR", "CPC", "ECPM"],
        "breakdowns": ["DATE"],
      }
    },
  )


async def test_get_performance_report_accepts_custom_fields_and_breakdowns():
  client = make_client()

  await tools.get_performance_report(
    client,
    start_date="2026-01-01T12:00:00Z",
    end_date="2026-01-31",
    account_id="a2_x",
    fields=["SPEND"],
    breakdowns=["CAMPAIGN_ID"],
  )

  client.post.assert_called_once_with(
    "ad_accounts/a2_x/reports",
    {
      "data": {
        "starts_at": "2026-01-01T12:00:00Z",
        "ends_at": "2026-01-31T00:00:00Z",
        "fields": ["SPEND"],
        "breakdowns": ["CAMPAIGN_ID"],
      }
    },
  )


async def test_get_daily_performance_defaults_to_last_seven_days(monkeypatch):
  client = make_client()
  calls = {}

  async def fake_get_performance_report(
    client_, *, start_date, end_date, account_id, fields, breakdowns
  ):
    calls.update(
      start_date=start_date,
      end_date=end_date,
      account_id=account_id,
      fields=fields,
      breakdowns=breakdowns,
    )
    return {"data": {"metrics": []}}

  monkeypatch.setattr(tools, "get_performance_report", fake_get_performance_report)

  result = await tools.get_daily_performance(client, account_id="a2_x")

  assert result == {"data": {"metrics": []}}
  assert calls["account_id"] == "a2_x"
  assert calls["breakdowns"] == ["DATE", "CAMPAIGN_ID"]
  assert calls["fields"] is None


@pytest.mark.parametrize("days", [1, 7, 30])
async def test_get_daily_performance_uses_days_window(monkeypatch, days):
  from datetime import datetime, timedelta, timezone

  client = make_client()
  captured = {}

  async def fake_get_performance_report(
    client_, *, start_date, end_date, account_id, fields, breakdowns
  ):
    captured["start_date"] = start_date
    captured["end_date"] = end_date
    return {}

  monkeypatch.setattr(tools, "get_performance_report", fake_get_performance_report)

  before = datetime.now(timezone.utc)
  await tools.get_daily_performance(client, days=days)
  after = datetime.now(timezone.utc)

  expected_start_low = (before - timedelta(days=days)).strftime("%Y-%m-%d")
  expected_start_high = (after - timedelta(days=days)).strftime("%Y-%m-%d")
  assert captured["start_date"] in {expected_start_low, expected_start_high}


# -- write tools: guardrails ---------------------------------------------


async def test_create_campaign_defaults_to_paused_and_posts():
  client = make_client(post_result={"data": {"id": "camp_1"}})

  result = await tools.create_campaign(
    client,
    name="Q4 launch",
    objective="TRAFFIC",
    funding_instrument_id="fi_1",
  )

  assert result == {"data": {"id": "camp_1"}}
  client.post.assert_called_once_with(
    "ad_accounts/a2_default/campaigns",
    {
      "data": {
        "name": "Q4 launch",
        "objective": "TRAFFIC",
        "funding_instrument_id": "fi_1",
        "configured_status": "PAUSED",
      }
    },
  )


async def test_create_campaign_active_without_confirm_raises():
  client = make_client()

  with pytest.raises(tools.GuardrailError, match="confirm=True"):
    await tools.create_campaign(
      client,
      name="Q4 launch",
      objective="TRAFFIC",
      funding_instrument_id="fi_1",
      configured_status="ACTIVE",
    )

  client.post.assert_not_called()


async def test_create_campaign_active_with_confirm_posts():
  client = make_client(post_result={"data": {"id": "camp_1"}})

  result = await tools.create_campaign(
    client,
    name="Q4 launch",
    objective="TRAFFIC",
    funding_instrument_id="fi_1",
    configured_status="ACTIVE",
    confirm=True,
  )

  assert result == {"data": {"id": "camp_1"}}
  client.post.assert_called_once()


async def test_create_campaign_dry_run_skips_the_api_call():
  client = make_client()

  result = await tools.create_campaign(
    client,
    name="Q4 launch",
    objective="TRAFFIC",
    funding_instrument_id="fi_1",
    dry_run=True,
  )

  assert result["dry_run"] is True
  assert result["body"]["data"]["name"] == "Q4 launch"
  client.post.assert_not_called()


async def test_update_campaign_without_status_change_skips_guardrail():
  client = make_client(patch_result={"data": {"id": "camp_1"}})

  result = await tools.update_campaign(client, "camp_1", account_id="a2_x", name="renamed")

  assert result == {"data": {"id": "camp_1"}}
  client.patch.assert_called_once_with(
    "ad_accounts/a2_x/campaigns/camp_1", {"data": {"name": "renamed"}}
  )


async def test_update_campaign_to_active_requires_confirm():
  client = make_client()

  with pytest.raises(tools.GuardrailError, match="confirm=True"):
    await tools.update_campaign(client, "camp_1", configured_status="ACTIVE")

  client.patch.assert_not_called()


async def test_update_campaign_to_paused_does_not_require_confirm():
  client = make_client(patch_result={"data": {"id": "camp_1"}})

  await tools.update_campaign(client, "camp_1", configured_status="PAUSED")

  client.patch.assert_called_once()


async def test_create_ad_group_defaults_to_paused():
  client = make_client(post_result={"data": {"id": "ag_1"}})

  result = await tools.create_ad_group(
    client,
    campaign_id="camp_1",
    name="Group A",
    daily_budget=5000,
  )

  assert result == {"data": {"id": "ag_1"}}
  client.post.assert_called_once_with(
    "ad_accounts/a2_default/ad_groups",
    {
      "data": {
        "campaign_id": "camp_1",
        "name": "Group A",
        "daily_budget": 5000,
        "configured_status": "PAUSED",
      }
    },
  )


async def test_create_ad_group_active_without_confirm_raises():
  client = make_client()

  with pytest.raises(tools.GuardrailError, match="confirm=True"):
    await tools.create_ad_group(
      client,
      campaign_id="camp_1",
      name="Group A",
      configured_status="ACTIVE",
    )


async def test_update_ad_group_active_requires_confirm():
  client = make_client()

  with pytest.raises(tools.GuardrailError, match="confirm=True"):
    await tools.update_ad_group(client, "ag_1", configured_status="ACTIVE")

  client.patch.assert_not_called()


async def test_update_ad_group_budget_only_does_not_require_confirm():
  client = make_client(patch_result={"data": {"id": "ag_1"}})

  await tools.update_ad_group(client, "ag_1", account_id="a2_x", daily_budget=7500)

  client.patch.assert_called_once_with(
    "ad_accounts/a2_x/ad_groups/ag_1", {"data": {"daily_budget": 7500}}
  )


async def test_create_ad_defaults_to_paused():
  client = make_client(post_result={"data": {"id": "ad_1"}})

  result = await tools.create_ad(
    client,
    ad_group_id="ag_1",
    name="Ad A",
    creative_id="cr_1",
  )

  assert result == {"data": {"id": "ad_1"}}
  client.post.assert_called_once_with(
    "ad_accounts/a2_default/ads",
    {
      "data": {
        "ad_group_id": "ag_1",
        "name": "Ad A",
        "creative_id": "cr_1",
        "configured_status": "PAUSED",
      }
    },
  )


async def test_create_ad_active_without_confirm_raises():
  client = make_client()

  with pytest.raises(tools.GuardrailError, match="confirm=True"):
    await tools.create_ad(
      client,
      ad_group_id="ag_1",
      name="Ad A",
      creative_id="cr_1",
      configured_status="ACTIVE",
    )


async def test_update_ad_active_requires_confirm():
  client = make_client()

  with pytest.raises(tools.GuardrailError, match="confirm=True"):
    await tools.update_ad(client, "ad_1", configured_status="ACTIVE")

  client.patch.assert_not_called()


async def test_update_ad_name_only_does_not_require_confirm():
  client = make_client(patch_result={"data": {"id": "ad_1"}})

  await tools.update_ad(client, "ad_1", account_id="a2_x", name="renamed")

  client.patch.assert_called_once_with("ad_accounts/a2_x/ads/ad_1", {"data": {"name": "renamed"}})


async def test_create_ad_dry_run_skips_the_api_call():
  client = make_client()

  result = await tools.create_ad(
    client,
    ad_group_id="ag_1",
    name="Ad A",
    creative_id="cr_1",
    dry_run=True,
  )

  assert result["dry_run"] is True
  client.post.assert_not_called()
