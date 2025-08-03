#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=13.0.0",
# ]
# ///

import sys
import os
import subprocess
import argparse
from pathlib import Path
from rich.console import Console

console = Console()

DEFAULT_KEY_FILE = "/Users/finnstjohn/.ssh/id_ed25519_devops.pub"
DEFAULT_REGION = "us-west-2"
DEFAULT_USERS = "ec2-user,ubuntu"

def main():
    parser = argparse.ArgumentParser(description="Push SSH key to EC2 instance")
    parser.add_argument("aws_role", help="AWS role to assume")
    parser.add_argument("instance_id", help="EC2 instance ID")
    parser.add_argument("--region", default=DEFAULT_REGION, help=f"AWS region (default: {DEFAULT_REGION})")
    parser.add_argument("--key-file", default=DEFAULT_KEY_FILE, help=f"SSH public key file (default: {DEFAULT_KEY_FILE})")
    parser.add_argument("--users", default=DEFAULT_USERS, help=f"Comma-separated list of users to try (default: {DEFAULT_USERS})")
    
    args = parser.parse_args()
    
    aws_role = args.aws_role
    instance_id = args.instance_id
    region = args.region
    key_file = args.key_file
    possible_users = [user.strip() for user in args.users.split(",")]

    # Convert to absolute path if it's a relative path
    if not os.path.isabs(key_file):
        key_file = str(Path.cwd() / key_file)

    # Validate that the key file exists
    if not os.path.isfile(key_file):
        print(f"Error: Key file '{key_file}' does not exist")
        sys.exit(1)

    # print the arguments
    console.print(f"aws_role: {aws_role}", style="dim")
    console.print(f"instance_id: {instance_id}", style="dim")
    console.print(f"region: {region}", style="dim")
    console.print(f"key_file: {key_file}", style="dim")
    console.print(f"users: {possible_users}", style="dim")

    # Push ssh key to instance
    for user in possible_users:
        console.print(f"Pushing key for user: {user}", style="dim")
        
        try:
            # Set environment variable and run the command
            env = os.environ.copy()
            env["FORCE_NO_ALIAS"] = "true"
            
            cmd = [
                "assume", aws_role, "--exec", "--", "aws", "ec2-instance-connect", "send-ssh-public-key",
                "--instance-id", instance_id,
                "--region", region,
                "--instance-os-user", user,
                f"--ssh-public-key=file://{key_file}"
            ]
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print(f"✓ Successfully pushed key for user: {user}", style="green")
                # break  # Exit loop on first success
            else:
                console.print(f"✗ Failed to push key for user: {user}", style="dim")
                
        except Exception as e:
            console.print(f"✗ Failed to push key for user: {user}", style="dim")
            console.print(f"Error: {e}", style="dim")

if __name__ == "__main__":
    main() 