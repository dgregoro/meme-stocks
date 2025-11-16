from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

import praw
from praw.models import Submission

from backend.app.config import get_settings
from backend.app.utils.errors import ExternalAPIError


@dataclass(frozen=True)
class RedditPostData:
    """Normalized representation of a Reddit submission relevant for sentiment."""

    id: str
    stock_symbol: str
    subreddit: str
    title: str
    author: str
    upvotes: int
    comments: int
    url: str
    posted_at: datetime
    collected_at: datetime


class RedditService:
    """Service responsible for fetching posts from Reddit via PRAW.

    This service is intentionally decoupled from the database; callers can
    decide how to persist the returned data. Errors from the Reddit API are
    wrapped in ExternalAPIError so that higher layers can handle them
    explicitly.
    """

    def __init__(self, client: praw.Reddit | None = None) -> None:
        if client is None:
            settings = get_settings()
            try:
                client = praw.Reddit(
                    client_id=settings.reddit_client_id,
                    client_secret=settings.reddit_client_secret,
                    user_agent=settings.reddit_user_agent,
                    check_for_async=False,
                )
            except Exception as exc:  # pragma: no cover - exercised via higher-level tests
                raise ExternalAPIError("Failed to initialize Reddit client") from exc

        self._client = client

    def fetch_recent_posts(
        self,
        subreddits: Iterable[str],
        limit_per_subreddit: int = 100,
        max_age: timedelta | None = timedelta(days=2),
    ) -> List[RedditPostData]:
        """Fetch recent submissions from the given subreddits.

        - Only returns posts not older than ``max_age`` if provided.
        - Does not filter by stock symbol here; that is left to higher-level
          logic so ticker extraction rules remain configurable.
        """

        now = datetime.now(timezone.utc)
        results: list[RedditPostData] = []

        for subreddit_name in subreddits:
            try:
                subreddit = self._client.subreddit(subreddit_name)
                for submission in subreddit.new(limit=limit_per_subreddit):
                    created = datetime.fromtimestamp(
                        float(submission.created_utc), tz=timezone.utc
                    )
                    if max_age is not None and created < now - max_age:
                        # Skip posts older than the window; we do not break here
                        # to keep behavior simple and testable with dummy data.
                        continue

                    results.append(
                        RedditPostData(
                            id=submission.id,
                            stock_symbol="",  # to be filled by ticker extraction logic
                            subreddit=subreddit_name,
                            title=submission.title or "",
                            author=str(getattr(submission, "author", "") or ""),
                            upvotes=int(getattr(submission, "score", 0)),
                            comments=int(getattr(submission, "num_comments", 0)),
                            url=submission.permalink,
                            posted_at=created,
                            collected_at=now,
                        )
                    )
            except Exception as exc:
                raise ExternalAPIError(
                    f"Failed to fetch posts from subreddit '{subreddit_name}'"
                ) from exc

        return results


