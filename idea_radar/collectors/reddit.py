"""Reddit collector using PRAW (OAuth API)."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import praw
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from idea_radar.collectors.base import BaseCollector
from idea_radar.config import Config
from idea_radar.models import Post, Source

logger = logging.getLogger(__name__)
console = Console()


class RedditCollector(BaseCollector):
    """Collector for Reddit posts via PRAW (OAuth API)."""

    def __init__(self, config: Config):
        super().__init__(config)
        self.reddit = praw.Reddit(
            client_id=config.sources.reddit.client_id,
            client_secret=config.sources.reddit.client_secret,
            user_agent="idea-radar/1.0 (personal research tool by /u/idea_radar_bot)",
            ratelimit_seconds=300,
        )
        # Read-only mode (no login needed)
        self.reddit.read_only = True

    def _fetch_listing(self, subreddit: str, sort: str = "hot", limit: int = 50) -> List:
        """Fetch posts from subreddit via PRAW."""
        try:
            sub = self.reddit.subreddit(subreddit)
            listing = getattr(sub, sort)(limit=limit)
            return list(listing)
        except Exception as e:
            logger.warning(f"Failed to fetch r/{subreddit}/{sort}: {e}")
            return []

    def _submission_to_post(self, submission, subreddit_name: str, time_threshold: datetime) -> Optional[Post]:
        """Convert a PRAW submission to a Post object."""
        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        if created_at < time_threshold:
            return None

        if submission.score < self.config.sources.reddit.min_score:
            return None

        # Skip removed/deleted posts
        if submission.removed_by_category or submission.selftext in ("[removed]", "[deleted]"):
            return None

        body = submission.selftext or ""
        if len(body) > 2000:
            body = body[:1997] + "..."

        return Post(
            id=f"reddit:{submission.id}",
            source=Source.REDDIT,
            title=submission.title,
            body=body,
            url=f"https://reddit.com{submission.permalink}",
            author=str(submission.author) if submission.author else "[deleted]",
            score=submission.score,
            num_comments=submission.num_comments,
            created_at=created_at,
            subreddit=subreddit_name,
        )

    def collect(self) -> List[Post]:
        """Collect posts from configured subreddits via PRAW."""
        all_posts: dict[str, Post] = {}
        reddit_config = self.config.sources.reddit
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=reddit_config.time_window_hours)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Collecting from Reddit...", total=len(reddit_config.subreddits))

            for subreddit_name in reddit_config.subreddits:
                progress.update(task, description=f"Collecting from r/{subreddit_name}...")
                count = 0

                for sort in ("hot", "new"):
                    submissions = self._fetch_listing(subreddit_name, sort, reddit_config.max_posts_per_sub)
                    for submission in submissions:
                        post = self._submission_to_post(submission, subreddit_name, time_threshold)
                        if post and post.id not in all_posts:
                            all_posts[post.id] = post
                            count += 1
                    time.sleep(1)  # be polite

                console.print(f"  ✓ r/{subreddit_name}: [green]{count}[/green] posts")
                progress.advance(task)

        posts = list(all_posts.values())
        console.print(f"[bold]Total collected:[/bold] {len(posts)} posts")

        filtered = self.filter_by_keywords(posts)
        console.print(f"[bold]After keyword filter:[/bold] {len(filtered)} posts")

        return filtered
