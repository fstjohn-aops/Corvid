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
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

console = Console()
stderr_console = Console(stderr=True)

# US regions
REGIONS = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]

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
                    'state': instance['State']['Name'],
                    'name': instance_name
                })
        
        return instances
    except ClientError as e:
        stderr_console.print(f"Error in region {region}: {e}", style="red")
        return []
    except Exception as e:
        stderr_console.print(f"Unexpected error in region {region}: {e}", style="red")
        return []

def display_instances(all_instances):
    """Display instances in a nice table"""
    if not all_instances:
        stderr_console.print("No instances found", style="yellow")
        return
    
    table = Table(title="Available EC2 Instances")
    table.add_column("Instance ID", style="cyan")
    table.add_column("Region", style="green")
    table.add_column("State", style="yellow")
    table.add_column("Name", style="white")
    
    for instance in all_instances:
        table.add_row(
            instance['instance_id'],
            instance['region'],
            instance['state'],
            instance['name']
        )
    
    console.print(table)

def select_instances(all_instances):
    """Let user select which instances to tag"""
    if not all_instances:
        return []
    
    stderr_console.print("\nSelect instances to tag:", style="bold blue")
    
    # Show numbered list
    for i, instance in enumerate(all_instances, 1):
        stderr_console.print(f"{i}. {instance['instance_id']} ({instance['region']}) - {instance['name']}")
    
    stderr_console.print("\nOptions:", style="bold")
    stderr_console.print("- Enter instance numbers separated by commas (e.g., 1,3,5)")
    stderr_console.print("- Enter 'all' to select all instances")
    stderr_console.print("- Enter 'none' to skip")
    
    while True:
        choice = Prompt.ask("\nYour selection")
        
        if choice.lower() == 'all':
            return all_instances
        elif choice.lower() == 'none':
            return []
        else:
            try:
                # Parse comma-separated numbers
                indices = [int(x.strip()) - 1 for x in choice.split(',')]
                selected = []
                
                for idx in indices:
                    if 0 <= idx < len(all_instances):
                        selected.append(all_instances[idx])
                    else:
                        stderr_console.print(f"Invalid index: {idx + 1}", style="red")
                
                if selected:
                    return selected
                else:
                    stderr_console.print("No valid instances selected", style="red")
            except ValueError:
                stderr_console.print("Invalid input. Please enter numbers separated by commas", style="red")

def get_tags_from_user():
    """Get tags from user input"""
    tags = {}
    
    stderr_console.print("\nEnter tags (key=value format):", style="bold blue")
    stderr_console.print("Enter 'done' when finished, or 'cancel' to abort")
    
    while True:
        tag_input = Prompt.ask("\nEnter tag (key=value)")
        
        if tag_input.lower() == 'done':
            break
        elif tag_input.lower() == 'cancel':
            return None
        
        if '=' in tag_input:
            key, value = tag_input.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            if key and value:
                tags[key] = value
                stderr_console.print(f"Added tag: {key} = {value}", style="green")
            else:
                stderr_console.print("Invalid tag format. Use key=value", style="red")
        else:
            stderr_console.print("Invalid format. Use key=value", style="red")
    
    return tags

def apply_tags_to_instances(selected_instances, tags):
    """Apply tags to selected instances"""
    if not selected_instances or not tags:
        return
    
    stderr_console.print(f"\nApplying {len(tags)} tags to {len(selected_instances)} instances...", style="bold blue")
    
    # Group instances by region for efficiency
    instances_by_region = {}
    for instance in selected_instances:
        region = instance['region']
        if region not in instances_by_region:
            instances_by_region[region] = []
        instances_by_region[region].append(instance)
    
    success_count = 0
    error_count = 0
    
    for region, instances in instances_by_region.items():
        stderr_console.print(f"\nProcessing region: {region}", style="bold")
        
        try:
            ec2_client = boto3.client('ec2', region_name=region)
            
            for instance in instances:
                try:
                    # Convert tags dict to boto3 format
                    tag_list = [{'Key': k, 'Value': v} for k, v in tags.items()]
                    
                    ec2_client.create_tags(
                        Resources=[instance['instance_id']],
                        Tags=tag_list
                    )
                    
                    stderr_console.print(f"✓ Tagged {instance['instance_id']} ({instance['name']})", style="green")
                    success_count += 1
                    
                except ClientError as e:
                    stderr_console.print(f"✗ Failed to tag {instance['instance_id']}: {e}", style="red")
                    error_count += 1
                except Exception as e:
                    stderr_console.print(f"✗ Unexpected error tagging {instance['instance_id']}: {e}", style="red")
                    error_count += 1
                    
        except Exception as e:
            stderr_console.print(f"Error accessing region {region}: {e}", style="red")
            error_count += len(instances)
    
    # Summary
    stderr_console.print(f"\n=== Summary ===", style="bold blue")
    stderr_console.print(f"Successfully tagged: {success_count} instances", style="green")
    if error_count > 0:
        stderr_console.print(f"Failed to tag: {error_count} instances", style="red")

def main():
    stderr_console.print("=== EC2 Tag Wizard ===", style="bold green")
    
    # Check AWS environment
    if not check_aws_environment():
        stderr_console.print("Missing required AWS environment variables", style="red")
        sys.exit(1)
    
    # Fetch instances
    stderr_console.print("\nFetching EC2 instances across US regions...", style="bold blue")
    
    all_instances = []
    for region in REGIONS:
        try:
            ec2_client = boto3.client('ec2', region_name=region)
            instances = get_instances_in_region(ec2_client, region)
            all_instances.extend(instances)
            
            if instances:
                stderr_console.print(f"Found {len(instances)} instances in {region}", style="green")
            else:
                stderr_console.print(f"No instances in {region}", style="dim")
                
        except NoCredentialsError:
            stderr_console.print("No AWS credentials found", style="red")
            sys.exit(1)
        except Exception as e:
            stderr_console.print(f"Error accessing region {region}: {e}", style="red")
    
    if not all_instances:
        stderr_console.print("No instances found in any region", style="yellow")
        return
    
    # Display instances
    display_instances(all_instances)
    
    # Select instances
    selected_instances = select_instances(all_instances)
    if not selected_instances:
        stderr_console.print("No instances selected. Exiting.", style="yellow")
        return
    
    stderr_console.print(f"\nSelected {len(selected_instances)} instances", style="green")
    
    # Get tags
    tags = get_tags_from_user()
    if tags is None:
        stderr_console.print("Tagging cancelled.", style="yellow")
        return
    
    if not tags:
        stderr_console.print("No tags entered. Exiting.", style="yellow")
        return
    
    # Confirm before applying
    stderr_console.print(f"\nAbout to apply {len(tags)} tags to {len(selected_instances)} instances:", style="bold yellow")
    for key, value in tags.items():
        stderr_console.print(f"  {key} = {value}")
    
    if not Confirm.ask("\nProceed with tagging?"):
        stderr_console.print("Tagging cancelled.", style="yellow")
        return
    
    # Apply tags
    apply_tags_to_instances(selected_instances, tags)
    
    stderr_console.print("\nTag wizard completed!", style="bold green")

if __name__ == "__main__":
    main()
