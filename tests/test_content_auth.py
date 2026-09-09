from datetime import timedelta

import httpx
import pytest
import respx

from reddit_ads_mcp.content_auth import RedditContentAuthService

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def make_service(http_client: httpx.AsyncClient) -> RedditContentAuthService:
  return RedditContentAuthService(
    client_id="cid",
    client_secret="secret",
    refresh_token="rtok",
    http_client=http_client,
  )


@respx.mock
async def test_get_access_token_fetches_and_caches():
  route = respx.post(TOKEN_URL).mock(
    return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
  )

  async with httpx.AsyncClient() as http_client:
    service = make_service(http_client)

    token1 = await service.get_access_token()
    token2 = await service.get_access_token()

  assert token1 == "tok-1"
  assert token2 == "tok-1"
  assert route.call_count == 1


@respx.mock
async def test_get_access_token_sends_basic_auth_and_refresh_grant():
  route = respx.post(TOKEN_URL).mock(
    return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
  )

  async with httpx.AsyncClient() as http_client:
    service = make_service(http_client)
    await service.get_access_token()

  request = route.calls.last.request
  assert request.headers["authorization"].startswith("Basic ")
  body = request.content.decode()
  assert "grant_type=refresh_token" in body
  assert "refresh_token=rtok" in body


@respx.mock
async def test_get_access_token_refreshes_once_expired():
  route = respx.post(TOKEN_URL).mock(
    side_effect=[
      httpx.Response(200, json={"access_token": "tok-1", "expires_in": 1}),
      httpx.Response(200, json={"access_token": "tok-2", "expires_in": 3600}),
    ]
  )

  async with httpx.AsyncClient() as http_client:
    service = make_service(http_client)
    token1 = await service.get_access_token()
    service._expires_at -= timedelta(hours=1)  # force expiry without sleeping
    token2 = await service.get_access_token()

  assert token1 == "tok-1"
  assert token2 == "tok-2"
  assert route.call_count == 2


def test_from_env_requires_all_variables(monkeypatch):
  monkeypatch.delenv("REDDIT_CONTENT_CLIENT_ID", raising=False)
  monkeypatch.delenv("REDDIT_CONTENT_CLIENT_SECRET", raising=False)
  monkeypatch.delenv("REDDIT_CONTENT_REFRESH_TOKEN", raising=False)

  with pytest.raises(RuntimeError, match="REDDIT_CONTENT_CLIENT_ID"):
    RedditContentAuthService.from_env(http_client=httpx.AsyncClient())


def test_from_env_builds_service(monkeypatch):
  monkeypatch.setenv("REDDIT_CONTENT_CLIENT_ID", "cid")
  monkeypatch.setenv("REDDIT_CONTENT_CLIENT_SECRET", "secret")
  monkeypatch.setenv("REDDIT_CONTENT_REFRESH_TOKEN", "rtok")

  service = RedditContentAuthService.from_env(http_client=httpx.AsyncClient())

  assert isinstance(service, RedditContentAuthService)
