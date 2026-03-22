"""AI classifier using OpenRouter API to classify posts."""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console

from idea_radar.config import Config
from idea_radar.models import Post, Category

logger = logging.getLogger(__name__)
console = Console()


class AIClassifier:
    """Classify posts using OpenRouter API (OpenAI-compatible)."""
    
    def __init__(self, config: Config):
        """Initialize the AI classifier.
        
        Args:
            config: Application configuration.
        """
        self.config = config  # keep full config for prompt access
        self.client = OpenAI(
            api_key=config.ai.api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = config.ai.model
        self.fallback_model = config.ai.fallback_model
        self.batch_size = config.ai.batch_size
        
    def classify_posts(self, posts: List[Post]) -> List[Post]:
        """Classify all posts in batches.
        
        Args:
            posts: List of posts to classify.
            
        Returns:
            Posts with category/summary filled.
        """
        if not posts:
            return []
            
        classified = []
        total_batches = (len(posts) + self.batch_size - 1) // self.batch_size
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(
                f"[cyan]Classifying {len(posts)} posts in {total_batches} batches...[/cyan]",
                total=len(posts)
            )
            
            for i in range(0, len(posts), self.batch_size):
                batch = posts[i:i + self.batch_size]
                try:
                    batch_results = self.classify_batch(batch)
                    classified.extend(batch_results)
                    progress.update(task, advance=len(batch))
                except Exception as e:
                    logger.error(f"Batch classification failed: {e}")
                    # Fall back to one-by-one classification
                    for post in batch:
                        try:
                            single_result = self.classify_batch([post])
                            classified.extend(single_result)
                        except Exception as e2:
                            logger.error(f"Single post classification failed for {post.id}: {e2}")
                            # Keep original post with uncategorized
                            classified.append(post)
                        progress.update(task, advance=1)
        
        return classified
    
    def classify_batch(self, batch: List[Post], use_fallback: bool = False) -> List[Post]:
        """Classify a single batch via one LLM call.
        
        Args:
            batch: Posts to classify in this batch.
            use_fallback: Whether to use the fallback model.
            
        Returns:
            Classified posts.
        """
        prompt = self._build_prompt(batch)
        model = self.fallback_model if use_fallback else self.model
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing community discussions and extracting insights. Classify each post accurately based on the given categories."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            return self._parse_response(response_text, batch)
            
        except Exception as e:
            if not use_fallback and self.fallback_model:
                logger.warning(f"Primary model failed, trying fallback: {e}")
                return self.classify_batch(batch, use_fallback=True)
            raise
    
    def _build_prompt(self, batch: List[Post]) -> str:
        """Build classification prompt for a batch.
        
        Args:
            batch: Posts to include in prompt.
            
        Returns:
            Formatted prompt string.
        """
        prompt_cfg = self.config.ai.prompt
        
        # Build categories description from config
        categories_text = "\n".join(
            f"- {cat}: {desc}" 
            for cat, desc in prompt_cfg.categories.items()
        )
        
        # Build posts text
        posts_text = "\n\n".join(
            f"[{i+1}] Title: {p.title}\nBody: {p.body[:500]}\nSource: {p.source.value}/{p.subreddit or 'general'}"
            for i, p in enumerate(batch)
        )
        
        extra = f"\n\nAdditional instructions: {prompt_cfg.extra_instructions}" if prompt_cfg.extra_instructions else ""
        
        return f"""You are analyzing {prompt_cfg.focus}.

Categories:
{categories_text}
{extra}

For each post return JSON with:
- category: one of {list(prompt_cfg.categories.keys())}
- relevance_score: 0.0-1.0
- ai_summary: 1-2 sentence summary
- ai_opportunity: if pain_point or idea, describe the product opportunity; otherwise null

Posts to classify:
{posts_text}

Return ONLY a valid JSON array:
[{{"index": 1, "category": "...", "relevance_score": 0.0, "ai_summary": "...", "ai_opportunity": null}}, ...]"""
    
    def _parse_response(self, response_text: str, batch: List[Post]) -> List[Post]:
        """Parse JSON response and update Post objects.
        
        Args:
            response_text: Raw response from LLM.
            batch: Original posts to update.
            
        Returns:
            Updated posts.
        """
        # Try to extract JSON from response
        json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON array found in response")
        
        try:
            results = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            # Try to clean up common issues
            cleaned = response_text.replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false")
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', cleaned, re.DOTALL)
            if json_match:
                results = json.loads(json_match.group())
            else:
                raise
        
        # Create a map of results by index
        result_map: Dict[int, Dict[str, Any]] = {}
        for result in results:
            if "index" in result:
                result_map[result["index"]] = result
        
        # Update posts
        updated_posts = []
        for i, post in enumerate(batch, 1):
            if i in result_map:
                result = result_map[i]
                try:
                    # Update category
                    category_str = result.get("category", "uncategorized")
                    post.category = Category(category_str) if category_str in [c.value for c in Category] else Category.UNCATEGORIZED
                    
                    # Update other fields
                    post.ai_summary = result.get("ai_summary", "")
                    post.ai_opportunity = result.get("ai_opportunity", None)
                    post.relevance_score = float(result.get("relevance_score", 0.0))
                    
                    # Clamp relevance score
                    post.relevance_score = max(0.0, min(1.0, post.relevance_score))
                    
                except Exception as e:
                    logger.error(f"Failed to update post {post.id}: {e}")
            
            updated_posts.append(post)
        
        return updated_posts