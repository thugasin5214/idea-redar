# -*- coding: utf-8 -*-
"""Build HTML email digest from classified posts."""

from typing import List, Dict
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from idea_radar.models import Post, Category
from idea_radar.config import Config


CATEGORY_META = {
    Category.PAIN_POINT: ("🔥", "Pain Points"),
    Category.IDEA: ("💡", "Ideas"),
    Category.PROJECT_LAUNCH: ("🚀", "Project Launches"),
    Category.LESSON_LEARNED: ("📚", "Lessons Learned"),
}


class DigestBuilder:
    """Build HTML email from classified posts."""
    
    def __init__(self):
        """Initialize the digest builder with Jinja2 templates."""
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
        self.template = self.env.get_template("daily.html")
    
    def build(self, posts: List[Post], config: Config, run_stats: dict) -> str:
        """Build HTML email from classified posts.
        
        Args:
            posts: List of classified posts from database.
            config: Application configuration.
            run_stats: Statistics about the run including:
                - date: "Saturday, March 22 2026"
                - time_window_hours: 24
                - sources: ["r/SideProject", "r/SaaS", ...]
                - total_collected: 36
                - after_keyword_filter: 9
                - classified: 9
                - noise_filtered: 2
                
        Returns:
            HTML string for email body.
        """
        # Filter out low relevance posts
        relevant_posts = [p for p in posts if p.relevance_score >= 0.5 and p.category != Category.NOISE]
        
        # Group posts by category
        posts_by_category = {}
        for post in relevant_posts:
            if post.category not in posts_by_category:
                posts_by_category[post.category] = []
            posts_by_category[post.category].append(post)
        
        # Sort posts within each category by relevance_score DESC, then score DESC
        for category_posts in posts_by_category.values():
            category_posts.sort(key=lambda p: (p.relevance_score, p.score), reverse=True)
        
        # Build sections in display order
        sections = []
        display_order = [Category.PAIN_POINT, Category.PROJECT_LAUNCH, Category.IDEA, Category.LESSON_LEARNED]
        
        for category in display_order:
            if category in posts_by_category and posts_by_category[category]:
                icon, label = CATEGORY_META[category]
                sections.append({
                    "icon": icon,
                    "label": label,
                    "posts": posts_by_category[category],
                    "count": len(posts_by_category[category])
                })
        
        # Prepare template context
        context = {
            "date": run_stats["date"],
            "sources": ", ".join(run_stats["sources"][:5]) + (
                f" +{len(run_stats['sources']) - 5} more" if len(run_stats['sources']) > 5 else ""
            ),
            "time_window": run_stats["time_window_hours"],
            "total_collected": run_stats["total_collected"],
            "after_keyword": run_stats["after_keyword_filter"],
            "classified": run_stats["classified"],
            "noise_filtered": run_stats["noise_filtered"],
            "focus": config.ai.prompt.focus,
            "sections": sections,
            "has_content": len(relevant_posts) > 0,
            "recipient_email": config.email.recipient,
        }
        
        return self.template.render(**context)