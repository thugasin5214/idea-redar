#!/usr/bin/env python3
"""Run benchmark evaluation across models."""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from idea_radar.config import load_config
from idea_radar.eval.benchmark import run_benchmark, print_report, export_results

console = Console()

# Default models to test
DEFAULT_MODELS = [
    "qwen/qwen-2.5-72b-instruct:free",
    "google/gemini-flash-1.5:free",
    "meta-llama/llama-3.1-70b-instruct:free"
]


def main():
    parser = argparse.ArgumentParser(description="Run classifier benchmark evaluation")
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="Models to test (default: qwen, gemini-flash, llama-3.1)"
    )
    parser.add_argument(
        "--export",
        type=str,
        default="benchmark_results.json",
        help="Path to export results JSON (default: benchmark_results.json)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config file (default: config.yaml)"
    )
    
    args = parser.parse_args()
    
    console.print("[bold blue]Idea Radar Classifier Benchmark[/bold blue]")
    console.print("[dim]Loading configuration...[/dim]\n")
    
    try:
        # Load config
        config = load_config(args.config)
        
        # Run benchmark
        results = run_benchmark(args.models, config)
        
        # Print report
        print_report(results)
        
        # Export results
        if args.export:
            export_results(results, args.export)
            
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure config.yaml exists. Copy config.example.yaml and fill in your API keys.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Benchmark failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()