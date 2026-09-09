"""Read-only Reddit content browsing tools, mirroring reddit-mcp-buddy.

Talks to the general Reddit API (oauth.reddit.com) via RedditContentClient —
independent of the Ads API tools in `tools.py`.
"""

import re
from typing import Any

from reddit_ads_mcp.content_client import RedditContentClient

POST_URL_RE = re.compile(r"comments/([a-z0-9]+)", re.IGNORECASE)


class UnknownTermError(RuntimeError):
  """Raised when `reddit_explain` is asked about a term it doesn't know."""


def _extract_post_id(post_id_or_url: str) -> str:
  match = POST_URL_RE.search(post_id_or_url)
  if match:
    return match.group(1)
  return post_id_or_url.removeprefix("t3_")


def _simplify_post(child: dict[str, Any]) -> dict[str, Any]:
  data = child["data"]
  return {
    "id": data.get("id"),
    "title": data.get("title"),
    "author": data.get("author"),
    "subreddit": data.get("subreddit"),
    "score": data.get("score"),
    "num_comments": data.get("num_comments"),
    "upvote_ratio": data.get("upvote_ratio"),
    "created_utc": data.get("created_utc"),
    "url": data.get("url"),
    "permalink": data.get("permalink"),
    "selftext": data.get("selftext"),
    "nsfw": data.get("over_18"),
    "flair": data.get("link_flair_text"),
  }


def _simplify_comment(child: dict[str, Any]) -> dict[str, Any]:
  data = child["data"]
  return {
    "id": data.get("id"),
    "author": data.get("author"),
    "body": data.get("body"),
    "score": data.get("score"),
    "created_utc": data.get("created_utc"),
  }


async def browse_subreddit(
  client: RedditContentClient,
  subreddit: str,
  *,
  sort: str = "hot",
  time: str | None = None,
  limit: int = 25,
) -> list[dict[str, Any]]:
  params: dict[str, Any] = {"limit": limit}
  if sort in ("top", "controversial") and time:
    params["t"] = time

  data = await client.get(f"r/{subreddit}/{sort}", params=params)
  return [_simplify_post(child) for child in data["data"]["children"]]


async def search_reddit(
  client: RedditContentClient,
  query: str,
  *,
  subreddits: list[str] | None = None,
  sort: str = "relevance",
  time: str = "all",
  limit: int = 25,
) -> list[dict[str, Any]]:
  params: dict[str, Any] = {"q": query, "sort": sort, "t": time, "limit": limit}

  if subreddits:
    path = f"r/{'+'.join(subreddits)}/search"
    params["restrict_sr"] = 1
  else:
    path = "search"

  data = await client.get(path, params=params)
  return [_simplify_post(child) for child in data["data"]["children"]]


async def get_post_details(
  client: RedditContentClient,
  *,
  post_id: str | None = None,
  url: str | None = None,
  subreddit: str | None = None,
  comment_limit: int = 20,
  comment_sort: str = "best",
) -> dict[str, Any]:
  if not post_id and not url:
    raise ValueError("either post_id or url is required")

  resolved_id = _extract_post_id(url or post_id)  # type: ignore[arg-type]
  path = f"r/{subreddit}/comments/{resolved_id}" if subreddit else f"comments/{resolved_id}"
  params = {"limit": comment_limit, "sort": comment_sort}

  data = await client.get(path, params=params)
  post = _simplify_post(data[0]["data"]["children"][0])
  comments = [
    _simplify_comment(child) for child in data[1]["data"]["children"] if child.get("kind") == "t1"
  ]

  return {"post": post, "comments": comments}


async def user_analysis(
  client: RedditContentClient,
  username: str,
  *,
  posts_limit: int = 10,
  comments_limit: int = 10,
  time_range: str = "month",
  top_subreddits_limit: int = 10,
) -> dict[str, Any]:
  about = await client.get(f"user/{username}/about")

  posts: list[dict[str, Any]] = []
  if posts_limit > 0:
    submitted = await client.get(
      f"user/{username}/submitted", params={"limit": posts_limit, "t": time_range}
    )
    posts = [_simplify_post(child) for child in submitted["data"]["children"]]

  comments: list[dict[str, Any]] = []
  if comments_limit > 0:
    comment_listing = await client.get(
      f"user/{username}/comments", params={"limit": comments_limit, "t": time_range}
    )
    comments = [_simplify_comment(child) for child in comment_listing["data"]["children"]]

  subreddit_counts: dict[str, int] = {}
  for post in posts:
    subreddit = post.get("subreddit")
    if subreddit:
      subreddit_counts[subreddit] = subreddit_counts.get(subreddit, 0) + 1

  top_subreddits = sorted(subreddit_counts.items(), key=lambda item: item[1], reverse=True)[
    :top_subreddits_limit
  ]

  about_data = about.get("data", {})
  return {
    "username": username,
    "link_karma": about_data.get("link_karma"),
    "comment_karma": about_data.get("comment_karma"),
    "account_created_utc": about_data.get("created_utc"),
    "posts": posts,
    "comments": comments,
    "top_subreddits": [{"subreddit": name, "count": count} for name, count in top_subreddits],
  }


REDDIT_GLOSSARY: dict[str, dict[str, str]] = {
  "karma": {
    "definition": "A running score of upvotes minus downvotes a user has received on their "
    "posts and comments.",
    "origin": "Named after the Buddhist/Hindu concept of cause and effect.",
    "usage": "Used informally as a measure of a user's reputation or contribution history.",
    "example": '"That comment got 500 karma overnight."',
  },
  "cake day": {
    "definition": "The annual anniversary of the day a Reddit account was created.",
    "origin": "Reddit shows a small cake icon next to a username on their account anniversary.",
    "usage": "Users sometimes get extra goodwill or upvotes from others on their cake day.",
    "example": '"Happy cake day!"',
  },
  "ama": {
    "definition": '"Ask Me Anything" — a post format where someone answers questions from '
    "the community, usually in r/IAmA.",
    "origin": "Shorthand that emerged from the r/IAmA subreddit.",
    "usage": "Posted by notable guests, experts, or people with unusual experiences.",
    "example": '"I\'m a former astronaut, AMA."',
  },
  "op": {
    "definition": '"Original Poster" — the person who created the post or comment thread.',
    "origin": "Common internet forum shorthand predating Reddit.",
    "usage": "Used to refer back to whoever started the thread.",
    "example": '"OP never responded to any comments."',
  },
  "til": {
    "definition": '"Today I Learned" — a post sharing a fact the poster recently learned.',
    "origin": "Common post-title prefix, associated with r/todayilearned.",
    "usage": "Used to introduce a factual, often surprising, claim.",
    "example": '"TIL octopuses have three hearts."',
  },
  "eli5": {
    "definition": '"Explain Like I\'m 5" — a request for a simple, jargon-free explanation.',
    "origin": "Associated with the r/explainlikeimfive subreddit.",
    "usage": "Used when asking for or giving a simplified explanation of a complex topic.",
    "example": '"ELI5: how does a blockchain work?"',
  },
  "subreddit": {
    "definition": "A community on Reddit dedicated to a specific topic, prefixed with r/.",
    "origin": "Portmanteau of 'sub' (subsection) and 'Reddit'.",
    "usage": "Every post is submitted to exactly one subreddit.",
    "example": '"r/technology is a subreddit about tech news."',
  },
  "upvote": {
    "definition": "A vote that increases a post or comment's score, shown as an up arrow.",
    "origin": "Part of Reddit's original voting system.",
    "usage": "Used to signal agreement or that content is valuable/interesting.",
    "example": '"I upvoted that because it was genuinely helpful."',
  },
  "downvote": {
    "definition": "A vote that decreases a post or comment's score, shown as a down arrow.",
    "origin": "Part of Reddit's original voting system.",
    "usage": "Intended for content that doesn't contribute to the discussion, though often used "
    "for disagreement.",
    "example": '"That comment got downvoted into oblivion."',
  },
  "nsfw": {
    "definition": '"Not Safe For Work" — a tag marking content as explicit or inappropriate '
    "for a work/public setting.",
    "origin": "General internet content-warning convention.",
    "usage": "Posts and subreddits can be flagged NSFW to require confirmation before viewing.",
    "example": '"This post is tagged NSFW."',
  },
  "tldr": {
    "definition": '"Too Long; Didn\'t Read" — a short summary placed at the end of a long '
    "post or comment.",
    "origin": "General internet forum shorthand.",
    "usage": "Used to give readers the gist without reading the full text.",
    "example": '"TL;DR: the plan got approved."',
  },
  "mod": {
    "definition": '"Moderator" — a user with administrative permissions over a subreddit.',
    "origin": "Standard forum terminology.",
    "usage": "Mods enforce subreddit rules, remove posts, and ban users.",
    "example": '"A mod removed the post for breaking rule 3."',
  },
  "lurker": {
    "definition": "Someone who reads Reddit regularly but rarely or never posts or comments.",
    "origin": "General internet forum terminology.",
    "usage": "Often used self-deprecatingly.",
    "example": '"I\'ve been a lurker here for years before making an account."',
  },
  "crosspost": {
    "definition": "Sharing a post from one subreddit into another, preserving a link to the "
    "original.",
    "origin": "Built-in Reddit feature (the 'xpost' button).",
    "usage": "Used to share relevant content across communities.",
    "example": '"Crossposted this from r/aww."',
  },
  "gild": {
    "definition": "To give a post or comment a paid Reddit award (historically 'gold').",
    "origin": "From Reddit's original paid-award system, 'Reddit Gold'.",
    "usage": "A way to show extra appreciation beyond an upvote.",
    "example": '"Someone gilded my comment."',
  },
}


def reddit_explain(term: str) -> dict[str, str]:
  key = term.strip().lower()
  entry = REDDIT_GLOSSARY.get(key)
  if entry is None:
    raise UnknownTermError(
      f"no explanation available for {term!r} — known terms: {', '.join(sorted(REDDIT_GLOSSARY))}"
    )

  return {"term": key, **entry}
