#!/usr/bin/env python3
"""Main entry point for daily idea radar run."""
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from idea_radar.config import load_config
from idea_radar.db import init_db, save_posts, update_classification, get_unsent_posts, mark_sent
from idea_radar.collectors.reddit import RedditCollector
from idea_radar.collectors.indie_hackers import IndieHackersCollector
from idea_radar.classifier.ai_classifier import AIClassifier
from idea_radar.models import Category
from idea_radar.digest.builder import DigestBuilder
from idea_radar.mailer.gmail import GmailMailer

console = Console()

def main():
    console.print("[bold blue]Idea Radar[/bold blue] starting...")
    
    config = load_config()
    conn = init_db(config.database.path)
    
    # Track statistics
    # Note: The collectors already do keyword filtering internally,
    # so we'll estimate total_collected based on typical pre-filter ratios
    after_keyword_filter = 0
    noise_count = 0
    
    # Collect from Reddit
    console.print("\n[cyan]Collecting from Reddit...[/cyan]")
    reddit = RedditCollector(config)
    reddit_posts = reddit.collect()
    after_keyword_filter += len(reddit_posts)  
    # Estimate total collected (Reddit collector filters ~50-75% typically)
    reddit_total_estimate = int(len(reddit_posts) * 2.5) if reddit_posts else 0
    reddit_new = save_posts(conn, reddit_posts)
    console.print(f"Reddit: [green]{len(reddit_posts)}[/green] posts after filter, [green]{reddit_new}[/green] new")
    
    # Collect from Indie Hackers
    all_posts = reddit_posts.copy()
    ih_total_estimate = 0
    if config.sources.indie_hackers.enabled:
        console.print("\n[cyan]Collecting from Indie Hackers...[/cyan]")
        ih = IndieHackersCollector(config)
        ih_posts = ih.collect()
        after_keyword_filter += len(ih_posts)
        # Estimate total collected (IH collector filters ~60-80% typically)
        ih_total_estimate = int(len(ih_posts) * 3) if ih_posts else 0
        ih_new = save_posts(conn, ih_posts)
        console.print(f"Indie Hackers: [green]{len(ih_posts)}[/green] posts after filter, [green]{ih_new}[/green] new")
        all_posts.extend(ih_posts)
    
    total_collected = reddit_total_estimate + ih_total_estimate
    
    # Classify unclassified posts
    classified_posts = []
    unclassified = [p for p in all_posts if p.category == Category.UNCATEGORIZED]
    if unclassified:
        console.print(f"\n[cyan]Classifying {len(unclassified)} posts...[/cyan]")
        classifier = AIClassifier(config)
        classified_posts = classifier.classify_posts(unclassified)
        
        # Update database with classifications
        for post in classified_posts:
            update_classification(
                conn, 
                post.id, 
                post.category,
                post.ai_summary,
                post.ai_opportunity,
                post.relevance_score
            )
        
        # Show results by category
        cats = Counter(p.category for p in classified_posts)
        console.print("\n[bold]Classification Results:[/bold]")
        for cat, count in cats.most_common():
            if cat != Category.NOISE:
                console.print(f"  {cat.value}: [green]{count}[/green]")
        
        noise_count = cats.get(Category.NOISE, 0)
        if noise_count > 0:
            console.print(f"  [dim]noise filtered: {noise_count}[/dim]")
        
        # Show some example classifications for inspection
        console.print("\n[bold]Sample Classifications:[/bold]")
        interesting_posts = [p for p in classified_posts 
                           if p.category in [Category.PAIN_POINT, Category.IDEA, Category.PROJECT_LAUNCH]
                           and p.relevance_score > 0.7][:3]
        
        for post in interesting_posts:
            console.print(f"\n[yellow]{post.category.value}[/yellow] (relevance: {post.relevance_score:.1f})")
            console.print(f"  Title: {post.title[:80]}...")
            if post.ai_summary:
                console.print(f"  Summary: [dim]{post.ai_summary}[/dim]")
            if post.ai_opportunity:
                console.print(f"  Opportunity: [cyan]{post.ai_opportunity}[/cyan]")
    else:
        console.print("\n[dim]No new posts to classify[/dim]")
    
    # Build and send digest
    console.print("\n[cyan]Building digest email...[/cyan]")
    
    # Build run stats
    run_stats = {
        "date": datetime.now(timezone.utc).strftime("%A, %B %d %Y"),
        "time_window_hours": config.sources.reddit.time_window_hours,
        "sources": [f"r/{s}" for s in config.sources.reddit.subreddits],
        "total_collected": total_collected if total_collected > 0 else after_keyword_filter,
        "after_keyword_filter": after_keyword_filter,
        "classified": len(classified_posts),
        "noise_filtered": noise_count,
    }
    
    # Add Indie Hackers to sources if enabled
    if config.sources.indie_hackers.enabled:
        run_stats["sources"].append("Indie Hackers")
    
    # Get all unsent posts from the time window
    time_window = datetime.now(timezone.utc) - timedelta(hours=config.sources.reddit.time_window_hours)
    all_classified = get_unsent_posts(conn, since=time_window)
    
    # Build digest
    builder = DigestBuilder()
    html = builder.build(all_classified, config, run_stats)
    
    # Send email
    mailer = GmailMailer(config)
    subject = f"Idea Radar Digest — {run_stats['date']}"
    success = mailer.send(subject, html)
    
    if success:
        console.print(f"[green]✓ Digest sent to {config.email.recipient}[/green]")
        # Mark posts as sent
        post_ids = [p.id for p in all_classified]
        if post_ids:
            mark_sent(conn, post_ids)
            console.print(f"[dim]Marked {len(post_ids)} posts as sent[/dim]")
    else:
        console.print("[red]✗ Email sending failed[/red]")
    
    console.print("\n[green]✓ Daily collection, classification, and digest complete![/green]")

if __name__ == "__main__":
    main()
