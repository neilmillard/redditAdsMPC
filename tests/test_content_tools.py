from unittest.mock import AsyncMock

import pytest

from reddit_ads_mcp import content_tools


def make_post(post_id="abc123", subreddit="technology", title="Some title"):
  return {
    "kind": "t3",
    "data": {
      "id": post_id,
      "title": title,
      "author": "some_user",
      "subreddit": subreddit,
      "score": 42,
      "num_comments": 3,
      "upvote_ratio": 0.9,
      "created_utc": 1700000000,
      "url": "https://example.com/article",
      "permalink": f"/r/{subreddit}/comments/{post_id}/some_title/",
      "selftext": "",
      "over_18": False,
      "link_flair_text": None,
    },
  }


def make_comment(comment_id="c1", body="Nice find"):
  return {
    "kind": "t1",
    "data": {
      "id": comment_id,
      "author": "commenter",
      "body": body,
      "score": 5,
      "created_utc": 1700000100,
    },
  }


def make_client(**overrides):
  client = AsyncMock()
  client.get.return_value = overrides.get("get_result", {"data": {"children": []}})
  return client


# -- browse_subreddit -----------------------------------------------------


async def test_browse_subreddit_defaults_to_hot():
  client = make_client(get_result={"data": {"children": [make_post()]}})

  result = await content_tools.browse_subreddit(client, "technology")

  assert result == [
    {
      "id": "abc123",
      "title": "Some title",
      "author": "some_user",
      "subreddit": "technology",
      "score": 42,
      "num_comments": 3,
      "upvote_ratio": 0.9,
      "created_utc": 1700000000,
      "url": "https://example.com/article",
      "permalink": "/r/technology/comments/abc123/some_title/",
      "selftext": "",
      "nsfw": False,
      "flair": None,
    }
  ]
  client.get.assert_called_once_with("r/technology/hot", params={"limit": 25})


async def test_browse_subreddit_top_with_time_window():
  client = make_client()

  await content_tools.browse_subreddit(client, "technology", sort="top", time="week", limit=10)

  client.get.assert_called_once_with("r/technology/top", params={"limit": 10, "t": "week"})


async def test_browse_subreddit_hot_ignores_time():
  client = make_client()

  await content_tools.browse_subreddit(client, "technology", sort="hot", time="week")

  client.get.assert_called_once_with("r/technology/hot", params={"limit": 25})


# -- search_reddit ----------------------------------------------------------


async def test_search_reddit_searches_globally_by_default():
  client = make_client(get_result={"data": {"children": [make_post()]}})

  result = await content_tools.search_reddit(client, "quantum computing")

  assert len(result) == 1
  client.get.assert_called_once_with(
    "search", params={"q": "quantum computing", "sort": "relevance", "t": "all", "limit": 25}
  )


async def test_search_reddit_restricts_to_subreddits():
  client = make_client()

  await content_tools.search_reddit(
    client, "quantum", subreddits=["physics", "science"], sort="top", time="year", limit=5
  )

  client.get.assert_called_once_with(
    "r/physics+science/search",
    params={"q": "quantum", "sort": "top", "t": "year", "limit": 5, "restrict_sr": 1},
  )


# -- get_post_details ---------------------------------------------------------


async def test_get_post_details_requires_post_id_or_url():
  client = make_client()

  with pytest.raises(ValueError):
    await content_tools.get_post_details(client)


async def test_get_post_details_by_post_id():
  client = make_client(
    get_result=[
      {"data": {"children": [make_post(post_id="abc123")]}},
      {"data": {"children": [make_comment()]}},
    ]
  )

  result = await content_tools.get_post_details(client, post_id="abc123")

  assert result["post"]["id"] == "abc123"
  assert result["comments"] == [
    {"id": "c1", "author": "commenter", "body": "Nice find", "score": 5, "created_utc": 1700000100}
  ]
  client.get.assert_called_once_with("comments/abc123", params={"limit": 20, "sort": "best"})


async def test_get_post_details_with_subreddit_avoids_extra_lookup():
  client = make_client(
    get_result=[
      {"data": {"children": [make_post(post_id="abc123")]}},
      {"data": {"children": []}},
    ]
  )

  await content_tools.get_post_details(client, post_id="abc123", subreddit="technology")

  client.get.assert_called_once_with(
    "r/technology/comments/abc123", params={"limit": 20, "sort": "best"}
  )


async def test_get_post_details_extracts_id_from_full_url():
  client = make_client(
    get_result=[
      {"data": {"children": [make_post(post_id="abc123")]}},
      {"data": {"children": []}},
    ]
  )

  await content_tools.get_post_details(
    client, url="https://reddit.com/r/technology/comments/abc123/some_title/"
  )

  client.get.assert_called_once_with("comments/abc123", params={"limit": 20, "sort": "best"})


async def test_get_post_details_filters_non_comment_children():
  client = make_client(
    get_result=[
      {"data": {"children": [make_post(post_id="abc123")]}},
      {"data": {"children": [make_comment(), {"kind": "more", "data": {}}]}},
    ]
  )

  result = await content_tools.get_post_details(client, post_id="abc123")

  assert len(result["comments"]) == 1


# -- user_analysis ------------------------------------------------------------


async def test_user_analysis_combines_about_posts_and_comments():
  client = make_client()
  client.get.side_effect = [
    {"data": {"link_karma": 100, "comment_karma": 200, "created_utc": 1690000000}},
    {"data": {"children": [make_post(subreddit="technology"), make_post(subreddit="technology")]}},
    {"data": {"children": [make_comment()]}},
  ]

  result = await content_tools.user_analysis(client, "some_user")

  assert result["username"] == "some_user"
  assert result["link_karma"] == 100
  assert result["comment_karma"] == 200
  assert len(result["posts"]) == 2
  assert len(result["comments"]) == 1
  assert result["top_subreddits"] == [{"subreddit": "technology", "count": 2}]
  client.get.assert_any_call("user/some_user/about")
  client.get.assert_any_call("user/some_user/submitted", params={"limit": 10, "t": "month"})
  client.get.assert_any_call("user/some_user/comments", params={"limit": 10, "t": "month"})


async def test_user_analysis_skips_calls_when_limits_are_zero():
  client = make_client()
  client.get.side_effect = [
    {"data": {"link_karma": 1, "comment_karma": 2, "created_utc": 1690000000}},
  ]

  result = await content_tools.user_analysis(client, "some_user", posts_limit=0, comments_limit=0)

  assert result["posts"] == []
  assert result["comments"] == []
  client.get.assert_called_once_with("user/some_user/about")


# -- reddit_explain -----------------------------------------------------------


def test_reddit_explain_returns_known_term():
  result = content_tools.reddit_explain("karma")

  assert result["term"] == "karma"
  assert "definition" in result
  assert "origin" in result
  assert "usage" in result
  assert "example" in result


def test_reddit_explain_is_case_and_whitespace_insensitive():
  result = content_tools.reddit_explain("  Cake Day ")

  assert result["term"] == "cake day"


def test_reddit_explain_raises_for_unknown_term():
  with pytest.raises(content_tools.UnknownTermError):
    content_tools.reddit_explain("not_a_real_reddit_term")
