from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from reddit_ads_mcp.client import RedditAdsClient, RedditApiError


def make_auth(token: str = "tok-1", default_account_id: str = "a2_default"):
  auth = AsyncMock()
  auth.get_access_token.return_value = token
  auth.default_account_id = default_account_id
  return auth


def test_resolve_account_id_uses_default_when_omitted():
  auth = make_auth(default_account_id="a2_default")
  client = RedditAdsClient(auth=auth, http_client=httpx.AsyncClient())

  assert client.resolve_account_id(None) == "a2_default"
  assert client.resolve_account_id("a2_other") == "a2_other"


@respx.mock
async def test_get_sends_bearer_token_and_returns_json():
  respx.get("https://ads-api.reddit.com/api/v3/me/businesses").mock(
    return_value=httpx.Response(200, json={"data": [{"id": "biz_1"}]})
  )

  async with httpx.AsyncClient() as http_client:
    client = RedditAdsClient(auth=make_auth(token="tok-xyz"), http_client=http_client)
    result = await client.get("me/businesses")

  assert result == {"data": [{"id": "biz_1"}]}
  request = respx.calls.last.request
  assert request.headers["authorization"] == "Bearer tok-xyz"


@respx.mock
async def test_post_sends_json_body():
  route = respx.post("https://ads-api.reddit.com/api/v3/ad_accounts/a2_default/reports").mock(
    return_value=httpx.Response(200, json={"data": {"metrics": []}})
  )

  async with httpx.AsyncClient() as http_client:
    client = RedditAdsClient(auth=make_auth(), http_client=http_client)
    result = await client.post("ad_accounts/a2_default/reports", {"data": {"fields": ["SPEND"]}})

  assert result == {"data": {"metrics": []}}
  assert route.calls.last.request.headers["content-type"] == "application/json"


@respx.mock
async def test_patch_sends_json_body():
  route = respx.patch(
    "https://ads-api.reddit.com/api/v3/ad_accounts/a2_default/campaigns/camp_1"
  ).mock(return_value=httpx.Response(200, json={"data": {"id": "camp_1"}}))

  async with httpx.AsyncClient() as http_client:
    client = RedditAdsClient(auth=make_auth(), http_client=http_client)
    result = await client.patch(
      "ad_accounts/a2_default/campaigns/camp_1", {"data": {"name": "new name"}}
    )

  assert result == {"data": {"id": "camp_1"}}
  assert route.calls.last.request.headers["content-type"] == "application/json"


@respx.mock
async def test_error_response_raises_reddit_api_error():
  respx.get("https://ads-api.reddit.com/api/v3/ad_accounts/bad/campaigns").mock(
    return_value=httpx.Response(403, text="forbidden")
  )

  async with httpx.AsyncClient() as http_client:
    client = RedditAdsClient(auth=make_auth(), http_client=http_client)

    with pytest.raises(RedditApiError, match="403"):
      await client.get("ad_accounts/bad/campaigns")
