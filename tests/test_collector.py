"""Tests for collectors."""

import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from idea_radar.collectors.base import BaseCollector
from idea_radar.config import Config, KeywordsConfig
from idea_radar.db import init_db, save_posts, get_unsent_posts
from idea_radar.models import Post, Source, Category


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=Config)
    config.keywords = KeywordsConfig(
        include=["pain point", "struggling with", "wish there was"],
        exclude=["hiring", "job posting"]
    )
    return config


@pytest.fixture
def sample_post():
    """Create a sample post."""
    return Post(
        id="reddit:test123",
        source=Source.REDDIT,
        title="Test Post",
        body="This is a test body",
        url="https://reddit.com/r/test/comments/test",
        author="testuser",
        score=50,
        num_comments=10,
        created_at=datetime.now(timezone.utc),
        subreddit="test"
    )


class TestCollector(BaseCollector):
    """Test implementation of BaseCollector."""
    
    def collect(self):
        return []


def test_keyword_filter_include(mock_config, sample_post):
    """Test that posts with include keywords pass filter."""
    collector = TestCollector(mock_config)
    
    # Post with "pain point" in title
    sample_post.title = "I have a pain point with documentation"
    result = collector.filter_by_keywords([sample_post])
    assert len(result) == 1
    assert result[0].id == "reddit:test123"
    
    # Post with "struggling with" in body
    sample_post.title = "Need help"
    sample_post.body = "I'm struggling with deployment"
    result = collector.filter_by_keywords([sample_post])
    assert len(result) == 1


def test_keyword_filter_exclude(mock_config, sample_post):
    """Test that posts with exclude keywords are filtered out."""
    collector = TestCollector(mock_config)
    
    # Post with "hiring" in title
    sample_post.title = "We're hiring engineers who have a pain point"
    result = collector.filter_by_keywords([sample_post])
    assert len(result) == 0
    
    # Post with "job posting" in body
    sample_post.title = "I have a pain point"
    sample_post.body = "This is a job posting for developers"
    result = collector.filter_by_keywords([sample_post])
    assert len(result) == 0


def test_keyword_filter_no_match(mock_config, sample_post):
    """Test that posts with no matching keywords are filtered out."""
    collector = TestCollector(mock_config)
    
    sample_post.title = "Just a regular post"
    sample_post.body = "Nothing special here"
    result = collector.filter_by_keywords([sample_post])
    assert len(result) == 0


def test_reddit_post_id_format(sample_post):
    """Test that Reddit post IDs have correct format."""
    assert sample_post.id.startswith("reddit:")
    assert sample_post.source == Source.REDDIT


def test_save_and_retrieve_posts():
    """Test saving posts to database and retrieving unsent posts."""
    # Create in-memory database
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Initialize schema
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            url TEXT NOT NULL,
            author TEXT,
            score INTEGER,
            num_comments INTEGER,
            created_at TEXT,
            subreddit TEXT,
            category TEXT DEFAULT 'uncategorized',
            ai_summary TEXT,
            ai_opportunity TEXT,
            relevance_score REAL DEFAULT 0.0,
            collected_at TEXT,
            sent INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    
    # Create test posts
    now = datetime.now(timezone.utc)
    posts = [
        Post(
            id="reddit:test1",
            source=Source.REDDIT,
            title="Test Post 1",
            body="Body 1",
            url="https://reddit.com/1",
            author="user1",
            score=100,
            num_comments=5,
            created_at=now,
            subreddit="test",
            collected_at=now
        ),
        Post(
            id="reddit:test2",
            source=Source.REDDIT,
            title="Test Post 2",
            body="Body 2",
            url="https://reddit.com/2",
            author="user2",
            score=200,
            num_comments=10,
            created_at=now,
            subreddit="test",
            collected_at=now
        )
    ]
    
    # Save posts
    new_count = save_posts(conn, posts)
    assert new_count == 2
    
    # Try saving again (should be 0 due to duplicates)
    new_count = save_posts(conn, posts)
    assert new_count == 0
    
    # Retrieve unsent posts
    unsent = get_unsent_posts(conn, now)
    assert len(unsent) == 2
    assert all(not post.sent for post in unsent)
    assert unsent[0].id in ["reddit:test1", "reddit:test2"]
    
    conn.close()