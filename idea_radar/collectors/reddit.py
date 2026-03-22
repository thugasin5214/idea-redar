"""Reddit collector using public JSON API (no credentials required)."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from idea_radar.collectors.base import BaseCollector
from idea_radar.config import Config
from idea_radar.models import Post, Source

logger = logging.getLogger(__name__)
console = Console()

REDDIT_BASE = "https://www.reddit.com/r/{subreddit}/{sort}.json"
HEADERS = {"User-Agent": "idea-radar/1.0 (personal research tool)"}


class RedditCollector(BaseCollector):
    """Collector for Reddit posts via public JSON API (no OAuth needed)."""

    def __init__(self, config: Config):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _fetch_listing(self, subreddit: str, sort: str = "hot", limit: int = 50) -> List[dict]:
        """Fetch a listing from Reddit JSON API."""
        url = REDDIT_BASE.format(subreddit=subreddit, sort=sort)
        try:
            resp = self.session.get(url, params={"limit": limit}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("children", [])
        except Exception as e:
            logger.warning(f"Failed to fetch r/{subreddit}/{sort}: {e}")
            return []

    def _child_to_post(self, child: dict, subreddit_name: str, time_threshold: datetime) -> Optional[Post]:
        """Convert a Reddit JSON listing child to a Post object."""
        d = child.get("data", {})

        created_utc = d.get("created_utc", 0)
        created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
        if created_at < time_threshold:
            return None

        score = d.get("score", 0)
        if score < self.config.sources.reddit.min_score:
            return None

        # Skip removed/deleted posts
        if d.get("removed_by_category") or d.get("selftext") == "[removed]":
            return None

        body = d.get("selftext", "") or ""
        if len(body) > 2000:
            body = body[:1997] + "..."

        post_id = d.get("id", "")
        permalink = d.get("permalink", "")

        return Post(
            id=f"reddit:{post_id}",
            source=Source.REDDIT,
            title=d.get("title", ""),
            body=body,
            url=f"https://reddit.com{permalink}",
            author=d.get("author", "[deleted]"),
            score=score,
            num_comments=d.get("num_comments", 0),
            created_at=created_at,
            subreddit=subreddit_name,
        )

    def collect(self) -> List[Post]:
        """Collect posts from configured subreddits via public JSON API."""
        all_posts: dict[str, Post] = {}
        reddit_config = self.config.sources.reddit
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=reddit_config.time_window_hours)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Collecting from Reddit...", total=len(reddit_config.subreddits))

            for subreddit_name in reddit_config.subreddits:
                progress.update(task, description=f"Collecting from r/{subreddit_name}...")
                count = 0

                for sort in ("hot", "new"):
                    children = self._fetch_listing(subreddit_name, sort, reddit_config.max_posts_per_sub)
                    for child in children:
                        post = self._child_to_post(child, subreddit_name, time_threshold)
                        if post and post.id not in all_posts:
                            all_posts[post.id] = post
                            count += 1
                    time.sleep(1)  # be polite to Reddit

                console.print(f"  ✓ r/{subreddit_name}: [green]{count}[/green] posts")
                progress.advance(task)

        posts = list(all_posts.values())
        console.print(f"[bold]Total collected:[/bold] {len(posts)} posts")

        filtered = self.filter_by_keywords(posts)
        console.print(f"[bold]After keyword filter:[/bold] {len(filtered)} posts")

        return filtered
