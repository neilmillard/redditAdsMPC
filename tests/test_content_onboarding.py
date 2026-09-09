import json

import httpx
import respx

from reddit_ads_mcp import content_onboarding

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def test_build_authorize_url_includes_client_id_and_redirect_uri():
  url = content_onboarding.build_authorize_url(
    client_id="cid", redirect_uri="https://example.com/callback"
  )

  assert url.startswith("https://www.reddit.com/api/v1/authorize?")
  assert "client_id=cid" in url
  assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in url
  assert "duration=permanent" in url


def test_build_authorize_url_defaults_scope_to_read_identity():
  url = content_onboarding.build_authorize_url(
    client_id="cid", redirect_uri="https://example.com/callback"
  )

  assert "scope=read+identity" in url


def test_normalize_scope_defaults_when_blank():
  assert content_onboarding.normalize_scope("") == "read identity history"
  assert content_onboarding.normalize_scope("   ") == "read identity history"


def test_normalize_scope_joins_comma_separated_scopes():
  assert content_onboarding.normalize_scope("read, identity") == "read identity"


def test_render_env_block_contains_content_specific_variables():
  block = content_onboarding.render_env_block(
    client_id="cid", client_secret="secret", refresh_token="rtok"
  )

  assert "REDDIT_CONTENT_CLIENT_ID=cid" in block
  assert "REDDIT_CONTENT_CLIENT_SECRET=secret" in block
  assert "REDDIT_CONTENT_REFRESH_TOKEN=rtok" in block


def test_render_mcp_config_is_valid_json_with_expected_shape():
  config = content_onboarding.render_mcp_config(
    project_path="/path/to/redditAdsMPC",
    client_id="cid",
    client_secret="secret",
    refresh_token="rtok",
  )
  parsed = json.loads(config)

  assert parsed["reddit-content"]["command"] == "uv"
  assert parsed["reddit-content"]["env"] == {
    "REDDIT_CONTENT_CLIENT_ID": "cid",
    "REDDIT_CONTENT_CLIENT_SECRET": "secret",
    "REDDIT_CONTENT_REFRESH_TOKEN": "rtok",
  }


@respx.mock
async def test_reuses_shared_exchange_code_for_token():
  respx.post(TOKEN_URL).mock(
    return_value=httpx.Response(
      200, json={"access_token": "tok-1", "refresh_token": "rtok-1", "expires_in": 3600}
    )
  )

  async with httpx.AsyncClient() as http_client:
    result = await content_onboarding.exchange_code_for_token(
      client_id="cid",
      client_secret="secret",
      code="auth-code",
      redirect_uri="https://example.com/callback",
      http_client=http_client,
    )

  assert result["refresh_token"] == "rtok-1"


def test_extract_code_is_reused_from_shared_onboarding():
  raw = "https://example.com/callback?state=mcp&code=abc-123"
  assert content_onboarding.extract_code(raw) == "abc-123"
