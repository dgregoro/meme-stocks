"""Canonical metric keys for job run history.

Use these constants everywhere (scheduler, api/jobs, tests) so metrics
stay consistent and the UI can rely on stable keys.
"""

# Reddit collection job
REDDIT_POSTS_FETCHED = "posts_fetched"
REDDIT_POSTS_INSERTED = "posts_inserted"
REDDIT_SYMBOLS_MENTIONED = "symbols_mentioned"
REDDIT_STOCKS_CREATED = "stocks_created"
