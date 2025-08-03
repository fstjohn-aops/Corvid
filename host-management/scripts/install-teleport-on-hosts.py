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
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

console = Console()
stderr_console = Console(stderr=True)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Install Teleport on multiple hosts across AWS accounts')
    parser.add_argument('--public-key', '-p', type=str, 
                       default="/Users/finnstjohn/.ssh/id_ed25519_devops.pub",
                       help='Path to public key file (default: /Users/finnstjohn/.ssh/id_ed25519_devops.pub)')
    parser.add_argument('--private-key', '-k', type=str,
                       default="/Users/finnstjohn/.ssh/id_ed25519_devops",
                       help='Path to private key file (default: /Users/finnstjohn/.ssh/id_ed25519_devops)')
    parser.add_argument('--limit', '-l', type=int, metavar='N',
                       help='Limit to first N profiles (default: all profiles)')
    parser.add_argument('--filter', '-f', type=str, default='bastion',
                       help='Comma-separated list of substrings to filter hosts by name (default: bastion)')
    parser.add_argument('--ansible-path', type=str,
                       help='Path to existing ansible playbooks directory')
    parser.add_argument('--force-download', action='store_true',
                       help='Force download of ansible playbooks')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode with verbose output and interactive prompts')
    parser.add_argument('--skip-ssh-key-push', action='store_true',
                       help='Skip pushing SSH key (assumes key is already permanently installed)')
    return parser.parse_args()

def get_hosts(limit=None, filter_terms='bastion'):
    """Get hosts using find-ec2.py"""
    try:
        FIND_EC2_SCRIPT_NAME = "find-ec2.py"
        script_dir = Path(__file__).parent
        find_ec2_script = script_dir / FIND_EC2_SCRIPT_NAME
        
        if not find_ec2_script.exists():
            stderr_console.print(f"Error: find-ec2.py not found at {find_ec2_script}", style="red")
            return []
        
        cmd = [sys.executable, str(find_ec2_script), "--search", filter_terms]
        if limit:
            cmd.extend(["--limit", str(limit)])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Parse CSV output
            hosts = []
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Skip header
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 8:
                            hosts.append({
                                'account_role': parts[0],
                                'instance_id': parts[1],
                                'region': parts[2],
                                'public_ip': parts[3],
                                'private_ip': parts[4],
                                'state': parts[5],
                                'name': parts[6],
                                'key_name': parts[7]
                            })
            
            stderr_console.print(f"Found {len(hosts)} hosts matching filter: {filter_terms}", style="green")
            return hosts
        else:
            stderr_console.print(f"Error running find-ec2.py: {result.stderr}", style="red")
            return []
            
    except Exception as e:
        stderr_console.print(f"Error getting hosts: {e}", style="red")
        return []

def install_teleport_on_host(host, private_key_file, ansible_path=None, force_download=False, debug=False, skip_ssh_key_push=False):
    """Install Teleport on a single host using the single-host script"""
    try:
        script_dir = Path(__file__).parent
        single_host_script = script_dir / "install-teleport-single-host.py"
        
        if not single_host_script.exists():
            stderr_console.print(f"Error: install-teleport-single-host.py not found at {single_host_script}", style="red")
            return False
        
        cmd = [
            sys.executable, str(single_host_script),
            host['account_role'],
            host['instance_id'],
            host['region'],
            host['public_ip'],
            host['name'],
            "--private-key", private_key_file
        ]
        
        if ansible_path:
            cmd.extend(["--ansible-path", ansible_path])
        
        if force_download:
            cmd.append("--force-download")
        
        if debug:
            cmd.append("--debug")
        
        if skip_ssh_key_push:
            cmd.append("--skip-ssh-key-push")
        
        if debug:
            stderr_console.print(f"Running command: {' '.join(cmd)}", style="cyan")
            input("Press Enter to continue...")
        
        if debug:
            # Stream output in real-time for debug mode
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0, universal_newlines=True)
            
            # Read and display output line by line
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    stderr_console.print(line.rstrip(), style="cyan")
            
            result = process.wait()
            stderr_console.print(f"Return code: {result}", style="cyan")
        else:
            # Normal mode: capture output
            result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            stderr_console.print(f"Failed to install teleport on {host['name']}: {result.stderr}", style="yellow")
            return False
            
    except Exception as e:
        stderr_console.print(f"Error installing teleport on {host['name']}: {e}", style="red")
        return False

def main():
    args = parse_arguments()
    
    # Validate key files
    if not Path(args.public_key).exists():
        stderr_console.print(f"Error: Public key file '{args.public_key}' does not exist", style="red")
        sys.exit(1)
    
    if not Path(args.private_key).exists():
        stderr_console.print(f"Error: Private key file '{args.private_key}' does not exist", style="red")
        sys.exit(1)
    
    # Get hosts
    hosts = get_hosts(args.limit, args.filter)
    if not hosts:
        stderr_console.print("No hosts found matching filter. Exiting.", style="red")
        sys.exit(1)
    
    # Process each host
    successful = 0
    failed = 0
    
    if args.debug:
        # Debug mode: no progress bar, just process hosts directly
        for host in hosts:
            stderr_console.print(f"Processing {host['instance_id']}", style="bold blue")
            
            # Install teleport
            if install_teleport_on_host(host, args.private_key, args.ansible_path, args.force_download, args.debug, args.skip_ssh_key_push):
                successful += 1
            else:
                failed += 1
    else:
        # Normal mode: use progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=stderr_console
        ) as progress:
            task = progress.add_task("Installing Teleport...", total=len(hosts))
            
            for host in hosts:
                progress.update(task, description=f"Processing {host['instance_id']}")
                
                # Install teleport
                if install_teleport_on_host(host, args.private_key, args.ansible_path, args.force_download, args.debug, args.skip_ssh_key_push):
                    successful += 1
                else:
                    failed += 1
                
                progress.advance(task)
    
    # Summary
    stderr_console.print(Panel(
        f"Summary:\n"
        f"Successful: {successful}\n"
        f"Failed: {failed}\n"
        f"Total: {len(hosts)}",
        title="Installation Complete",
        border_style="blue"
    ))

if __name__ == "__main__":
    main() 