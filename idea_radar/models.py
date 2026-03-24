"""Data models for Idea Radar."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Category(str, Enum):
    """Categories for classifying posts."""
    PAIN_POINT = "pain_point"
    IDEA = "idea"
    PROJECT_LAUNCH = "project_launch"
    LESSON_LEARNED = "lesson_learned"
    NOISE = "noise"
    UNCATEGORIZED = "uncategorized"


class Source(str, Enum):
    """Sources for posts."""
    REDDIT = "reddit"
    INDIE_HACKERS = "indie_hackers"
    HACKER_NEWS = "hacker_news"


@dataclass
class Post:
    """Represents a post from Reddit or Indie Hackers."""
    id: str  # unique, format "reddit:abc123" or "ih:abc123"
    source: Source
    title: str
    body: str
    url: str
    author: str
    score: int
    num_comments: int
    created_at: datetime
    subreddit: Optional[str] = None
    category: Category = Category.UNCATEGORIZED
    ai_summary: Optional[str] = None
    ai_opportunity: Optional[str] = None
    relevance_score: float = 0.0
    collected_at: datetime = field(default_factory=datetime.utcnow)
    sent: bool = False