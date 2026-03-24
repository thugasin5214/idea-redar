"""Hacker News collector using public Firebase API."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from html import unescape
import re

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from idea_radar.collectors.base import BaseCollector
from idea_radar.config import Config
from idea_radar.models import Post, Source

logger = logging.getLogger(__name__)
console = Console()

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HEADERS = {"User-Agent": "idea-radar/1.0 (personal research tool)"}


class HackerNewsCollector(BaseCollector):
    """Collector for Hacker News via public Firebase API."""
    
    FEEDS = [
        ("askstories", "Ask HN"),     # "Ask HN: Is there a tool for X?" - gold for pain points
        ("showstories", "Show HN"),   # "Show HN: I built X" - project launches
    ]
    
    def __init__(self, config: Config):
        """Initialize HN collector with configuration."""
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.max_workers = 10  # For parallel fetching
    
    def _strip_html(self, html_text: str) -> str:
        """Strip HTML tags from text."""
        if not html_text:
            return ""
        # Unescape HTML entities
        text = unescape(html_text)
        # Remove HTML tags
        text = re.sub('<.*?>', '', text)
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    
    def _fetch_story_ids(self, feed: str, limit: int) -> List[int]:
        """Fetch story IDs from a HN feed."""
        url = f"{HN_API_BASE}/{feed}.json"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            ids = resp.json()
            return ids[:limit] if ids else []
        except Exception as e:
            logger.warning(f"Failed to fetch HN {feed}: {e}")
            return []
    
    def _fetch_item(self, item_id: int) -> Optional[dict]:
        """Fetch a single item from HN API."""
        url = f"{HN_API_BASE}/item/{item_id}.json"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"Failed to fetch HN item {item_id}: {e}")
            return None
    
    def _item_to_post(self, item: dict, feed_label: str, time_threshold: datetime) -> Optional[Post]:
        """Convert HN item to Post object."""
        if not item:
            return None
        
        # Check time threshold
        created_timestamp = item.get('time', 0)
        created_at = datetime.fromtimestamp(created_timestamp, tz=timezone.utc)
        if created_at < time_threshold:
            return None
        
        # Check score threshold (reuse Reddit's min_score config)
        score = item.get('score', 0)
        if score < self.config.sources.reddit.min_score:
            return None
        
        # Extract fields
        item_id = item.get('id')
        if not item_id:
            return None
        
        title = item.get('title', '')
        body = self._strip_html(item.get('text', ''))
        url = item.get('url', f"https://news.ycombinator.com/item?id={item_id}")
        author = item.get('by', 'unknown')
        num_comments = item.get('descendants', 0)
        
        return Post(
            id=f"hn:{item_id}",
            source=Source.HACKER_NEWS,
            title=title,
            body=body,
            url=url,
            author=author,
            score=score,
            num_comments=num_comments,
            created_at=created_at,
            subreddit="hackernews"  # Reuse field for source label
        )
    
    def collect(self) -> List[Post]:
        """Collect posts from Hacker News.
        
        Returns:
            List of collected posts.
        """
        if not self.config.sources.hacker_news or not self.config.sources.hacker_news.enabled:
            logger.info("Hacker News collection disabled")
            return []
        
        all_posts = []
        time_threshold = datetime.now(timezone.utc) - timedelta(
            hours=self.config.sources.reddit.time_window_hours
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as progress:
            
            for feed_key, feed_label in self.FEEDS:
                # Check if this feed is enabled
                if feed_key not in self.config.sources.hacker_news.feeds:
                    continue
                
                # Fetch story IDs
                task = progress.add_task(
                    f"[cyan]Fetching HN {feed_label} stories...", 
                    total=None
                )
                
                story_ids = self._fetch_story_ids(
                    feed_key, 
                    self.config.sources.hacker_news.max_items_per_feed
                )
                
                if not story_ids:
                    progress.update(task, completed=1, total=1)
                    continue
                
                progress.update(
                    task, 
                    description=f"[cyan]Fetching {len(story_ids)} {feed_label} items...",
                    total=len(story_ids),
                    completed=0
                )
                
                # Fetch items in parallel
                feed_posts = []
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all fetch tasks
                    future_to_id = {
                        executor.submit(self._fetch_item, item_id): item_id
                        for item_id in story_ids
                    }
                    
                    # Process results as they complete
                    for future in as_completed(future_to_id):
                        progress.advance(task)
                        
                        try:
                            item = future.result()
                            if item:
                                post = self._item_to_post(item, feed_label, time_threshold)
                                if post:
                                    feed_posts.append(post)
                        except Exception as e:
                            item_id = future_to_id[future]
                            logger.debug(f"Error processing HN item {item_id}: {e}")
                        
                        # Small delay to be polite to the API
                        time.sleep(0.05)
                
                all_posts.extend(feed_posts)
                console.print(f"[green]✓[/green] Collected {len(feed_posts)} posts from HN {feed_label}")
        
        # Apply keyword filter
        filtered_posts = self.filter_by_keywords(all_posts)
        
        console.print(
            f"[bold green]Hacker News:[/bold green] "
            f"Collected {len(all_posts)} posts, {len(filtered_posts)} after keyword filtering"
        )
        
        return filtered_posts