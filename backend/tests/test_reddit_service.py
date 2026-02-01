from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.reddit_service import RedditService
from backend.app.utils.errors import ExternalAPIError


class DummySubmission:
    def __init__(
        self,
        id: str,
        created_utc: float,
        title: str = "t",
        score: int = 0,
        num_comments: int = 0,
    ):
        self.id = id
        self.created_utc = created_utc
        self.title = title
        self.score = score
        self.num_comments = num_comments
        self.author = "user"
        self.permalink = f"https://reddit.com/{id}"


class DummySubreddit:
    def __init__(self, submissions: list[DummySubmission]) -> None:
        self._submissions = submissions

    def new(self, limit: int) -> list[DummySubmission]:
        # Return at most limit submissions in the order provided
        return self._submissions[:limit]


class DummyRedditClient:
    def __init__(self, mapping: dict[str, DummySubreddit]) -> None:
        self._mapping = mapping

    def subreddit(self, name: str) -> DummySubreddit:
        if name not in self._mapping:
            raise ValueError(f"Unknown subreddit {name}")
        return self._mapping[name]


def test_reddit_service_fetch_recent_posts_filters_by_max_age() -> None:
    # Use a fixed reference time to make this test deterministic.
    now = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    recent = DummySubmission(id="recent", created_utc=(now - timedelta(hours=1)).timestamp())
    old = DummySubmission(id="old", created_utc=(now - timedelta(days=10)).timestamp())

    client = DummyRedditClient({"wallstreetbets": DummySubreddit([recent, old])})
    service = RedditService(client=client)  # type: ignore[arg-type]

    # Patch datetime.now used inside the service to return our fixed time.
    # We do this locally here to avoid coupling production code to test-time behavior.
    from backend.app import services as services_pkg  # type: ignore

    original_datetime = services_pkg.reddit_service.datetime  # type: ignore[attr-defined]
    try:
        services_pkg.reddit_service.datetime = type(  # type: ignore[attr-defined,misc,assignment]
            "DT",
            (),
            {
                "now": staticmethod(lambda tz=None: now),
                "fromtimestamp": datetime.fromtimestamp,
            },
        )

        posts = service.fetch_recent_posts(["wallstreetbets"], limit_per_subreddit=10, max_age=timedelta(days=2))

        ids = {p.id for p in posts}
        assert "recent" in ids
        assert "old" not in ids
    finally:
        services_pkg.reddit_service.datetime = original_datetime  # type: ignore[attr-defined,misc,assignment]


def test_reddit_service_raises_external_api_error_on_client_failure() -> None:
    class FailingClient(DummyRedditClient):
        def subreddit(self, name: str) -> DummySubreddit:
            raise RuntimeError("boom")

    service = RedditService(client=FailingClient({}))  # type: ignore[arg-type]

    with pytest.raises(ExternalAPIError):
        service.fetch_recent_posts(["wallstreetbets"])
