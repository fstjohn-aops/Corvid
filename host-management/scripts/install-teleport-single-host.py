#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=13.0.0",
# ]
# ///

import sys
import os
import argparse
import subprocess
import tempfile
from pathlib import Path
from rich.console import Console

console = Console()
stderr_console = Console(stderr=True)

# Global variable to store ansible playbooks directory
_ANSIBLE_PLAYBOOKS_DIR = None

def get_ansible_playbooks_dir(force_download=False, custom_path=None):
    """Get ansible playbooks directory, downloading if necessary"""
    global _ANSIBLE_PLAYBOOKS_DIR
    
    if _ANSIBLE_PLAYBOOKS_DIR is not None:
        return _ANSIBLE_PLAYBOOKS_DIR
    
    if custom_path:
        if Path(custom_path).exists():
            _ANSIBLE_PLAYBOOKS_DIR = custom_path
            stderr_console.print(f"Using custom ansible playbooks path: {custom_path}", style="blue")
            return _ANSIBLE_PLAYBOOKS_DIR
        else:
            stderr_console.print(f"Custom path does not exist: {custom_path}", style="red")
            return None
    
    # Check if we have a cached version in temp
    temp_dir = Path(tempfile.gettempdir()) / "teleport-ansible-playbooks"
    if temp_dir.exists() and not force_download:
        _ANSIBLE_PLAYBOOKS_DIR = str(temp_dir)
        stderr_console.print(f"Using cached ansible playbooks: {temp_dir}", style="blue")
        return _ANSIBLE_PLAYBOOKS_DIR
    
    # Download fresh copy
    try:
        temp_dir.mkdir(exist_ok=True)
        stderr_console.print("Downloading ansible playbooks...", style="blue")
        
        env = os.environ.copy()
        env["FORCE_NO_ALIAS"] = "true"
        
        cmd = [
            "assume", "Monitoring.AWSAdministratorAccess", "--exec", "--",
            "aws", "s3", "sync", "s3://aops-ansible-playbooks/playbooks/install-teleport", str(temp_dir)
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            _ANSIBLE_PLAYBOOKS_DIR = str(temp_dir)
            stderr_console.print("Ansible playbooks downloaded", style="green")
            return _ANSIBLE_PLAYBOOKS_DIR
        else:
            stderr_console.print(f"Failed to download playbooks: {result.stderr}", style="yellow")
            return None
            
    except Exception as e:
        stderr_console.print(f"Error downloading playbooks: {e}", style="red")
        return None

def push_ssh_key(account_role, instance_id, region, public_key_file, debug=False):
    """Push SSH key using push-ssh-key-to-instance.py"""
    try:
        script_dir = Path(__file__).parent
        push_key_script = script_dir / "push-ssh-key-to-instance.py"
        
        if not push_key_script.exists():
            stderr_console.print(f"Error: push-ssh-key-to-instance.py not found at {push_key_script}", style="red")
            return False
        
        cmd = [
            sys.executable, str(push_key_script),
            account_role, instance_id,
            "--region", region,
            "--key-file", public_key_file
        ]
        
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
        
        # Check return code (result is int in debug mode, CompletedProcess in normal mode)
        if (debug and result == 0) or (not debug and result.returncode == 0):
            return True
        else:
            stderr_console.print(f"Failed to push SSH key", style="yellow")
            return False
            
    except Exception as e:
        stderr_console.print(f"Error pushing SSH key: {e}", style="red")
        return False

def exec_ssh_command(host, private_key_file, command, description="", debug=False, public_key_file=None, skip_ssh_key_push=False):
    """Execute SSH command on host"""
    try:
        # Push SSH key before each command to ensure it doesn't expire (unless skipped)
        if public_key_file and not skip_ssh_key_push:
            if debug:
                stderr_console.print("Pushing SSH key before command...", style="cyan")
            push_ssh_key(host['account_role'], host['instance_id'], host['region'], public_key_file, debug)
        
        ssh_cmd = [
            "ssh", "-i", private_key_file,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            f"ec2-user@{host['public_ip']}",
            command
        ]
        
        if debug:
            stderr_console.print(f"Running SSH command: {' '.join(ssh_cmd)}", style="cyan")
            input("Press Enter to continue...")
        
        if debug:
            # Stream output in real-time for debug mode
            process = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0, universal_newlines=True)
            
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
            result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        
        # Check return code (result is int in debug mode, CompletedProcess in normal mode)
        if (debug and result == 0) or (not debug and result.returncode == 0):
            stderr_console.print(f"{description} successful", style="green")
            return True
        else:
            stderr_console.print(f"{description} failed", style="yellow")
            stderr_console.print("Make sure your VPN is on and you can reach the instance", style="red")
            return False
            
    except Exception as e:
        stderr_console.print(f"Error executing SSH command: {e}", style="red")
        return False

def copy_files_to_host(host, private_key_file, local_dir, remote_dir="/tmp", debug=False, public_key_file=None, skip_ssh_key_push=False):
    """Copy files to host using scp"""
    try:
        # Push SSH key before SCP to ensure it doesn't expire (unless skipped)
        if public_key_file and not skip_ssh_key_push:
            if debug:
                stderr_console.print("Pushing SSH key before SCP...", style="cyan")
            push_ssh_key(host['account_role'], host['instance_id'], host['region'], public_key_file, debug)
        
        scp_cmd = [
            "scp", "-r", "-i", private_key_file,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            local_dir,
            f"ec2-user@{host['public_ip']}:{remote_dir}/"
        ]
        
        if debug:
            stderr_console.print(f"Running SCP command: {' '.join(scp_cmd)}", style="cyan")
            input("Press Enter to continue...")
        
        if debug:
            # Stream output in real-time for debug mode
            process = subprocess.Popen(scp_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0, universal_newlines=True)
            
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
            result = subprocess.run(scp_cmd, capture_output=True, text=True)
        
        # Check return code (result is int in debug mode, CompletedProcess in normal mode)
        if (debug and result == 0) or (not debug and result.returncode == 0):
            stderr_console.print("Files copied successfully", style="green")
            return True
        else:
            stderr_console.print("Failed to copy files", style="yellow")
            return False
            
    except Exception as e:
        stderr_console.print(f"Error copying files: {e}", style="red")
        return False

def install_teleport_on_host(host, private_key_file, ansible_dir=None, force_download=False, debug=False, public_key_file=None, skip_ssh_key_push=False):
    """Install Teleport on a single host"""
    stderr_console.print(f"Processing {host['instance_id']}", style="bold blue")
    
    if debug:
        stderr_console.print(f"Host details: {host}", style="cyan")
        input("Press Enter to continue...")
    
    # Get ansible playbooks directory
    if ansible_dir is None:
        ansible_dir = get_ansible_playbooks_dir(force_download)
        if not ansible_dir:
            stderr_console.print("Failed to get ansible playbooks", style="red")
            return False
    
    # Test connection
    if not exec_ssh_command(host, private_key_file, "sudo echo Connection is working!", "Connection test", debug, public_key_file, skip_ssh_key_push):
        return False
    
    # Copy ansible playbooks
    if not copy_files_to_host(host, private_key_file, ansible_dir, debug=debug, public_key_file=public_key_file, skip_ssh_key_push=skip_ssh_key_push):
        return False
    
    # Install ansible (try multiple approaches for different Linux distributions)
    ansible_install_cmd = '''sudo dnf install -y ansible || 
                            sudo yum install -y ansible ||
                            sudo amazon-linux-extras enable ansible2 && sudo yum install -y ansible ||
                            sudo yum install -y python3-pip && sudo pip3 install ansible'''
    if not exec_ssh_command(host, private_key_file, ansible_install_cmd, "Install ansible", debug, public_key_file, skip_ssh_key_push):
        return False
    
    # Install yq
    yq_cmd = '''ARCH=$(uname -m) && if [ "$ARCH" = "aarch64" ]; then YQ_ARCH="arm64"; else YQ_ARCH="amd64"; fi && sudo curl -L "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_$YQ_ARCH" -o /usr/local/bin/yq && sudo chmod +x /usr/local/bin/yq'''
    if not exec_ssh_command(host, private_key_file, yq_cmd, "Install yq", debug, public_key_file, skip_ssh_key_push):
        return False
    
    # Install teleport
    playbook_dir = Path(ansible_dir).name
    if not exec_ssh_command(host, private_key_file, f"cd /tmp/{playbook_dir} && ansible-playbook local.yml", "Install teleport", debug, public_key_file, skip_ssh_key_push):
        return False
    
    # Add manual bastion label
    label_cmd = f'sudo /usr/local/bin/yq eval \'.ssh_service.labels.manual_name = "{host["name"]}"\' -i /etc/teleport.yaml'
    if not exec_ssh_command(host, private_key_file, label_cmd, "Add bastion label", debug, public_key_file, skip_ssh_key_push):
        return False
    
    # Restart teleport service
    if not exec_ssh_command(host, private_key_file, "sudo systemctl restart teleport", "Restart teleport", debug, public_key_file, skip_ssh_key_push):
        return False
    
    # Cleanup
    if not exec_ssh_command(host, private_key_file, f"rm -rf /tmp/{playbook_dir}", "Cleanup", debug, public_key_file, skip_ssh_key_push):
        return False
    
    return True

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Install Teleport on a single bastion host')
    parser.add_argument('account_role', help='AWS account role')
    parser.add_argument('instance_id', help='EC2 instance ID')
    parser.add_argument('region', help='AWS region')
    parser.add_argument('public_ip', help='Public IP address')
    parser.add_argument('name', help='Instance name')
    parser.add_argument('--public-key', '-p', type=str, 
                       default="/Users/finnstjohn/.ssh/id_ed25519_devops.pub",
                       help='Path to public key file (default: /Users/finnstjohn/.ssh/id_ed25519_devops.pub)')
    parser.add_argument('--private-key', '-k', type=str,
                       default="/Users/finnstjohn/.ssh/id_ed25519_devops",
                       help='Path to private key file (default: /Users/finnstjohn/.ssh/id_ed25519_devops)')
    parser.add_argument('--ansible-path', type=str,
                       help='Path to existing ansible playbooks directory')
    parser.add_argument('--force-download', action='store_true',
                       help='Force download of ansible playbooks')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode with verbose output and interactive prompts')
    parser.add_argument('--skip-ssh-key-push', action='store_true',
                       help='Skip pushing SSH key (assumes key is already permanently installed)')
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    if args.debug:
        stderr_console.print("Starting single-host teleport installation in debug mode", style="cyan")
    
    # Validate key files
    if not Path(args.public_key).exists():
        stderr_console.print(f"Error: Public key file '{args.public_key}' does not exist", style="red")
        sys.exit(1)
    
    if not Path(args.private_key).exists():
        stderr_console.print(f"Error: Private key file '{args.private_key}' does not exist", style="red")
        sys.exit(1)
    
    # Create host dict
    host = {
        'account_role': args.account_role,
        'instance_id': args.instance_id,
        'region': args.region,
        'public_ip': args.public_ip,
        'name': args.name
    }
    
    if args.debug:
        stderr_console.print(f"Host configuration: {host}", style="cyan")
        stderr_console.print(f"Public key: {args.public_key}", style="cyan")
        stderr_console.print(f"Private key: {args.private_key}", style="cyan")
        input("Press Enter to start installation...")
    
    # Push SSH key (unless skipped)
    if not args.skip_ssh_key_push:
        if not push_ssh_key(host['account_role'], host['instance_id'], host['region'], args.public_key, args.debug):
            stderr_console.print("Failed to push SSH key", style="red")
            sys.exit(1)
    else:
        stderr_console.print("Skipping initial SSH key push (assumes key is permanently installed)", style="blue")
    
    # Install teleport
    success = install_teleport_on_host(
        host, 
        args.private_key, 
        ansible_dir=args.ansible_path,
        force_download=args.force_download,
        debug=args.debug,
        public_key_file=args.public_key,
        skip_ssh_key_push=args.skip_ssh_key_push
    )
    
    if success:
        stderr_console.print("Teleport installation completed successfully", style="green")
        sys.exit(0)
    else:
        stderr_console.print("Teleport installation failed", style="red")
        sys.exit(1)

if __name__ == "__main__":
    main() 