"""Interactive setup helper: turns the manual README onboarding steps into one command.

Automates authorizing a Reddit Ads API app, exchanging the authorization code
for a permanent refresh token, discovering ad account IDs, and printing a
ready-to-use env block and MCP client config snippet.
"""

import asyncio
import json
import os
import sys
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from reddit_ads_mcp.auth import USER_AGENT
from reddit_ads_mcp.client import BASE_URL

AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


class OnboardingError(RuntimeError):
  """Raised when a setup step fails (bad credentials, expired code, etc.)."""


def extract_code(raw: str) -> str:
  """Pull the `code` out of whatever the user pastes back.

  Reddit's authorize redirect looks like
  ``https://your-redirect-uri/?state=mcp&code=830775384-AbCdEf...`` (or
  ``...&error=access_denied`` if they hit Cancel). Accept the bare code, the
  full redirect URL, or just its query string, so people don't have to know
  which part to copy.

  Reddit also has a long-standing quirk of tacking a stray ``#_`` fragment
  onto the redirect URL; that's not part of the code, so it's stripped
  before anything else.
  """
  raw = raw.strip().split("#", 1)[0].strip()
  if "=" not in raw:
    return raw

  query = urlparse(raw).query if "://" in raw else raw
  params = parse_qs(query)

  if "error" in params:
    raise OnboardingError(f"Reddit denied authorization: {params['error'][0]}")
  if "code" in params:
    return params["code"][0]

  raise OnboardingError(
    "no `code` parameter found — paste the code Reddit gave you, or the full redirect URL"
  )


def build_authorize_url(*, client_id: str, redirect_uri: str) -> str:
  params = {
    "client_id": client_id,
    "response_type": "code",
    "state": "mcp",
    "redirect_uri": redirect_uri,
    "duration": "permanent",
    "scope": "adsread",
  }
  return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(
  *,
  client_id: str,
  client_secret: str,
  code: str,
  redirect_uri: str,
  http_client: httpx.AsyncClient,
) -> dict:
  response = await http_client.post(
    TOKEN_URL,
    auth=(client_id, client_secret),
    headers={"User-Agent": USER_AGENT},
    data={
      "grant_type": "authorization_code",
      "code": code,
      "redirect_uri": redirect_uri,
    },
  )
  if response.is_error:
    detail = f"{response.status_code}: {response.text}"
    raise OnboardingError(f"Reddit token exchange failed ({detail})")

  return response.json()


async def discover_accounts(*, access_token: str, http_client: httpx.AsyncClient) -> list[dict]:
  headers = {"Authorization": f"Bearer {access_token}", "User-Agent": USER_AGENT}

  businesses_response = await http_client.get(f"{BASE_URL}me/businesses", headers=headers)
  if businesses_response.is_error:
    raise OnboardingError(
      f"Failed to list businesses ({businesses_response.status_code}): {businesses_response.text}"
    )

  accounts: list[dict] = []
  for business in businesses_response.json()["data"]:
    accounts_response = await http_client.get(
      f"{BASE_URL}businesses/{business['id']}/ad_accounts", headers=headers
    )
    if accounts_response.is_error:
      raise OnboardingError(
        f"Failed to list ad accounts ({accounts_response.status_code}): {accounts_response.text}"
      )
    accounts.extend(accounts_response.json()["data"])

  return accounts


def render_env_block(
  *, client_id: str, client_secret: str, refresh_token: str, account_id: str
) -> str:
  return "\n".join(
    [
      f"REDDIT_CLIENT_ID={client_id}",
      f"REDDIT_CLIENT_SECRET={client_secret}",
      f"REDDIT_REFRESH_TOKEN={refresh_token}",
      f"REDDIT_ACCOUNT_ID={account_id}",
    ]
  )


def render_mcp_config(
  *, project_path: str, client_id: str, client_secret: str, refresh_token: str, account_id: str
) -> str:
  config = {
    "reddit-ads": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--project", project_path, "reddit-ads-mcp"],
      "env": {
        "REDDIT_CLIENT_ID": client_id,
        "REDDIT_CLIENT_SECRET": client_secret,
        "REDDIT_REFRESH_TOKEN": refresh_token,
        "REDDIT_ACCOUNT_ID": account_id,
      },
    }
  }
  return json.dumps(config, indent=2)


async def _run(*, project_path: str) -> None:
  print("Reddit Ads MCP onboarding\n")

  client_id = input("Reddit Ads app ID: ").strip()
  client_secret = input("Reddit Ads app secret: ").strip()
  redirect_uri = input("Redirect URI (the HTTPS URL configured on the app): ").strip()

  print(
    f"\nOpen this URL, click Allow, then paste the code (or the whole redirected URL) back here:\n"
    f"{build_authorize_url(client_id=client_id, redirect_uri=redirect_uri)}\n"
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

    print("Discovering ad accounts...")
    accounts = await discover_accounts(access_token=token["access_token"], http_client=http_client)

  if not accounts:
    raise OnboardingError("No ad accounts found for this Reddit account.")

  if len(accounts) == 1:
    account_id = accounts[0]["id"]
  else:
    print("\nMultiple ad accounts found:")
    for i, account in enumerate(accounts):
      print(f"  [{i}] {account.get('name', account['id'])} ({account['id']})")
    choice = int(input("Pick an account by number: ").strip())
    account_id = accounts[choice]["id"]

  print("\nSetup complete. Env vars:\n")
  print(
    render_env_block(
      client_id=client_id,
      client_secret=client_secret,
      refresh_token=refresh_token,
      account_id=account_id,
    )
  )
  print("\nMCP client config:\n")
  print(
    render_mcp_config(
      project_path=project_path,
      client_id=client_id,
      client_secret=client_secret,
      refresh_token=refresh_token,
      account_id=account_id,
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
