"""Configuration loading and management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

import yaml


@dataclass
class RedditConfig:
    """Reddit source configuration."""
    client_id: str
    client_secret: str
    user_agent: str
    subreddits: List[str]
    min_score: int
    max_posts_per_sub: int
    time_window_hours: int


@dataclass
class IndieHackersConfig:
    """Indie Hackers source configuration."""
    enabled: bool


@dataclass
class HackerNewsConfig:
    """Hacker News source configuration."""
    enabled: bool
    feeds: List[str]
    max_items_per_feed: int


@dataclass
class SourcesConfig:
    """Sources configuration."""
    reddit: RedditConfig
    indie_hackers: IndieHackersConfig
    hacker_news: Optional[HackerNewsConfig] = None


@dataclass
class KeywordsConfig:
    """Keywords configuration."""
    include: List[str]
    exclude: List[str]


@dataclass
class PromptConfig:
    """Prompt configuration."""
    focus: str = "side projects, startup ideas, and user pain points"
    extra_instructions: str = ""
    categories: Dict[str, str] = field(default_factory=lambda: {
        "pain_point": "User expressing frustration, problem, or unmet need",
        "idea": "Someone sharing a startup or side project idea",
        "project_launch": "Announcing a new product, project, or milestone",
        "lesson_learned": "Sharing experience, retrospective, or advice",
        "noise": "Off-topic, promotional spam, or not relevant",
    })


@dataclass
class AIConfig:
    """AI configuration."""
    provider: str
    api_key: str
    model: str
    fallback_model: str
    batch_size: int
    prompt: PromptConfig = field(default_factory=PromptConfig)


@dataclass
class EmailConfig:
    """Email configuration."""
    smtp_host: str
    smtp_port: int
    sender: str
    password: str
    recipient: str
    send_hour: int
    timezone: str


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str


@dataclass
class Config:
    """Main configuration."""
    sources: SourcesConfig
    keywords: KeywordsConfig
    ai: AIConfig
    email: EmailConfig
    database: DatabaseConfig
    logging: LoggingConfig


def load_config(path: str = "config.yaml") -> Config:
    """Load configuration from YAML file with environment variable overrides.
    
    Args:
        path: Path to configuration file.
        
    Returns:
        Loaded configuration.
        
    Raises:
        ValueError: If required configuration fields are missing.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ValueError(f"Configuration file not found: {path}. Copy config.example.yaml to config.yaml and fill in your settings.")
    
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Validate required fields
    if not data:
        raise ValueError("Configuration file is empty")
    
    # Apply environment variable overrides
    if openrouter_key := os.getenv("OPENROUTER_API_KEY"):
        data["ai"]["api_key"] = openrouter_key
    
    if gmail_password := os.getenv("GMAIL_PASSWORD"):
        data["email"]["password"] = gmail_password
    
    if reddit_secret := os.getenv("REDDIT_CLIENT_SECRET"):
        data["sources"]["reddit"]["client_secret"] = reddit_secret
    
    # Parse sources
    reddit_data = data["sources"]["reddit"]
    reddit_config = RedditConfig(
        client_id=reddit_data["client_id"],
        client_secret=reddit_data["client_secret"],
        user_agent=reddit_data["user_agent"],
        subreddits=reddit_data["subreddits"],
        min_score=reddit_data["min_score"],
        max_posts_per_sub=reddit_data["max_posts_per_sub"],
        time_window_hours=reddit_data["time_window_hours"]
    )
    
    indie_hackers_config = IndieHackersConfig(
        enabled=data["sources"]["indie_hackers"]["enabled"]
    )
    
    # Parse Hacker News config if present
    hacker_news_config = None
    if "hacker_news" in data["sources"]:
        hn_data = data["sources"]["hacker_news"]
        hacker_news_config = HackerNewsConfig(
            enabled=hn_data["enabled"],
            feeds=hn_data["feeds"],
            max_items_per_feed=hn_data["max_items_per_feed"]
        )
    
    sources_config = SourcesConfig(
        reddit=reddit_config,
        indie_hackers=indie_hackers_config,
        hacker_news=hacker_news_config
    )
    
    # Parse keywords
    keywords_config = KeywordsConfig(
        include=data["keywords"]["include"],
        exclude=data["keywords"]["exclude"]
    )
    
    # Parse AI
    ai_data = data["ai"]
    
    # Parse prompt config if present (backward compatible)
    prompt_config = PromptConfig()
    if "prompt" in ai_data:
        prompt_data = ai_data["prompt"]
        prompt_config = PromptConfig(
            focus=prompt_data.get("focus", prompt_config.focus),
            extra_instructions=prompt_data.get("extra_instructions", ""),
            categories=prompt_data.get("categories", prompt_config.categories)
        )
    
    ai_config = AIConfig(
        provider=ai_data["provider"],
        api_key=ai_data["api_key"],
        model=ai_data["model"],
        fallback_model=ai_data["fallback_model"],
        batch_size=ai_data["batch_size"],
        prompt=prompt_config
    )
    
    # Parse email
    email_config = EmailConfig(
        smtp_host=data["email"]["smtp_host"],
        smtp_port=data["email"]["smtp_port"],
        sender=data["email"]["sender"],
        password=data["email"]["password"],
        recipient=data["email"]["recipient"],
        send_hour=data["email"]["send_hour"],
        timezone=data["email"]["timezone"]
    )
    
    # Parse database
    database_config = DatabaseConfig(
        path=data["database"]["path"]
    )
    
    # Parse logging
    logging_config = LoggingConfig(
        level=data["logging"]["level"]
    )
    
    return Config(
        sources=sources_config,
        keywords=keywords_config,
        ai=ai_config,
        email=email_config,
        database=database_config,
        logging=logging_config
    )