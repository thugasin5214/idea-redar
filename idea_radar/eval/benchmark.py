"""Benchmark multiple models on the test set."""

import json
import time
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from idea_radar.config import Config
from idea_radar.models import Post, Category, Source
from idea_radar.classifier.ai_classifier import AIClassifier

console = Console()


def load_test_set() -> List[Dict[str, Any]]:
    """Load test set from JSONL file.
    
    Returns:
        List of test examples.
    """
    test_file = Path(__file__).parent / "test_set.jsonl"
    test_examples = []
    
    with open(test_file, 'r') as f:
        for line in f:
            if line.strip():
                test_examples.append(json.loads(line))
    
    return test_examples


def prepare_posts(test_examples: List[Dict[str, Any]]) -> List[Post]:
    """Convert test examples to Post objects.
    
    Args:
        test_examples: Raw test examples.
        
    Returns:
        List of Post objects.
    """
    posts = []
    for example in test_examples:
        post = Post(
            id=example["id"],
            source=Source.REDDIT if example["source"] == "reddit" else Source.INDIE_HACKERS,
            title=example["title"],
            body=example["body"],
            url=f"https://example.com/{example['id']}",
            author="test_user",
            score=100,
            num_comments=10,
            created_at=datetime.now(),
            subreddit="test" if example["source"] == "reddit" else None
        )
        posts.append(post)
    
    return posts


def calculate_metrics(predictions: List[Post], test_examples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate accuracy and per-category metrics.
    
    Args:
        predictions: Posts with predicted categories.
        test_examples: Original test examples with labels.
        
    Returns:
        Dictionary of metrics.
    """
    # Create mapping of id to label
    label_map = {ex["id"]: ex["label"] for ex in test_examples}
    
    # Track predictions and labels
    all_predictions = []
    all_labels = []
    
    # Per-category tracking
    category_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    
    for pred in predictions:
        true_label = label_map.get(pred.id)
        if true_label is None:
            continue
            
        pred_label = pred.category.value
        
        all_predictions.append(pred_label)
        all_labels.append(true_label)
        
        # Update category stats
        if pred_label == true_label:
            category_stats[pred_label]["tp"] += 1
        else:
            category_stats[pred_label]["fp"] += 1
            category_stats[true_label]["fn"] += 1
    
    # Calculate overall accuracy
    correct = sum(1 for p, l in zip(all_predictions, all_labels) if p == l)
    accuracy = correct / len(all_predictions) if all_predictions else 0
    
    # Calculate per-category metrics
    category_metrics = {}
    for category in ["pain_point", "idea", "project_launch", "lesson_learned", "noise"]:
        stats = category_stats[category]
        tp = stats["tp"]
        fp = stats["fp"]
        fn = stats["fn"]
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        category_metrics[category] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for l in all_labels if l == category)
        }
    
    return {
        "accuracy": accuracy,
        "total_examples": len(all_predictions),
        "correct": correct,
        "categories": category_metrics
    }


def run_benchmark(models: List[str], config: Config) -> Dict[str, Dict[str, Any]]:
    """Run benchmark on multiple models.
    
    Args:
        models: List of model names to test.
        config: Application configuration.
        
    Returns:
        Results dictionary with model performances.
    """
    # Load test set
    test_examples = load_test_set()
    posts = prepare_posts(test_examples)
    
    console.print(f"[bold cyan]Running benchmark on {len(test_examples)} test examples[/bold cyan]")
    console.print(f"Models to test: {', '.join(models)}\n")
    
    results = {}
    
    for model in models:
        console.print(f"[yellow]Testing model: {model}[/yellow]")
        
        # Create a temporary config with this model
        temp_config = config
        temp_config.ai.model = model
        
        # Initialize classifier
        classifier = AIClassifier(temp_config)
        
        # Run classification with timing
        start_time = time.time()
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Classifying with {model}...", total=None)
                predictions = classifier.classify_posts(posts.copy())
                progress.update(task, completed=True)
            
            elapsed_time = time.time() - start_time
            
            # Calculate metrics
            metrics = calculate_metrics(predictions, test_examples)
            metrics["time_seconds"] = elapsed_time
            metrics["model"] = model
            
            results[model] = metrics
            
            console.print(f"[green]✓ Completed in {elapsed_time:.2f}s[/green]")
            console.print(f"  Accuracy: {metrics['accuracy']:.2%}\n")
            
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]\n")
            results[model] = {
                "error": str(e),
                "model": model
            }
    
    return results


def print_report(results: Dict[str, Dict[str, Any]]) -> None:
    """Print a rich table comparing model performance.
    
    Args:
        results: Benchmark results dictionary.
    """
    console.print("\n[bold cyan]Benchmark Results[/bold cyan]\n")
    
    # Overall comparison table
    table = Table(title="Model Comparison", show_header=True)
    table.add_column("Model", style="cyan")
    table.add_column("Accuracy", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("Status", justify="center")
    
    for model, metrics in results.items():
        if "error" in metrics:
            table.add_row(
                model,
                "N/A",
                "N/A",
                "[red]Failed[/red]"
            )
        else:
            table.add_row(
                model,
                f"{metrics['accuracy']:.2%}",
                f"{metrics['time_seconds']:.2f}",
                "[green]Success[/green]"
            )
    
    console.print(table)
    
    # Per-category breakdown for successful models
    console.print("\n[bold cyan]Per-Category Performance[/bold cyan]\n")
    
    for model, metrics in results.items():
        if "error" in metrics:
            continue
            
        console.print(f"\n[yellow]{model}:[/yellow]")
        
        cat_table = Table(show_header=True)
        cat_table.add_column("Category", style="dim")
        cat_table.add_column("Precision", justify="right")
        cat_table.add_column("Recall", justify="right")
        cat_table.add_column("F1", justify="right")
        cat_table.add_column("Support", justify="right")
        
        for category in ["pain_point", "idea", "project_launch", "lesson_learned", "noise"]:
            if category in metrics["categories"]:
                cat_metrics = metrics["categories"][category]
                cat_table.add_row(
                    category,
                    f"{cat_metrics['precision']:.2f}",
                    f"{cat_metrics['recall']:.2f}",
                    f"{cat_metrics['f1']:.2f}",
                    str(cat_metrics['support'])
                )
        
        console.print(cat_table)
    
    # Best model summary
    successful_models = {m: r for m, r in results.items() if "error" not in r}
    if successful_models:
        best_model = max(successful_models.items(), key=lambda x: x[1]["accuracy"])
        console.print(f"\n[bold green]Best performing model: {best_model[0]} ({best_model[1]['accuracy']:.2%} accuracy)[/bold green]")


def export_results(results: Dict[str, Dict[str, Any]], output_path: str = "benchmark_results.json") -> None:
    """Export benchmark results to JSON file.
    
    Args:
        results: Benchmark results.
        output_path: Path to save results.
    """
    # Add timestamp
    for model_results in results.values():
        model_results["timestamp"] = datetime.now().isoformat()
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    console.print(f"[dim]Results saved to {output_path}[/dim]")