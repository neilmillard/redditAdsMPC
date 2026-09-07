import httpx
import pytest
import respx

from reddit_ads_mcp import onboarding

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def test_build_authorize_url_includes_client_id_and_redirect_uri():
  url = onboarding.build_authorize_url(client_id="cid", redirect_uri="https://example.com/callback")

  assert url.startswith("https://www.reddit.com/api/v1/authorize?")
  assert "client_id=cid" in url
  assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in url
  assert "duration=permanent" in url
  assert "scope=adsread" in url


@respx.mock
async def test_exchange_code_for_token_posts_authorization_code_grant():
  route = respx.post(TOKEN_URL).mock(
    return_value=httpx.Response(
      200, json={"access_token": "tok-1", "refresh_token": "rtok-1", "expires_in": 3600}
    )
  )

  async with httpx.AsyncClient() as http_client:
    result = await onboarding.exchange_code_for_token(
      client_id="cid",
      client_secret="secret",
      code="auth-code",
      redirect_uri="https://example.com/callback",
      http_client=http_client,
    )

  assert result == {"access_token": "tok-1", "refresh_token": "rtok-1", "expires_in": 3600}
  request = route.calls.last.request
  assert request.headers["authorization"].startswith("Basic ")
  body = request.content.decode()
  assert "grant_type=authorization_code" in body
  assert "code=auth-code" in body
  assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in body


@respx.mock
async def test_exchange_code_for_token_raises_on_error_response():
  respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))

  async with httpx.AsyncClient() as http_client:
    with pytest.raises(onboarding.OnboardingError, match="invalid_grant"):
      await onboarding.exchange_code_for_token(
        client_id="cid",
        client_secret="secret",
        code="bad-code",
        redirect_uri="https://example.com/callback",
        http_client=http_client,
      )


@respx.mock
async def test_discover_accounts_flattens_businesses_and_ad_accounts():
  respx.get("https://ads-api.reddit.com/api/v3/me/businesses").mock(
    return_value=httpx.Response(200, json={"data": [{"id": "biz_1"}]})
  )
  respx.get("https://ads-api.reddit.com/api/v3/businesses/biz_1/ad_accounts").mock(
    return_value=httpx.Response(
      200, json={"data": [{"id": "a2_1", "name": "Acme"}, {"id": "a2_2", "name": "Acme EU"}]}
    )
  )

  async with httpx.AsyncClient() as http_client:
    accounts = await onboarding.discover_accounts(access_token="tok-1", http_client=http_client)

  assert accounts == [
    {"id": "a2_1", "name": "Acme"},
    {"id": "a2_2", "name": "Acme EU"},
  ]


def test_render_env_block_contains_all_required_variables():
  block = onboarding.render_env_block(
    client_id="cid", client_secret="secret", refresh_token="rtok", account_id="a2_1"
  )

  assert "REDDIT_CLIENT_ID=cid" in block
  assert "REDDIT_CLIENT_SECRET=secret" in block
  assert "REDDIT_REFRESH_TOKEN=rtok" in block
  assert "REDDIT_ACCOUNT_ID=a2_1" in block


def test_render_mcp_config_is_valid_json_with_expected_shape():
  import json

  config = onboarding.render_mcp_config(
    project_path="/path/to/redditAdsMPC",
    client_id="cid",
    client_secret="secret",
    refresh_token="rtok",
    account_id="a2_1",
  )
  parsed = json.loads(config)

  assert parsed["reddit-ads"]["command"] == "uv"
  assert parsed["reddit-ads"]["args"] == [
    "run",
    "--project",
    "/path/to/redditAdsMPC",
    "reddit-ads-mcp",
  ]
  assert parsed["reddit-ads"]["env"] == {
    "REDDIT_CLIENT_ID": "cid",
    "REDDIT_CLIENT_SECRET": "secret",
    "REDDIT_REFRESH_TOKEN": "rtok",
    "REDDIT_ACCOUNT_ID": "a2_1",
  }
