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
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()
stderr_console = Console(stderr=True)

# US regions (following the pattern from show-instances.py)
REGIONS = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Find NAT gateways across all AWS profiles')
    parser.add_argument('--limit', '-l', type=int, metavar='N',
                       help='Limit to first N profiles (default: all profiles)')
    parser.add_argument('--region', '-r', type=str, metavar='REGION',
                       help='Limit to specific region (default: all US regions)')
    parser.add_argument('--sort', '-s', type=str, 
                       choices=['creation_date', 'id', 'name', 'account', 'region'],
                       default='account',
                       help='Sort output by column (default: account)')
    return parser.parse_args()

def get_aws_profiles(limit=None):
    """Get AWS profiles from list-aws-profiles.py"""
    try:
        # Get the path to the list-aws-profiles.py script
        script_dir = Path(__file__).parent.parent / "host-management" / "scripts"
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

def get_nat_gateways_in_region(ec2_client, region):
    """Get all NAT gateways in a specific region"""
    try:
        response = ec2_client.describe_nat_gateways()
        nat_gateways = []
        
        for nat_gateway in response['NatGateways']:
            # Get NAT gateway name from tags
            nat_name = "N/A"
            if 'Tags' in nat_gateway:
                for tag in nat_gateway['Tags']:
                    if tag['Key'] == 'Name':
                        nat_name = tag['Value']
                        break
            
            nat_gateways.append({
                'id': nat_gateway['NatGatewayId'],
                'name': nat_name,
                'state': nat_gateway['State'],
                'region': region,
                'creation_date': nat_gateway['CreateTime'],
                'subnet_id': nat_gateway['SubnetId'],
                'vpc_id': nat_gateway['VpcId']
            })
        
        return nat_gateways
    except ClientError as e:
        stderr_console.print(f"Error in region {region}: {e}", style="red")
        return []
    except Exception as e:
        stderr_console.print(f"Unexpected error in region {region}: {e}", style="red")
        return []

def get_nat_gateways_for_profile(profile_name, regions_to_check):
    """Get NAT gateways for a specific AWS profile across specified regions"""
    try:
        # Set the profile for boto3
        session = boto3.Session(profile_name=profile_name)
        
        all_nat_gateways = []
        
        for region in regions_to_check:
            try:
                ec2_client = session.client('ec2', region_name=region)
                nat_gateways = get_nat_gateways_in_region(ec2_client, region)
                
                # Add profile name to each NAT gateway
                for nat_gateway in nat_gateways:
                    nat_gateway['account'] = profile_name
                
                all_nat_gateways.extend(nat_gateways)
                
                if nat_gateways:
                    stderr_console.print(f"  {region}: Found {len(nat_gateways)} NAT gateways", style="dim")
                else:
                    stderr_console.print(f"  {region}: No NAT gateways found", style="dim")
                    
            except Exception as e:
                stderr_console.print(f"  {region}: Error - {e}", style="red")
                continue
        
        return all_nat_gateways
        
    except Exception as e:
        stderr_console.print(f"Error processing profile {profile_name}: {e}", style="red")
        return []

def format_creation_date(creation_date):
    """Format the creation date for display"""
    if isinstance(creation_date, str):
        return creation_date
    return creation_date.strftime("%Y-%m-%d %H:%M:%S")

def print_csv_header():
    """Print CSV header row"""
    print("account,id,name,state,region,creation_date,subnet_id,vpc_id")

def print_csv_row(nat_gateway):
    """Print a single CSV row for a NAT gateway"""
    csv_line = f"{nat_gateway['account']},{nat_gateway['id']},{nat_gateway['name']},{nat_gateway['state']},{nat_gateway['region']},{format_creation_date(nat_gateway['creation_date'])},{nat_gateway['subnet_id']},{nat_gateway['vpc_id']}"
    print(csv_line)

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Determine regions to check
    if args.region:
        regions_to_check = [args.region]
        stderr_console.print(f"Limiting search to region: {args.region}", style="yellow")
    else:
        regions_to_check = REGIONS
        stderr_console.print(f"Searching across regions: {', '.join(REGIONS)}", style="blue")
    
    # Get AWS profiles dynamically
    accounts = get_aws_profiles(args.limit)
    
    if not accounts:
        stderr_console.print("No AWS profiles found. Exiting.", style="red")
        sys.exit(1)
    
    stderr_console.print(f"\nSearching for NAT gateways across {len(accounts)} AWS profiles...", style="bold blue")
    
    all_nat_gateways = []
    total_nat_gateways = 0
    
    # Process each profile
    for i, account in enumerate(accounts, 1):
        stderr_console.print(f"\n[{i}/{len(accounts)}] Processing profile: {account}", style="bold")
        
        nat_gateways = get_nat_gateways_for_profile(account, regions_to_check)
        
        if nat_gateways:
            all_nat_gateways.extend(nat_gateways)
            total_nat_gateways += len(nat_gateways)
            stderr_console.print(f"  Total NAT gateways for {account}: {len(nat_gateways)}", style="green")
        else:
            stderr_console.print(f"  No NAT gateways found for {account}", style="dim")
    
    # Sort NAT gateways
    if args.sort == 'creation_date':
        all_nat_gateways.sort(key=lambda x: x['creation_date'])
    elif args.sort == 'id':
        all_nat_gateways.sort(key=lambda x: x['id'])
    elif args.sort == 'name':
        all_nat_gateways.sort(key=lambda x: x['name'])
    elif args.sort == 'region':
        all_nat_gateways.sort(key=lambda x: x['region'])
    else:  # account (default)
        all_nat_gateways.sort(key=lambda x: x['account'])
    
    # Print results
    stderr_console.print(f"\n=== Results (sorted by {args.sort}) ===", style="bold blue")
    
    if all_nat_gateways:
        # Print CSV header
        stderr_console.print("Printing CSV header", style="bold")
        print_csv_header()
        
        # Print each NAT gateway
        for nat_gateway in all_nat_gateways:
            print_csv_row(nat_gateway)
        
        # Summary
        stderr_console.print(f"\n=== Summary ===", style="bold blue")
        stderr_console.print(f"Total NAT gateways found: {total_nat_gateways}", style="green")
        stderr_console.print(f"Profiles checked: {len(accounts)}", style="dim")
        stderr_console.print(f"Regions checked: {', '.join(regions_to_check)}", style="dim")
        stderr_console.print(f"Sorted by: {args.sort}", style="dim")
    else:
        stderr_console.print("No NAT gateways found across all profiles and regions.", style="yellow")

if __name__ == "__main__":
    main()
