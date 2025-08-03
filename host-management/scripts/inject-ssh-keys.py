#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas>=2.0.0",
#   "rich>=13.0.0",
#   "pyyaml>=6.0",
# ]
# ///

import sys
import os
import argparse
import subprocess
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

console = Console()
stderr_console = Console(stderr=True)

# Default exclude patterns for production instances
DEFAULT_EXCLUDE_PATTERNS = [
    "prod",
    "production", 
    "live",
    "bastionhost"
]

# Default users to inject SSH keys for
# DEFAULT_USERS_TO_INJECT = ["ec2-user", "cloud-user", "ubuntu", "ansiblecontrol", "website", "root"]
DEFAULT_USERS_TO_INJECT = ["ansiblecontrol"]

class EC2InstanceConnectManager:
    """Manages EC2 Instance Connect operations"""
    
    @staticmethod
    def push_temp_key(aws_role: str, instance_id: str, region: str, ssh_key_file: str, user: str) -> bool:
        """Push temporary SSH key using EC2 Instance Connect"""
        try:
            script_dir = Path(__file__).parent
            push_script = script_dir / "push-ssh-key-to-instance.py"
            
            if not push_script.exists():
                stderr_console.print(f"Error: push-ssh-key-to-instance.py not found at {push_script}", style="red")
                return False
            
            cmd = [
                sys.executable, str(push_script),
                aws_role, instance_id,
                "--region", region,
                "--key-file", f"{ssh_key_file}.pub",
                "--users", user
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                stderr_console.print(f"    ✓ Successfully pushed temp key for user: {user}", style="green")
                return True
            else:
                # Clean up error message
                error_msg = result.stderr.strip()
                import re
                error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
                
                # Extract meaningful error
                if "access denied" in error_msg.lower():
                    error_msg = "Access denied - check AWS permissions"
                elif "not found" in error_msg.lower():
                    error_msg = "Instance not found or not accessible"
                else:
                    lines = [line.strip() for line in error_msg.split('\n') if line.strip()]
                    error_msg = lines[-1] if lines else "Unknown error"
                
                stderr_console.print(f"    ✗ Failed to push temp key: {error_msg}", style="red")
                return False
                
        except Exception as e:
            stderr_console.print(f"Error pushing temp SSH key: {e}", style="red")
            return False
    
    @staticmethod
    def inject_key_via_temp_ssh(instance_id: str, user: str, public_ip: str, pub_key_content: str, ssh_key_file: str) -> bool:
        """Inject SSH key using temporary SSH connection"""
        try:
            # Define the SSH commands to run
            ssh_commands = [
                ("Create .ssh directory", f"mkdir -p ~/.ssh"),
                ("Check if key exists", f"grep -F '{pub_key_content}' ~/.ssh/authorized_keys 2>/dev/null || echo 'not_found'"),
                ("Add SSH key", f"echo '{pub_key_content}' >> ~/.ssh/authorized_keys"),
                ("Set permissions", "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys")
            ]
            
            for step_name, command in ssh_commands:
                ssh_cmd = [
                    "ssh", "-i", ssh_key_file,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "ConnectTimeout=10",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"{user}@{public_ip}",
                    command
                ]
                
                result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    # Clean up error message
                    error_msg = result.stderr.strip()
                    import re
                    error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
                    
                    # Extract meaningful error
                    if "connection refused" in error_msg.lower():
                        error_msg = "Connection refused - SSH service may not be running"
                    elif "timeout" in error_msg.lower():
                        error_msg = "Connection timed out"
                    elif "permission denied" in error_msg.lower():
                        error_msg = "Permission denied - temporary key may have expired"
                    else:
                        lines = [line.strip() for line in error_msg.split('\n') if line.strip()]
                        error_msg = lines[-1] if lines else "Unknown error"
                    
                    stderr_console.print(f"    ✗ Failed to {step_name.lower()}: {error_msg}", style="red")
                    return False
                
                # Special handling for the "check if key exists" step
                if step_name == "Check if key exists" and "not_found" not in result.stdout:
                    stderr_console.print("✓ SSH key already exists in authorized_keys", style="green")
                    return True
                
                # Skip the "Add SSH key" step if key already exists
                if step_name == "Add SSH key" and "not_found" not in result.stdout:
                    continue
            
            stderr_console.print("✓ Successfully injected SSH key via temp SSH", style="green")
            return True
                
        except subprocess.TimeoutExpired:
            stderr_console.print("✗ SSH injection timed out", style="red")
            return False
        except Exception as e:
            stderr_console.print(f"Error injecting SSH key via temp SSH: {e}", style="red")
            return False

class SSHKeyInjector:
    """Main class for SSH key injection operations"""
    
    def __init__(self, ssh_key_file: str, existing_key_file: Optional[str] = None):
        self.ssh_key_file = ssh_key_file
        self.existing_key_file = existing_key_file
        self.pub_key_content = self._load_public_key()
        self.ec2_manager = EC2InstanceConnectManager()
    
    def _load_public_key(self) -> str:
        """Load the public key content"""
        pub_key_path = f"{self.ssh_key_file}.pub"
        if not os.path.exists(pub_key_path):
            stderr_console.print(f"Error: Public key file not found: {pub_key_path}", style="red")
            sys.exit(1)
        
        with open(pub_key_path, 'r') as f:
            return f.read().strip()
    
    def inject_key_to_host_all_users(self, host: pd.Series) -> Tuple[bool, Optional[str]]:
        """Inject SSH key to a host for all users using EC2 Instance Connect or existing key"""
        instance_id = host['instance_id']
        account_role = host['account_role']
        region = host['region']
        public_ip = host.get('public_ip', 'N/A')
        
        # If existing key is provided, use direct SSH method
        if self.existing_key_file:
            return self._inject_key_via_existing_key(host)
        
        # Otherwise use EC2 Instance Connect method
        stderr_console.print("  Using EC2 Instance Connect for temporary key injection...", style="blue")
        for user in DEFAULT_USERS_TO_INJECT:
            stderr_console.print(f"    Processing user: {user}", style="dim")
            
            # Push temporary key
            if not self.ec2_manager.push_temp_key(account_role, instance_id, region, self.ssh_key_file, user):
                stderr_console.print(f"    ✗ Failed to push temp key for user: {user}", style="red")
                continue
            
            # Inject key via temporary SSH
            if not self.ec2_manager.inject_key_via_temp_ssh(instance_id, user, public_ip, self.pub_key_content, self.ssh_key_file):
                stderr_console.print(f"    ✗ Failed to inject SSH key for user: {user}", style="red")
                continue
            
            # Test SSH connection
            if not self.test_ssh_connection(user, public_ip):
                stderr_console.print(f"    ✗ Failed SSH connection test for user: {user}", style="red")
                continue
            
            # Success!
            stderr_console.print(f"    ✓ Successfully processed user: {user}", style="green")
            return True, user
        
        return False, None
    
    def _inject_key_via_existing_key(self, host: pd.Series) -> Tuple[bool, Optional[str]]:
        """Inject SSH key using existing SSH key (bypasses EC2 Instance Connect)"""
        public_ip = host.get('public_ip', 'N/A')
        
        stderr_console.print("  Using existing SSH key for direct connection...", style="blue")
        for user in DEFAULT_USERS_TO_INJECT:
            stderr_console.print(f"    Processing user: {user}", style="dim")
            
            # Try to inject key directly via existing SSH connection
            if not self._inject_key_via_direct_ssh(user, public_ip):
                stderr_console.print(f"    ✗ Failed to inject SSH key for user: {user}", style="red")
                continue
            
            # Test SSH connection with the new key
            if not self.test_ssh_connection(user, public_ip):
                stderr_console.print(f"    ✗ Failed SSH connection test for user: {user}", style="red")
                continue
            
            # Success!
            stderr_console.print(f"    ✓ Successfully processed user: {user}", style="green")
            return True, user
        
        return False, None
    
    def _inject_key_via_direct_ssh(self, user: str, public_ip: str) -> bool:
        """Inject SSH key using existing SSH connection"""
        try:
            # Define the SSH commands to run
            ssh_commands = [
                ("Create .ssh directory", f"mkdir -p ~/.ssh"),
                ("Check if key exists", f"grep -F '{self.pub_key_content}' ~/.ssh/authorized_keys 2>/dev/null || echo 'not_found'"),
                ("Add SSH key", f"echo '{self.pub_key_content}' >> ~/.ssh/authorized_keys"),
                ("Set permissions", "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys")
            ]
            
            for step_name, command in ssh_commands:
                ssh_cmd = [
                    "ssh", "-i", self.existing_key_file,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "ConnectTimeout=10",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"{user}@{public_ip}",
                    command
                ]
                
                result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    # Clean up error message
                    error_msg = result.stderr.strip()
                    import re
                    error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
                    
                    # Extract meaningful error
                    if "connection refused" in error_msg.lower():
                        error_msg = "Connection refused - SSH service may not be running"
                    elif "timeout" in error_msg.lower():
                        error_msg = "Connection timed out"
                    elif "permission denied" in error_msg.lower():
                        error_msg = "Permission denied - check existing key permissions"
                    else:
                        lines = [line.strip() for line in error_msg.split('\n') if line.strip()]
                        error_msg = lines[-1] if lines else "Unknown error"
                    
                    stderr_console.print(f"    ✗ Failed to {step_name.lower()}: {error_msg}", style="red")
                    return False
                
                # Special handling for the "check if key exists" step
                if step_name == "Check if key exists" and "not_found" not in result.stdout:
                    stderr_console.print("✓ SSH key already exists in authorized_keys", style="green")
                    return True
                
                # Skip the "Add SSH key" step if key already exists
                if step_name == "Add SSH key" and "not_found" not in result.stdout:
                    continue
            
            stderr_console.print("✓ Successfully injected SSH key via existing SSH connection", style="green")
            return True
                
        except subprocess.TimeoutExpired:
            stderr_console.print("✗ SSH injection timed out", style="red")
            return False
        except Exception as e:
            stderr_console.print(f"Error injecting SSH key via existing SSH: {e}", style="red")
            return False
    
    def test_ssh_connection(self, user: str, public_ip: str) -> bool:
        """Test SSH connection"""
        try:
            if not public_ip or public_ip == 'N/A':
                stderr_console.print("✗ No public IP available for SSH test", style="red")
                return False
            
            ssh_cmd = [
                "ssh", "-i", self.ssh_key_file, 
                "-o", "StrictHostKeyChecking=no", 
                "-o", "ConnectTimeout=10",
                "-o", "PasswordAuthentication=no",
                "-o", "PubkeyAuthentication=yes",
                "-o", "PreferredAuthentications=publickey",
                f"{user}@{public_ip}", 
                "echo 'SSH connection test successful'"
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                stderr_console.print("✓ SSH connection test successful", style="green")
                return True
            else:
                stderr_console.print(f"✗ SSH connection test failed: {result.stderr}", style="red")
                return False
                
        except subprocess.TimeoutExpired:
            stderr_console.print("✗ SSH connection test timed out", style="red")
            return False
        except Exception as e:
            stderr_console.print(f"Error testing SSH connection: {e}", style="red")
            return False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Inject SSH keys into multiple hosts from CSV file')
    parser.add_argument('--csv', '-c', type=str, default='files/all_hosts.csv',
                       help='Path to CSV file (default: files/all_hosts.csv)')
    parser.add_argument('--ssh-key', '-k', type=str, 
                       default=os.path.expanduser("~/.ssh/id_ed25519_devops"),
                       help='Path to SSH private key to inject (default: ~/.ssh/id_ed25519_devops)')
    parser.add_argument('--existing-key', type=str,
                       help='Path to existing SSH private key to use for connection (bypasses EC2 Instance Connect)')
    parser.add_argument('--exclude', '-e', type=str, 
                       default=','.join(DEFAULT_EXCLUDE_PATTERNS),
                       help=f'Comma-separated list of patterns to exclude (default: {",".join(DEFAULT_EXCLUDE_PATTERNS)})')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug mode with interactive prompts')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually doing it')
    return parser.parse_args()

def load_csv_data(csv_path):
    """Load and validate CSV data"""
    try:
        stderr_console.print(f"Loading CSV from: {csv_path}", style="bold blue")
        
        df = pd.read_csv(csv_path)
        stderr_console.print(f"Successfully loaded CSV with {len(df)} rows", style="green")
        
        return df
    except FileNotFoundError:
        stderr_console.print(f"Error: CSV file not found at {csv_path}", style="red")
        
        if csv_path.name == 'all_hosts.csv':
            stderr_console.print("\n[bold yellow]To generate the CSV file, run:[/bold yellow]")
            stderr_console.print("  [cyan]./scripts/find-ec2.py > files/all_hosts.csv[/cyan]", style="bold")
            stderr_console.print("\nOr specify a different CSV file with --csv option", style="dim")
        
        sys.exit(1)
    except Exception as e:
        stderr_console.print(f"Error loading CSV: {e}", style="red")
        sys.exit(1)

def should_exclude_host(host_name, exclude_patterns):
    """Check if host should be excluded based on patterns"""
    if pd.isna(host_name) or host_name == 'N/A':
        return True
    
    host_name_lower = str(host_name).lower()
    for pattern in exclude_patterns:
        if pattern.lower() in host_name_lower:
            return True
    return False

def process_host(host: pd.Series, injector: SSHKeyInjector, exclude_patterns: List[str], 
                debug: bool = False, dry_run: bool = False) -> Tuple[bool, Optional[List[str]]]:
    """Process a single host"""
    account_role = host['account_role']
    instance_id = host['instance_id']
    region = host['region']
    name = host['name']
    state = host['state']
    public_ip = host.get('public_ip', 'N/A')
    
    # Skip if host should be excluded
    if should_exclude_host(name, exclude_patterns):
        stderr_console.print(f"Skipping {name} (excluded by pattern)", style="yellow")
        return False, None
    
    # Skip if instance is not running
    if state != 'running':
        stderr_console.print(f"Skipping {name} (state: {state})", style="yellow")
        return False, None
    
    if dry_run:
        stderr_console.print(f"[bold cyan]DRY RUN:[/bold cyan] Would process {name} in {account_role} ({instance_id}) - {public_ip}")
        return True, None
    
    # Process the host
    stderr_console.print(f"\n[bold cyan]Processing:[/bold cyan] {name} in {account_role} ({instance_id}) - {public_ip}")
    
    # Process all users, trying EC2 Instance Connect
    success, user = injector.inject_key_to_host_all_users(host)
    
    if success:
        stderr_console.print(f"  Test with: ssh -i {injector.ssh_key_file} {user}@{public_ip}", style="cyan")
        return True, [user]
    else:
        stderr_console.print(f"✗ Failed to process any users for {name}", style="red")
        return False, []

def main():
    """Main function"""
    args = parse_arguments()
    
    # Display helpful information
    method_info = f"[yellow]Method:[/yellow] [dim]{'Existing key bypass' if args.existing_key else 'EC2 Instance Connect'}[/dim]"
    if args.existing_key:
        method_info += f"\n[yellow]Existing key:[/yellow] [dim]{args.existing_key}[/dim]"
    
    console.print(Panel.fit(
        "[bold cyan]SSH Key Injection Script[/bold cyan]\n\n"
        "[yellow]To generate the CSV file, run:[/yellow]\n"
        "[cyan]./scripts/find-ec2.py > files/all_hosts.csv[/cyan]\n\n"
        f"{method_info}\n"
        "[yellow]Exclude patterns:[/yellow] [dim]{exclude_patterns}[/dim]\n"
        "[yellow]SSH key to inject:[/yellow] [dim]{ssh_key}[/dim]".format(
            exclude_patterns=args.exclude,
            ssh_key=args.ssh_key
        ),
        title="Setup Information"
    ))
    
    # Load CSV data
    df = load_csv_data(args.csv)
    
    # Parse exclude patterns
    exclude_patterns = [pattern.strip() for pattern in args.exclude.split(',')]
    
    # Initialize SSH key injector
    injector = SSHKeyInjector(args.ssh_key, args.existing_key)
    
    # Filter hosts
    total_hosts = len(df)
    excluded_count = 0
    processed_count = 0
    failed_count = 0
    user_counts = {}
    ec2_count = 0
    
    stderr_console.print(f"\n[bold cyan]Processing {total_hosts} hosts...[/bold cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=stderr_console
    ) as progress:
        task = progress.add_task("Processing hosts...", total=total_hosts)
        
        for _, host in df.iterrows():
            # Check if host should be excluded
            if should_exclude_host(host.get('name'), exclude_patterns):
                excluded_count += 1
                progress.advance(task)
                continue
            
            # Debug prompt - pause progress bar if needed
            if args.debug:
                progress.stop()
                name = host.get('name', 'Unknown')
                account_role = host.get('account_role', 'Unknown')
                instance_id = host.get('instance_id', 'Unknown')
                public_ip = host.get('public_ip', 'N/A')
                stderr_console.print(f"\n[bold cyan]Processing:[/bold cyan] {name} in {account_role} ({instance_id}) - {public_ip}")
                response = input("Continue? (y/n): ")
                if response.lower() != 'y':
                    stderr_console.print("Skipping...", style="yellow")
                    progress.start()
                    progress.advance(task)
                    continue
                progress.start()
            
            # Process the host
            success, users = process_host(host, injector, exclude_patterns, args.debug, args.dry_run)
            
            if success:
                processed_count += 1
                if users:
                    for user in users:
                        user_counts[user] = user_counts.get(user, 0) + 1
                
                # Count method used
                # EC2 Instance Connect is always used for temporary key injection
                ec2_count += 1
            else:
                failed_count += 1
            
            progress.advance(task)
            
            # Small delay to avoid overwhelming the system
            if not args.dry_run:
                time.sleep(1)
    
    # Summary
    console.print("\n[bold cyan]Summary:[/bold cyan]")
    console.print(f"Total hosts: {total_hosts}")
    console.print(f"Excluded: {excluded_count}")
    console.print(f"Processed: {processed_count}")
    console.print(f"Failed: {failed_count}")
    
    if processed_count > 0:
        console.print(f"\n[bold cyan]Methods used:[/bold cyan]")
        console.print(f"EC2 Instance Connect: {ec2_count}")
    
    if user_counts:
        console.print("\n[bold cyan]Users SSH keys were added for:[/bold cyan]")
        for user, count in sorted(user_counts.items()):
            console.print(f"  {user}: {count} hosts")

if __name__ == "__main__":
    main() 