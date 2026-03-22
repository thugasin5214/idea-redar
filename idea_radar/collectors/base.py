"""Base collector abstract class."""

from abc import ABC, abstractmethod
from typing import List

from idea_radar.config import Config
from idea_radar.models import Post


class BaseCollector(ABC):
    """Abstract base class for collectors."""
    
    def __init__(self, config: Config):
        """Initialize collector with configuration.
        
        Args:
            config: Application configuration.
        """
        self.config = config
    
    @abstractmethod
    def collect(self) -> List[Post]:
        """Collect posts from the source.
        
        Returns:
            List of collected posts.
        """
        pass
    
    def filter_by_keywords(self, posts: List[Post]) -> List[Post]:
        """Filter posts by keywords from configuration.
        
        Posts must:
        - Match at least one include keyword (if any)
        - Not match any exclude keyword
        
        Args:
            posts: List of posts to filter.
            
        Returns:
            Filtered list of posts.
        """
        filtered = []
        
        include_keywords = [kw.lower() for kw in self.config.keywords.include]
        exclude_keywords = [kw.lower() for kw in self.config.keywords.exclude]
        
        for post in posts:
            # Combine title and body for searching (case insensitive)
            text = (post.title + " " + post.body).lower()
            
            # Check exclude keywords first - if any match, skip this post
            if any(kw in text for kw in exclude_keywords):
                continue
            
            # Check include keywords - must match at least one
            if any(kw in text for kw in include_keywords):
                filtered.append(post)
        
        return filtered