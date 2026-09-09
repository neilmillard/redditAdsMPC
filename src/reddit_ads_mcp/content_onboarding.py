"""Interactive setup helper for the second Reddit app: general content read access.

Distinct from `onboarding.py` (Ads API). This app needs only `read`/`identity`
scopes against the standard Reddit OAuth endpoints — no ads account involved.
"""

import asyncio
import json
import os
import sys

import httpx

from reddit_ads_mcp.onboarding import OnboardingError, exchange_code_for_token, extract_code

AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
DEFAULT_SCOPE = "read identity history"


def normalize_scope(raw: str) -> str:
  """Turn user-typed scopes (comma or space separated, extra whitespace) into
  Reddit's expected space-separated scope string. Blank input defaults to
  `read identity`."""
  scopes = raw.replace(",", " ").split()
  return " ".join(scopes) if scopes else DEFAULT_SCOPE


def build_authorize_url(*, client_id: str, redirect_uri: str, scope: str = DEFAULT_SCOPE) -> str:
  from urllib.parse import urlencode

  params = {
    "client_id": client_id,
    "response_type": "code",
    "state": "mcp",
    "redirect_uri": redirect_uri,
    "duration": "permanent",
    "scope": scope,
  }
  return f"{AUTHORIZE_URL}?{urlencode(params)}"


def render_env_block(*, client_id: str, client_secret: str, refresh_token: str) -> str:
  return "\n".join(
    [
      f"REDDIT_CONTENT_CLIENT_ID={client_id}",
      f"REDDIT_CONTENT_CLIENT_SECRET={client_secret}",
      f"REDDIT_CONTENT_REFRESH_TOKEN={refresh_token}",
    ]
  )


def render_mcp_config(
  *, project_path: str, client_id: str, client_secret: str, refresh_token: str
) -> str:
  config = {
    "reddit-content": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--project", project_path, "reddit-ads-mcp"],
      "env": {
        "REDDIT_CONTENT_CLIENT_ID": client_id,
        "REDDIT_CONTENT_CLIENT_SECRET": client_secret,
        "REDDIT_CONTENT_REFRESH_TOKEN": refresh_token,
      },
    }
  }
  return json.dumps(config, indent=2)


async def _run(*, project_path: str) -> None:
  print("Reddit content MCP onboarding\n")

  client_id = input("Reddit app ID (script/installed app): ").strip()
  client_secret = input("Reddit app secret: ").strip()
  redirect_uri = input("Redirect URI (the HTTPS URL configured on the app): ").strip()
  scope = normalize_scope(
    input(f"OAuth scopes, space or comma separated [{DEFAULT_SCOPE}]: ").strip()
  )

  print(
    f"\nOpen this URL, click Allow, then paste the code (or the whole redirected URL) back here:\n"
    f"{build_authorize_url(client_id=client_id, redirect_uri=redirect_uri, scope=scope)}\n"
  )
  code = extract_code(input("Authorization code (or redirect URL): "))

  async with httpx.AsyncClient() as http_client:
    print("\nExchanging code for a refresh token...")
    token = await exchange_code_for_token(
      client_id=client_id,
      client_secret=client_secret,
      code=code,
      redirect_uri=redirect_uri,
      http_client=http_client,
    )
    refresh_token = token["refresh_token"]

  print("\nSetup complete. Env vars:\n")
  print(
    render_env_block(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)
  )
  print("\nMCP client config:\n")
  print(
    render_mcp_config(
      project_path=project_path,
      client_id=client_id,
      client_secret=client_secret,
      refresh_token=refresh_token,
    )
  )


def main() -> None:
  try:
    asyncio.run(_run(project_path=os.getcwd()))
  except OnboardingError as error:
    print(f"\nSetup failed: {error}", file=sys.stderr)
    raise SystemExit(1) from error


if __name__ == "__main__":
  main()
