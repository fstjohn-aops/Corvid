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
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.text import Text

console = Console()
stderr_console = Console(stderr=True)

# US regions
REGIONS = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]

# Available sort columns
SORT_COLUMNS = {
    'instance_id': 'Instance ID', 
    'region': 'Region',
    'state': 'State',
    'name': 'Name',
    'key_name': 'Key Name'
}

def check_aws_environment():
    """Check for required AWS environment variables"""
    stderr_console.print("Checking for AWS environment vars:", style="bold blue")
    
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]
    optional_vars = ["AWS_SESSION_TOKEN"]
    
    all_good = True
    
    for var in required_vars:
        if os.getenv(var):
            stderr_console.print(f"  ✓ {var}", style="green")
        else:
            stderr_console.print(f"  ✗ {var} (missing)", style="red")
            all_good = False
    
    for var in optional_vars:
        if os.getenv(var):
            stderr_console.print(f"  ✓ {var} (optional)", style="green")
        else:
            stderr_console.print(f"  - {var} (optional, not set)", style="dim")
    
    return all_good

def get_instances_in_region(ec2_client, region):
    """Get all EC2 instances in a specific region"""
    try:
        response = ec2_client.describe_instances()
        instances = []
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                # Get instance name from tags
                instance_name = "N/A"
                if 'Tags' in instance:
                    for tag in instance['Tags']:
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']
                            break
                
                instances.append({
                    'instance_id': instance['InstanceId'],
                    'region': region,
                    'public_ip': instance.get('PublicIpAddress', 'N/A'),
                    'private_ip': instance.get('PrivateIpAddress', 'N/A'),
                    'state': instance['State']['Name'],
                    'name': instance_name,
                    'key_name': instance.get('KeyName', 'N/A')
                })
        
        return instances
    except ClientError as e:
        stderr_console.print(f"Error in region {region}: {e}", style="red")
        return []
    except Exception as e:
        stderr_console.print(f"Unexpected error in region {region}: {e}", style="red")
        return []

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Show EC2 instances across US regions')
    parser.add_argument('--sort', '-s', nargs='?', const='', metavar='COLUMN',
                       help='Sort by column. Use --sort to see available columns, or --sort COLUMN to sort by specific column')
    parser.add_argument('--search', '-q', metavar='QUERY',
                       help='Search for instances containing the query string (case-insensitive)')
    return parser.parse_args()

def get_sort_column():
    """Get the sort column from user input or arguments"""
    args = parse_arguments()
    
    # Default sort if no --sort flag
    if args.sort is None:
        return 'region'
    
    # If --sort with no value, show interactive selection
    if args.sort == '':
        stderr_console.print("\nAvailable sort columns:", style="bold blue")
        for key, description in SORT_COLUMNS.items():
            stderr_console.print(f"  {key}: {description}", style="dim")
        
        while True:
            choice = Prompt.ask("\nEnter column to sort by", choices=list(SORT_COLUMNS.keys()))
            if choice in SORT_COLUMNS:
                return choice
            stderr_console.print("Invalid choice, please try again", style="red")
    
    # If --sort with value, validate and return
    if args.sort in SORT_COLUMNS:
        return args.sort
    else:
        stderr_console.print(f"Invalid sort column: {args.sort}", style="red")
        stderr_console.print("Available columns:", style="dim")
        for key in SORT_COLUMNS.keys():
            stderr_console.print(f"  {key}", style="dim")
        sys.exit(1)

def highlight_matches(text, search_query):
    """Highlight search matches in text"""
    if not search_query:
        return text
    
    search_lower = search_query.lower()
    text_lower = text.lower()
    
    if search_lower not in text_lower:
        return text
    
    # Create rich text with highlighting
    rich_text = Text()
    start = 0
    
    while True:
        pos = text_lower.find(search_lower, start)
        if pos == -1:
            break
        
        # Add text before match
        rich_text.append(text[start:pos])
        
        # Add highlighted match
        rich_text.append(text[pos:pos + len(search_query)], style="bold yellow on red")
        
        start = pos + len(search_query)
    
    # Add remaining text
    rich_text.append(text[start:])
    
    return rich_text

def main():
    # Get arguments
    args = parse_arguments()
    sort_column = get_sort_column()
    search_query = args.search
    
    # Check AWS environment
    if not check_aws_environment():
        stderr_console.print("Missing required AWS environment variables", style="red")
        sys.exit(1)
    
    stderr_console.print("\nFetching EC2 instances across US regions...", style="bold blue")
    
    all_instances = []
    total_instances = 0
    
    # Process each region
    for region in REGIONS:
        stderr_console.print(f"\n=== Region: {region} ===", style="bold")
        
        try:
            ec2_client = boto3.client('ec2', region_name=region)
            instances = get_instances_in_region(ec2_client, region)
            
            if instances:
                all_instances.extend(instances)
                total_instances += len(instances)
                stderr_console.print(f"Found {len(instances)} instances", style="green")
            else:
                stderr_console.print("No instances found", style="dim")
                
        except NoCredentialsError:
            stderr_console.print("No AWS credentials found", style="red")
            sys.exit(1)
        except Exception as e:
            stderr_console.print(f"Error accessing region {region}: {e}", style="red")
    
    # Sort instances
    all_instances.sort(key=lambda x: x[sort_column])
    
    # Output all instances under a header
    header_text = f"Found instances (sorted by {SORT_COLUMNS[sort_column]})"
    if search_query:
        header_text += f" - searching for '{search_query}'"
    stderr_console.print(f"\n=== {header_text} ===", style="bold blue")
    
    # Print CSV header
    stderr_console.print("header row:", style="bold")
    print("account_role,instance_id,region,public_ip,private_ip,state,name,key_name")
    
    for instance in all_instances:
        # Create the CSV line
        csv_line = f"{os.getenv('AWS_PROFILE', 'default')},{instance['instance_id']},{instance['region']},{instance['public_ip']},{instance['private_ip']},{instance['state']},{instance['name']},{instance['key_name']}"
        
        if search_query:
            # Highlight matches and print to stderr for colored output
            highlighted_line = highlight_matches(csv_line, search_query)
            stderr_console.print(highlighted_line)
        else:
            # Normal output to stdout
            print(csv_line)
    
    # Summary
    stderr_console.print(f"\n=== Summary ===", style="bold blue")
    stderr_console.print(f"Total instances found: {total_instances}", style="green")
    stderr_console.print(f"Regions checked: {', '.join(REGIONS)}", style="dim")
    stderr_console.print(f"Sorted by: {SORT_COLUMNS[sort_column]}", style="dim")

if __name__ == "__main__":
    main() 