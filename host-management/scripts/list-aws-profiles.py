#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=13.0.0",
# ]
# ///

import sys
import os
from pathlib import Path
from rich.console import Console

console = Console()
stderr_console = Console(stderr=True)

# Set the role filter - change this to filter for different roles
ROLE_FILTER = "AWSAdministratorAccess"

def main():
    config_file = Path.home() / ".aws" / "config"
    
    if not config_file.exists():
        stderr_console.print(f"Error: AWS config file not found at {config_file}", style="red")
        sys.exit(1)
    
    # Print info to stderr (won't be redirected)
    stderr_console.print(f"Reading AWS profiles from {config_file}", style="dim")
    stderr_console.print(f"Filtering for profiles containing: {ROLE_FILTER}", style="dim")
    
    # Extract profile names from the config file
    # Look for lines that start with [profile and extract the profile name
    # Filter to only include profiles that match the ROLE_FILTER
    try:
        profile_count = 0
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('[profile '):
                    # Extract profile name from [profile name] format
                    profile_name = line[9:-1]  # Remove '[profile ' and ']'
                    if ROLE_FILTER in profile_name:
                        print(profile_name)  # Use print() for stdout (will be redirected)
                        profile_count += 1
        
        stderr_console.print(f"Found {profile_count} profiles containing '{ROLE_FILTER}'", style="green")
    except Exception as e:
        stderr_console.print(f"Error reading config file: {e}", style="red")
        sys.exit(1)

if __name__ == "__main__":
    main() 