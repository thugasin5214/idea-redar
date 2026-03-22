#!/usr/bin/env python3
"""Collector for Indie Hackers posts via RSS and scraping."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from rich.console import Console

from idea_radar.collectors.base import BaseCollector
from idea_radar.config import Config
from idea_radar.models import Post, Source

logger = logging.getLogger(__name__)
console = Console()


class IndieHackersCollector(BaseCollector):
    """Collector for Indie Hackers posts via RSS + scraping."""

    RSS_URLS = [
        "https://www.indiehackers.com/feed.rss",
    ]

    SCRAPE_URLS = [
        "https://www.indiehackers.com/posts",
    ]

    def __init__(self, config: Config) -> None:
        """Initialize the Indie Hackers collector.

        Args:
            config: Application configuration object.
        """
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def collect(self) -> List[Post]:
        """Collect posts from Indie Hackers.

        Returns:
            List of Post objects from Indie Hackers.
        """
        all_posts: List[Post] = []

        # 1. Try RSS feeds first
        console.print("[dim]Fetching Indie Hackers RSS feeds...[/dim]")
        rss_posts = self._fetch_rss_feeds()
        all_posts.extend(rss_posts)

        # 2. Try scraping HTML pages
        console.print("[dim]Scraping Indie Hackers pages...[/dim]")
        scraped_posts = self._scrape_pages()
        all_posts.extend(scraped_posts)

        # 3. Deduplicate by URL
        seen_urls = set()
        unique_posts = []
        for post in all_posts:
            if post.url not in seen_urls:
                seen_urls.add(post.url)
                unique_posts.append(post)

        # 4. Apply keyword filter (time window filtering happens at DB level)
        final_posts = self.filter_by_keywords(unique_posts)

        console.print(f"[dim]Indie Hackers: {len(final_posts)} posts after filtering[/dim]")
        return final_posts

    def _fetch_rss_feeds(self) -> List[Post]:
        """Fetch posts from RSS feeds.

        Returns:
            List of Post objects from RSS feeds.
        """
        posts: List[Post] = []

        for url in self.RSS_URLS:
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # Check if we got actual RSS or HTML error page
                if "text/html" in response.headers.get("Content-Type", ""):
                    logger.warning(f"RSS URL {url} returned HTML instead of RSS")
                    continue

                root = ET.fromstring(response.content)
                
                # Handle both RSS 2.0 and Atom formats
                channel = root.find("channel")
                if channel is None:
                    # Try Atom format
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
                    for item in items:
                        post = self._parse_atom_entry(item)
                        if post:
                            posts.append(post)
                else:
                    items = channel.findall("item")
                    for item in items:
                        post = self._parse_rss_item(item)
                        if post:
                            posts.append(post)

            except ET.ParseError as e:
                logger.warning(f"Failed to parse RSS feed {url}: {e}")
            except requests.RequestException as e:
                logger.warning(f"Failed to fetch RSS feed {url}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error fetching RSS {url}: {e}")

        return posts

    def _parse_rss_item(self, item: ET.Element) -> Optional[Post]:
        """Parse an RSS item element into a Post object.

        Args:
            item: XML element representing an RSS item.

        Returns:
            Post object or None if parsing fails.
        """
        try:
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")
            author_elem = item.find("author")
            creator_elem = item.find("{http://purl.org/dc/elements/1.1/}creator")

            title = title_elem.text if title_elem is not None and title_elem.text else ""
            url = link_elem.text if link_elem is not None and link_elem.text else ""
            description = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            pub_date_str = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
            author = author_elem.text if author_elem is not None and author_elem.text else ""
            if not author and creator_elem is not None and creator_elem.text:
                author = creator_elem.text

            if not url:
                return None

            created_at = self._parse_date(pub_date_str)
            post_id = self._generate_id(url)

            return Post(
                id=f"ih:{post_id}",
                source=Source.INDIE_HACKERS,
                title=title[:500] if title else "",
                body=description[:2000] if description else "",
                url=url,
                author=author if author else "indiehackers",
                score=0,
                num_comments=0,
                created_at=created_at,
                subreddit=None,
            )
        except Exception as e:
            logger.warning(f"Failed to parse RSS item: {e}")
            return None

    def _parse_atom_entry(self, entry: ET.Element) -> Optional[Post]:
        """Parse an Atom entry element into a Post object.

        Args:
            entry: XML element representing an Atom entry.

        Returns:
            Post object or None if parsing fails.
        """
        try:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            
            title_elem = entry.find("atom:title", ns)
            link_elem = entry.find("atom:link", ns)
            summary_elem = entry.find("atom:summary", ns)
            content_elem = entry.find("atom:content", ns)
            published_elem = entry.find("atom:published", ns)
            updated_elem = entry.find("atom:updated", ns)
            author_elem = entry.find("atom:author", ns)

            title = title_elem.text if title_elem is not None and title_elem.text else ""
            url = link_elem.get("href", "") if link_elem is not None else ""
            description = ""
            if summary_elem is not None and summary_elem.text:
                description = summary_elem.text
            elif content_elem is not None and content_elem.text:
                description = content_elem.text
            
            pub_date_str = ""
            if published_elem is not None and published_elem.text:
                pub_date_str = published_elem.text
            elif updated_elem is not None and updated_elem.text:
                pub_date_str = updated_elem.text

            author = ""
            if author_elem is not None:
                name_elem = author_elem.find("atom:name", ns)
                if name_elem is not None and name_elem.text:
                    author = name_elem.text

            if not url:
                return None

            created_at = self._parse_date(pub_date_str)
            post_id = self._generate_id(url)

            return Post(
                id=f"ih:{post_id}",
                source=Source.INDIE_HACKERS,
                title=title[:500] if title else "",
                body=description[:2000] if description else "",
                url=url,
                author=author if author else "indiehackers",
                score=0,
                num_comments=0,
                created_at=created_at,
                subreddit=None,
            )
        except Exception as e:
            logger.warning(f"Failed to parse Atom entry: {e}")
            return None

    def _scrape_pages(self) -> List[Post]:
        """Scrape HTML pages for posts.

        Returns:
            List of Post objects from scraped pages.
        """
        posts: List[Post] = []

        for url in self.SCRAPE_URLS:
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # Check if we got blocked or redirected
                if response.status_code != 200:
                    logger.warning(f"Scrape URL {url} returned status {response.status_code}")
                    continue

                # Check if it's actually HTML content we can parse
                if "Create an Indie Hackers Profile" in response.text:
                    logger.warning(f"Scrape URL {url} returned sign-up page (likely blocked)")
                    continue

                soup = BeautifulSoup(response.content, "html.parser")
                scraped_posts = self._parse_html_page(soup, url)
                posts.extend(scraped_posts)

            except requests.RequestException as e:
                logger.warning(f"Failed to scrape page {url}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error scraping {url}: {e}")

        return posts

    def _parse_html_page(self, soup: BeautifulSoup, base_url: str) -> List[Post]:
        """Parse HTML page content for posts.

        Args:
            soup: BeautifulSoup object of the page.
            base_url: The URL of the page being parsed.

        Returns:
            List of Post objects found on the page.
        """
        posts: List[Post] = []

        # Try to find post cards/containers
        # Indie Hackers uses various class names, try common patterns
        post_containers = soup.find_all(["article", "div"], class_=lambda x: x and any(
            keyword in x for keyword in ["post", "card", "item", "entry"]
        ))

        for container in post_containers[:20]:  # Limit to first 20 to avoid duplicates
            try:
                title_elem = container.find(["h1", "h2", "h3", "a"], class_=lambda x: x and "title" in str(x).lower())
                if not title_elem:
                    title_elem = container.find(["h1", "h2", "h3", "a"])
                
                link_elem = container.find("a", href=True)
                desc_elem = container.find(["p", "div"], class_=lambda x: x and any(
                    keyword in str(x).lower() for keyword in ["desc", "content", "summary", "text"]
                ))
                author_elem = container.find(class_=lambda x: x and any(
                    keyword in str(x).lower() for keyword in ["author", "user", "by"]
                ))
                time_elem = container.find(["time", "span"], class_=lambda x: x and any(
                    keyword in str(x).lower() for keyword in ["time", "date", "ago"]
                ))

                title = title_elem.get_text(strip=True) if title_elem else ""
                url = link_elem["href"] if link_elem else ""
                if url and not url.startswith("http"):
                    url = f"https://www.indiehackers.com{url}"
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                author = author_elem.get_text(strip=True) if author_elem else ""
                time_str = time_elem.get_text(strip=True) if time_elem else ""

                if not url or not title:
                    continue

                created_at = self._parse_relative_time(time_str) if time_str else datetime.now(timezone.utc)
                post_id = self._generate_id(url)

                post = Post(
                    id=f"ih:{post_id}",
                    source=Source.INDIE_HACKERS,
                    title=title[:500],
                    body=description[:2000],
                    url=url,
                    author=author if author else "indiehackers",
                    score=0,
                    num_comments=0,
                    created_at=created_at,
                    subreddit=None,
                )
                posts.append(post)

            except Exception as e:
                logger.warning(f"Failed to parse post container: {e}")
                continue

        return posts

    def _generate_id(self, url: str) -> str:
        """Generate a unique ID from a URL.

        Args:
            url: The URL to generate ID from.

        Returns:
            12-character hex string.
        """
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _parse_date(self, date_str: str) -> datetime:
        """Parse a date string into a datetime object.

        Args:
            date_str: Date string in various formats.

        Returns:
            datetime object, or current time if parsing fails.
        """
        if not date_str:
            return datetime.now(timezone.utc)

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # RFC 822
            "%a, %d %b %Y %H:%M:%S %Z",  # RFC 822 with timezone name
            "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601
            "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601 UTC
            "%Y-%m-%d %H:%M:%S",  # Simple format
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return datetime.now(timezone.utc)

    def _parse_relative_time(self, time_str: str) -> datetime:
        """Parse a relative time string (e.g., '2 hours ago') into datetime.

        Args:
            time_str: Relative time string.

        Returns:
            datetime object, or current time if parsing fails.
        """
        import re

        now = datetime.now(timezone.utc)

        if not time_str:
            return now

        time_str = time_str.lower().strip()

        # Try to extract number and unit
        match = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?", time_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            from dateutil.relativedelta import relativedelta
            try:
                if unit == "second":
                    delta = relativedelta(seconds=value)
                elif unit == "minute":
                    delta = relativedelta(minutes=value)
                elif unit == "hour":
                    delta = relativedelta(hours=value)
                elif unit == "day":
                    delta = relativedelta(days=value)
                elif unit == "week":
                    delta = relativedelta(weeks=value)
                elif unit == "month":
                    delta = relativedelta(months=value)
                elif unit == "year":
                    delta = relativedelta(years=value)
                else:
                    return now

                return now - delta
            except Exception:
                pass

        # If "ago" is in the string but we couldn't parse, assume recent
        if "ago" in time_str:
            return now

        return now
