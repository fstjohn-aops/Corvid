#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas>=2.0.0",
#   "rich>=13.0.0",
# ]
# ///

import sys
import os
import argparse
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()
stderr_console = Console(stderr=True)

def load_csv_data(csv_path):
    """Load and validate CSV data"""
    try:
        stderr_console.print(f"Loading CSV from: {csv_path}", style="bold blue")
        
        # Read the CSV file
        df = pd.read_csv(csv_path)
        
        stderr_console.print(f"Successfully loaded CSV with {len(df)} rows and {len(df.columns)} columns", style="green")
        
        return df
    except FileNotFoundError:
        stderr_console.print(f"Error: CSV file not found at {csv_path}", style="red")
        
        # If this is the default file, provide helpful guidance
        if csv_path.name == 'all_hosts.csv':
            stderr_console.print("\n[bold yellow]To generate the CSV file, run:[/bold yellow]")
            stderr_console.print("  [cyan]./scripts/find-ec2.py > files/all_hosts.csv[/cyan]", style="bold")
            stderr_console.print("\nOr specify a different CSV file with --csv option", style="dim")
        
        sys.exit(1)
    except Exception as e:
        stderr_console.print(f"Error loading CSV: {e}", style="red")
        sys.exit(1)

def display_basic_stats(df):
    """Display basic statistics about the CSV data"""
    console.print("\n[bold cyan]Basic Statistics:[/bold cyan]")
    
    # Create a table for basic stats
    table = Table(title="Host Data Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Rows", str(len(df)))
    table.add_row("Total Columns", str(len(df.columns)))
    table.add_row("Memory Usage", f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB")
    
    console.print(table)
    
    # Show column information
    console.print("\n[bold cyan]Columns:[/bold cyan]")
    for i, col in enumerate(df.columns, 1):
        console.print(f"  {i}. {col}")

def display_key_analysis(df):
    """Display analysis of the key_name column"""
    console.print("\n[bold cyan]Key Name Analysis:[/bold cyan]")
    
    # Get key name counts
    key_counts = df['key_name'].value_counts()
    unique_keys = len(key_counts)
    
    # Create summary table
    summary_table = Table(title="Key Name Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Unique Keys", str(unique_keys))
    summary_table.add_row("Total Hosts", str(len(df)))
    
    console.print(summary_table)
    
    # Create detailed breakdown table
    console.print(f"\n[bold cyan]Key Name Breakdown ({unique_keys} unique keys):[/bold cyan]")
    breakdown_table = Table(title="Key Name Counts")
    breakdown_table.add_column("Key Name", style="cyan")
    breakdown_table.add_column("Count", style="green", justify="right")
    breakdown_table.add_column("Percentage", style="yellow", justify="right")
    
    total_hosts = len(df)
    for key_name, count in key_counts.items():
        percentage = (count / total_hosts) * 100
        breakdown_table.add_row(
            str(key_name) if pd.notna(key_name) else "N/A",
            str(count),
            f"{percentage:.1f}%"
        )
    
    console.print(breakdown_table)

def display_region_analysis(df):
    """Display analysis of the region column"""
    console.print("\n[bold cyan]Region Analysis:[/bold cyan]")
    
    # Get region counts
    region_counts = df['region'].value_counts()
    unique_regions = len(region_counts)
    
    # Create summary table
    summary_table = Table(title="Region Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Unique Regions", str(unique_regions))
    summary_table.add_row("Total Hosts", str(len(df)))
    
    console.print(summary_table)
    
    # Create detailed breakdown table
    console.print(f"\n[bold cyan]Region Breakdown ({unique_regions} unique regions):[/bold cyan]")
    breakdown_table = Table(title="Region Counts")
    breakdown_table.add_column("Region", style="cyan")
    breakdown_table.add_column("Count", style="green", justify="right")
    breakdown_table.add_column("Percentage", style="yellow", justify="right")
    
    total_hosts = len(df)
    for region, count in region_counts.items():
        percentage = (count / total_hosts) * 100
        breakdown_table.add_row(
            str(region) if pd.notna(region) else "N/A",
            str(count),
            f"{percentage:.1f}%"
        )
    
    console.print(breakdown_table)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Analyze hosts CSV file')
    parser.add_argument('--csv', '-f', default='files/all_hosts.csv',
                       help='Path to CSV file (default: files/all_hosts.csv)')
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Basic stats command (default)
    subparsers.add_parser('default', help='Show basic statistics (default)')
    
    # Key analysis command
    subparsers.add_parser('keys', help='Analyze key_name column')
    
    # Region analysis command
    subparsers.add_parser('regions', help='Analyze region column')
    
    return parser.parse_args()

def main():
    # Get arguments
    args = parse_arguments()
    
    # Resolve CSV path
    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = Path.cwd() / csv_path
    
    # Load the CSV data
    df = load_csv_data(csv_path)
    
    # Default to stats if no command provided
    command = args.command or 'default'
    
    if command == 'default':
        display_basic_stats(df)
    elif command == 'keys':
        display_key_analysis(df)
    elif command == 'regions':
        display_region_analysis(df)
    else:
        stderr_console.print(f"Unknown command: {command}", style="red")
        sys.exit(1)
    
    stderr_console.print("\nAnalysis complete!", style="bold green")

if __name__ == "__main__":
    main() 