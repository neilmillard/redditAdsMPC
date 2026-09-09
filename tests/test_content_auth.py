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


CONTENT_ENV_VARS = (
  "REDDIT_CONTENT_CLIENT_ID",
  "REDDIT_CONTENT_CLIENT_SECRET",
  "REDDIT_CONTENT_REFRESH_TOKEN",
)

ADS_ENV_VARS = (
  "REDDIT_CLIENT_ID",
  "REDDIT_CLIENT_SECRET",
  "REDDIT_REFRESH_TOKEN",
)


def clear_env(monkeypatch):
  for name in CONTENT_ENV_VARS + ADS_ENV_VARS:
    monkeypatch.delenv(name, raising=False)


def test_from_env_requires_content_or_ads_variables(monkeypatch):
  clear_env(monkeypatch)

  with pytest.raises(RuntimeError, match="REDDIT_CONTENT_CLIENT_ID"):
    RedditContentAuthService.from_env(http_client=httpx.AsyncClient())


def test_from_env_falls_back_to_ads_credentials(monkeypatch):
  clear_env(monkeypatch)
  monkeypatch.setenv("REDDIT_CLIENT_ID", "ads-cid")
  monkeypatch.setenv("REDDIT_CLIENT_SECRET", "ads-secret")
  monkeypatch.setenv("REDDIT_REFRESH_TOKEN", "ads-rtok")

  service = RedditContentAuthService.from_env(http_client=httpx.AsyncClient())

  assert service._client_id == "ads-cid"
  assert service._client_secret == "ads-secret"
  assert service._refresh_token == "ads-rtok"


def test_from_env_prefers_content_credentials_over_ads(monkeypatch):
  clear_env(monkeypatch)
  monkeypatch.setenv("REDDIT_CLIENT_ID", "ads-cid")
  monkeypatch.setenv("REDDIT_CLIENT_SECRET", "ads-secret")
  monkeypatch.setenv("REDDIT_REFRESH_TOKEN", "ads-rtok")
  monkeypatch.setenv("REDDIT_CONTENT_CLIENT_ID", "cid")
  monkeypatch.setenv("REDDIT_CONTENT_CLIENT_SECRET", "secret")
  monkeypatch.setenv("REDDIT_CONTENT_REFRESH_TOKEN", "rtok")

  service = RedditContentAuthService.from_env(http_client=httpx.AsyncClient())

  assert service._client_id == "cid"
  assert service._refresh_token == "rtok"


def test_from_env_rejects_partial_content_variables(monkeypatch):
  clear_env(monkeypatch)
  monkeypatch.setenv("REDDIT_CONTENT_CLIENT_ID", "cid")

  with pytest.raises(RuntimeError, match="REDDIT_CONTENT_CLIENT_SECRET"):
    RedditContentAuthService.from_env(http_client=httpx.AsyncClient())


def test_from_env_builds_service(monkeypatch):
  clear_env(monkeypatch)
  monkeypatch.setenv("REDDIT_CONTENT_CLIENT_ID", "cid")
  monkeypatch.setenv("REDDIT_CONTENT_CLIENT_SECRET", "secret")
  monkeypatch.setenv("REDDIT_CONTENT_REFRESH_TOKEN", "rtok")

  service = RedditContentAuthService.from_env(http_client=httpx.AsyncClient())

  assert isinstance(service, RedditContentAuthService)
