"""Thin authenticated HTTP client for the general Reddit content API."""

from typing import Any

import httpx

from reddit_ads_mcp.auth import USER_AGENT
from reddit_ads_mcp.content_auth import RedditContentAuthService

BASE_URL = "https://oauth.reddit.com/"


class RedditContentApiError(RuntimeError):
  """Raised when the Reddit content API returns a non-2xx response."""


class RedditContentClient:
  """Authenticated JSON client for the general (non-ads) Reddit API."""

  def __init__(self, *, auth: RedditContentAuthService, http_client: httpx.AsyncClient) -> None:
    self._auth = auth
    self._http_client = http_client

  async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
    token = await self._auth.get_access_token()
    headers = {
      "Authorization": f"Bearer {token}",
      "User-Agent": USER_AGENT,
    }

    response = await self._http_client.get(f"{BASE_URL}{path}", headers=headers, params=params)
    if response.is_error:
      raise RedditContentApiError(f"Reddit API returned {response.status_code}: {response.text}")

    return response.json()
