"""SQLite database operations."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from idea_radar.models import Category, Post, Source


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize database with schema.
    
    Args:
        db_path: Path to SQLite database file.
        
    Returns:
        Database connection.
    """
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    
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
    
    return conn


def save_posts(conn: sqlite3.Connection, posts: List[Post]) -> int:
    """Save posts to database, skipping duplicates.
    
    Args:
        conn: Database connection.
        posts: List of posts to save.
        
    Returns:
        Number of new posts saved.
    """
    cursor = conn.cursor()
    new_count = 0
    
    for post in posts:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO posts (
                    id, source, title, body, url, author, score, num_comments,
                    created_at, subreddit, category, ai_summary, ai_opportunity,
                    relevance_score, collected_at, sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.id,
                post.source.value,
                post.title,
                post.body,
                post.url,
                post.author,
                post.score,
                post.num_comments,
                post.created_at.isoformat(),
                post.subreddit,
                post.category.value,
                post.ai_summary,
                post.ai_opportunity,
                post.relevance_score,
                post.collected_at.isoformat(),
                int(post.sent)
            ))
            
            if cursor.rowcount > 0:
                new_count += 1
        except sqlite3.IntegrityError:
            # Duplicate ID, skip
            continue
    
    conn.commit()
    return new_count


def get_unsent_posts(conn: sqlite3.Connection, since: datetime) -> List[Post]:
    """Get unsent posts since a given date.
    
    Args:
        conn: Database connection.
        since: Minimum collected_at date.
        
    Returns:
        List of unsent posts.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM posts 
        WHERE sent = 0 AND collected_at >= ?
        ORDER BY relevance_score DESC, created_at DESC
    """, (since.isoformat(),))
    
    rows = cursor.fetchall()
    posts = []
    
    for row in rows:
        post = Post(
            id=row["id"],
            source=Source(row["source"]),
            title=row["title"],
            body=row["body"] or "",
            url=row["url"],
            author=row["author"] or "",
            score=row["score"] or 0,
            num_comments=row["num_comments"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
            subreddit=row["subreddit"],
            category=Category(row["category"]),
            ai_summary=row["ai_summary"],
            ai_opportunity=row["ai_opportunity"],
            relevance_score=row["relevance_score"],
            collected_at=datetime.fromisoformat(row["collected_at"]),
            sent=bool(row["sent"])
        )
        posts.append(post)
    
    return posts


def mark_sent(conn: sqlite3.Connection, post_ids: List[str]) -> None:
    """Mark posts as sent.
    
    Args:
        conn: Database connection.
        post_ids: IDs of posts to mark as sent.
    """
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(post_ids))
    cursor.execute(f"""
        UPDATE posts SET sent = 1
        WHERE id IN ({placeholders})
    """, post_ids)
    conn.commit()


def update_classification(
    conn: sqlite3.Connection,
    post_id: str,
    category: Category,
    ai_summary: str,
    ai_opportunity: str,
    relevance_score: float
) -> None:
    """Update post classification from AI.
    
    Args:
        conn: Database connection.
        post_id: Post ID to update.
        category: Classified category.
        ai_summary: AI-generated summary.
        ai_opportunity: AI-generated opportunity description.
        relevance_score: Relevance score (0-1).
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE posts 
        SET category = ?, ai_summary = ?, ai_opportunity = ?, relevance_score = ?
        WHERE id = ?
    """, (category.value, ai_summary, ai_opportunity, relevance_score, post_id))
    conn.commit()