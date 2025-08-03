#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "boto3>=1.26.0",
#   "rich>=13.0.0",
# ]
# ///

import sys
import os
import argparse
import subprocess
from pathlib import Path
from rich.console import Console

console = Console()
stderr_console = Console(stderr=True)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Find bastion hosts across AWS accounts')
    parser.add_argument('--limit', '-l', type=int, metavar='N',
                       help='Limit to first N profiles (default: all profiles)')
    parser.add_argument('--search', '-s', type=str, default='i-',
                       help='Comma-separated list of substrings to search for (default: empty string - all instances)')
    parser.add_argument('--sort', type=str, choices=['account_role', 'instance_id', 'region', 'public_ip', 'private_ip', 'state', 'name', 'key_name'],
                       help='Sort output by column')
    return parser.parse_args()

def get_aws_profiles(limit=None):
    """Get AWS profiles from list-aws-profiles.py"""
    try:
        # Get the path to the list-aws-profiles.py script
        script_dir = Path(__file__).parent
        list_profiles_script = script_dir / "list-aws-profiles.py"
        
        if not list_profiles_script.exists():
            stderr_console.print(f"Error: list-aws-profiles.py not found at {list_profiles_script}", style="red")
            return []
        
        # Run the list-aws-profiles.py script
        result = subprocess.run(
            [sys.executable, str(list_profiles_script)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Parse the output and return list of profiles
            profiles = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            
            # Apply limit if specified
            if limit and limit > 0:
                profiles = profiles[:limit]
                stderr_console.print(f"Limited to first {limit} profiles", style="yellow")
            
            stderr_console.print(f"Found {len(profiles)} AWS profiles", style="green")
            return profiles
        else:
            stderr_console.print(f"Error running list-aws-profiles.py: {result.stderr}", style="red")
            return []
            
    except Exception as e:
        stderr_console.print(f"Error getting AWS profiles: {e}", style="red")
        return []

def run_show_instances_script(account, search_terms, sort_column=None):
    """Run the show-instances.py script for a given account and filter for search terms"""
    try:
        # Get the path to the show-instances.py script
        script_dir = Path(__file__).parent
        show_instances_script = script_dir / "show-instances.py"
        
        if not show_instances_script.exists():
            stderr_console.print(f"Error: show-instances.py not found at {show_instances_script}", style="red")
            return []
        
        # Set environment variable and run the command
        env = os.environ.copy()
        env["FORCE_NO_ALIAS"] = "true"
        
        cmd = ["assume", account, "--exec", "--", "python", str(show_instances_script)]
        
        # Add sort argument if specified
        if sort_column:
            cmd.extend(["--sort", sort_column])
        
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Filter lines containing any of the search terms (case-insensitive)
            filtered_lines = []
            for line in result.stdout.splitlines():
                # Skip header row
                if line.startswith("account_role,instance_id,region,public_ip,private_ip,state,name,key_name"):
                    continue
                    
                line_lower = line.lower()
                if any(term.strip().lower() in line_lower for term in search_terms):
                    # Replace the account_role field with the actual account being queried
                    parts = line.split(',')
                    if len(parts) >= 7:
                        # Replace first field (account_role) with the actual account
                        parts[0] = account
                        filtered_lines.append(','.join(parts))
            return filtered_lines
        else:
            stderr_console.print(f"Error running show-instances.py for {account}: {result.stderr}", style="red")
            return []
            
    except Exception as e:
        stderr_console.print(f"Error processing account {account}: {e}", style="red")
        return []

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Parse search terms
    search_terms = [term.strip() for term in args.search.split(',')]
    stderr_console.print(f"Searching for instances containing: {', '.join(search_terms)}", style="blue")
    
    # Get AWS profiles dynamically
    accounts = get_aws_profiles(args.limit)
    
    if not accounts:
        stderr_console.print("No AWS profiles found. Exiting.", style="red")
        sys.exit(1)
    
    # Print CSV header
    stderr_console.print("Printing header row", style="bold")
    print("account_role,instance_id,region,public_ip,private_ip,state,name,key_name")
    
    # Process each account
    for account in accounts:
        stderr_console.print(f"Processing account: {account}", style="dim")
        results = run_show_instances_script(account, search_terms, args.sort)
        
        for result in results:
            print(result)

if __name__ == "__main__":
    main()