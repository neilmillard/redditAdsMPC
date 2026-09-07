"""Thin authenticated HTTP client for the Reddit Ads API (v3)."""

from typing import Any

import httpx

from reddit_ads_mcp.auth import USER_AGENT, RedditAuthService

BASE_URL = "https://ads-api.reddit.com/api/v3/"


class RedditApiError(RuntimeError):
  """Raised when the Reddit Ads API returns a non-2xx response."""


class RedditAdsClient:
  """Authenticated JSON client for the Reddit Ads API."""

  def __init__(self, *, auth: RedditAuthService, http_client: httpx.AsyncClient) -> None:
    self._auth = auth
    self._http_client = http_client

  def resolve_account_id(self, account_id: str | None) -> str:
    return account_id or self._auth.default_account_id

  async def get(self, path: str) -> dict[str, Any]:
    response = await self._request("GET", path)
    return response.json()

  async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await self._request("POST", path, json=body)
    return response.json()

  async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
    token = await self._auth.get_access_token()
    headers = {
      "Authorization": f"Bearer {token}",
      "User-Agent": USER_AGENT,
    }

    response = await self._http_client.request(
      method, f"{BASE_URL}{path}", headers=headers, **kwargs
    )
    if response.is_error:
      raise RedditApiError(f"Reddit API returned {response.status_code}: {response.text}")

    return response
