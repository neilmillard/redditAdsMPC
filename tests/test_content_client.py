from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from reddit_ads_mcp.content_client import RedditContentApiError, RedditContentClient


def make_auth(token: str = "tok-1"):
  auth = AsyncMock()
  auth.get_access_token.return_value = token
  return auth


@respx.mock
async def test_get_sends_bearer_token_and_returns_json():
  respx.get("https://oauth.reddit.com/r/technology/hot").mock(
    return_value=httpx.Response(200, json={"data": {"children": []}})
  )

  async with httpx.AsyncClient() as http_client:
    client = RedditContentClient(auth=make_auth(token="tok-xyz"), http_client=http_client)
    result = await client.get("r/technology/hot")

  assert result == {"data": {"children": []}}
  request = respx.calls.last.request
  assert request.headers["authorization"] == "Bearer tok-xyz"


@respx.mock
async def test_get_forwards_params():
  route = respx.get("https://oauth.reddit.com/r/technology/hot").mock(
    return_value=httpx.Response(200, json={"data": {"children": []}})
  )

  async with httpx.AsyncClient() as http_client:
    client = RedditContentClient(auth=make_auth(), http_client=http_client)
    await client.get("r/technology/hot", params={"limit": 5})

  request = route.calls.last.request
  assert request.url.params["limit"] == "5"


@respx.mock
async def test_error_response_raises_content_api_error():
  respx.get("https://oauth.reddit.com/r/private/hot").mock(
    return_value=httpx.Response(403, text="forbidden")
  )

  async with httpx.AsyncClient() as http_client:
    client = RedditContentClient(auth=make_auth(), http_client=http_client)

    with pytest.raises(RedditContentApiError, match="403"):
      await client.get("r/private/hot")
