"""OAuth token management for the general Reddit content API (oauth.reddit.com).

Separate from `auth.py`, which authenticates against the Reddit *Ads* API.
This app is a distinct Reddit "script" app registration with `read`/`identity`
scopes — no ads account or ads scopes involved.
"""

import asyncio
import base64
import os
from datetime import datetime, timedelta, timezone

import httpx

from reddit_ads_mcp.auth import TOKEN_URL, USER_AGENT

REQUIRED_ENV_VARS = (
  "REDDIT_CONTENT_CLIENT_ID",
  "REDDIT_CONTENT_CLIENT_SECRET",
  "REDDIT_CONTENT_REFRESH_TOKEN",
)

REFRESH_BUFFER = timedelta(seconds=60)


class RedditContentAuthService:
  """Fetches and caches OAuth access tokens for the general content API."""

  def __init__(
    self,
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    http_client: httpx.AsyncClient,
  ) -> None:
    self._client_id = client_id
    self._client_secret = client_secret
    self._refresh_token = refresh_token
    self._http_client = http_client
    self._lock = asyncio.Lock()
    self._access_token: str | None = None
    self._expires_at = datetime.min.replace(tzinfo=timezone.utc)

  @classmethod
  def from_env(cls, *, http_client: httpx.AsyncClient) -> "RedditContentAuthService":
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
      raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing)}")

    return cls(
      client_id=os.environ["REDDIT_CONTENT_CLIENT_ID"],
      client_secret=os.environ["REDDIT_CONTENT_CLIENT_SECRET"],
      refresh_token=os.environ["REDDIT_CONTENT_REFRESH_TOKEN"],
      http_client=http_client,
    )

  async def get_access_token(self) -> str:
    if self._token_is_valid():
      return self._access_token  # type: ignore[return-value]

    async with self._lock:
      if self._token_is_valid():
        return self._access_token  # type: ignore[return-value]

      await self._refresh_token_now()
      return self._access_token  # type: ignore[return-value]

  def _token_is_valid(self) -> bool:
    return self._access_token is not None and datetime.now(timezone.utc) < (
      self._expires_at - REFRESH_BUFFER
    )

  async def _refresh_token_now(self) -> None:
    credentials = base64.b64encode(
      f"{self._client_id}:{self._client_secret}".encode("ascii")
    ).decode("ascii")

    response = await self._http_client.post(
      TOKEN_URL,
      headers={
        "Authorization": f"Basic {credentials}",
        "User-Agent": USER_AGENT,
      },
      data={
        "grant_type": "refresh_token",
        "refresh_token": self._refresh_token,
      },
    )
    response.raise_for_status()
    payload = response.json()

    self._access_token = payload["access_token"]
    self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload["expires_in"])
