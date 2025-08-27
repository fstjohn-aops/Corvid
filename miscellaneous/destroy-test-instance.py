#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=13.0.0",
#   "PyYAML>=6.0.0",
# ]
# ///

import os
import sys
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import time
import functools

# Third-party imports
from rich.console import Console
from rich.prompt import Prompt
from rich.status import Status
import yaml
from rich.live import Live
from rich.text import Text

console = Console()
stderr_console = Console(stderr=True)

# =============================
# GLOBAL CONSTANTS & DEFAULT CONFIG
# =============================

DEFAULT_ANSIBLE_CFG_BRANCH = "simple"
DEFAULT_TERRAMATE_CLOUD_REPO = "git@github.com:aops-ba/terramate-cloud.git"
DEFAULT_ANSIBLE_CONFIG_REPO = "git@github.com:aops-ba/ansible-cfg.git"
DEFAULT_STACK_ACCOUNT_PATH = "stacks/accounts/aops_dev.487718497406"
REQUIRED_DEPENDENCIES = [
    "git", "terraform", "aws", "yq", "play", "terramate"
]

# =============================
# ENVIRONMENT UTILITIES
# =============================

def get_env(var, default=None, required=False):
    val = os.environ.get(var, default)
    if required and not val:
        stderr_console.print(f"[red]ERROR: {var} is required but not set.[/red]")
        sys.exit(1)
    return val

# =============================
# ARGUMENT PARSING
# =============================

def parse_arguments():
    parser = argparse.ArgumentParser(description="Destroy a test EC2 instance and clean up configuration.")
    parser.add_argument("prefix", help="Prefix for the instance to destroy (alphanumeric, underscores, and dashes)")
    parser.add_argument("--ci", action="store_true", help="Run in CI mode (no prompts)")
    parser.add_argument("--verbose", action="store_true", help="Show all command output in real time (dim info lines still shown)")
    parser.add_argument("--debug", action="store_true", help="Stream all subprocess output directly to stdout/stderr (overrides --verbose, disables log file)")
    return parser.parse_args()

# =============================
# PRINTING & FEEDBACK UTILS
# =============================

def dim_print(*args, **kwargs):
    console.print(*args, style="dim", **kwargs)

# =============================
# COMMAND EXECUTION UTILS
# =============================

def run(cmd, cwd=None, check=True, env=None, log_file=None, debug=False, status_msg: Optional[str] = None):
    """
    Run a command. Handles debug, log_file, and status printing. If status_msg is provided, prints a status spinner during execution (unless debug is True).
    In non-debug mode, suppress all command output.
    """
    if debug:
        console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
        try:
            result = subprocess.run(cmd, cwd=cwd, check=check, env=env)
            console.print(f"[green]Command finished: {' '.join(cmd)}[/green]")
            return result.returncode
        except subprocess.CalledProcessError as e:
            stderr_console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
            raise
    def _run_proc():
        try:
            with subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            ) as proc:
                if log_file:
                    for line in proc.stdout:
                        log_file.write(line)
                else:
                    # Suppress all output in non-debug mode
                    for _ in proc.stdout:
                        pass
                proc.wait()
                if proc.returncode == 0 and debug:
                    console.print(f"[green]Command finished: {' '.join(cmd)}[/green]")
                if check and proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, cmd)
                return proc.returncode
        except subprocess.CalledProcessError as e:
            stderr_console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
            raise
    if status_msg and not debug:
        with Status(status_msg, console=console, spinner="dots"):
            return _run_proc()
    else:
        return _run_proc()

# =============================
# DECORATORS FOR TIMING & FEEDBACK
# =============================

def dimmed_timed_step(start_msg, end_msg_func):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if DEBUG_MODE:
                return func(*args, **kwargs)
            start = time.monotonic()
            with Status(Text(start_msg, style="dim"), console=console, spinner="dots"):
                result = func(*args, **kwargs)
            elapsed = int(time.monotonic() - start)
            m, s = divmod(elapsed, 60)
            time_str = f"{m}m{s:02d}s" if m else f"{s}s"
            msg = end_msg_func(result, *args, **kwargs)
            console.print(f"[{time_str}] {msg}", style="dim")
            return result
        return wrapper
    return decorator

DEBUG_MODE = False

# =============================
# REPO CLONING & FILE OPS
# =============================

# Timed operation for cloning Terramate repo
@dimmed_timed_step("Cloning Terramate repo", lambda result, *a, **k: f"Cloned Terramate repo to {result}")
def clone_terramate_repo(repo_url, path, log_file):
    run(["git", "clone", repo_url, str(path)], log_file=log_file, debug=DEBUG_MODE)
    return path

# Timed operation for cloning Ansible repo
@dimmed_timed_step("Cloning Ansible repo", lambda result, *a, **k: f"Cloned Ansible repo to {result}")
def clone_ansible_repo(repo_url, path, branch, log_file):
    run(["git", "clone", repo_url, str(path)], log_file=log_file, debug=DEBUG_MODE)
    run(["git", "checkout", branch], cwd=path, log_file=log_file, debug=DEBUG_MODE)
    return path

# =============================
# MAJOR STEP FUNCTIONS
# =============================

@dimmed_timed_step("Destroying Terraform stack and removing resources...", lambda result, *a, **k: f"Destroyed Terraform stack and removed resources for {k.get('full_hostname', '<host>')}")
def destroy_terraform_stack(stack_path, terramate_cloud_path, full_hostname, log_file):
    if not stack_path.exists():
        console.print(f"[yellow]Stack directory {stack_path} does not exist. Skipping terraform destroy.[/yellow]")
        return False
    
    # Navigate to stack directory and destroy
    run(["terraform", "init"], cwd=stack_path, log_file=log_file, debug=DEBUG_MODE)
    run(["terraform", "destroy", "-auto-approve"], cwd=stack_path, log_file=log_file, debug=DEBUG_MODE)
    
    # Remove stack directory
    shutil.rmtree(stack_path)
    
    # Commit and push changes
    run(["git", "add", "."], cwd=terramate_cloud_path, log_file=log_file, debug=DEBUG_MODE)
    run(["git", "commit", "-m", f"Destroy test instance {full_hostname} (remove stack)"], 
        cwd=terramate_cloud_path, check=False, log_file=log_file, debug=DEBUG_MODE)
    run(["git", "push", "origin", "main"], cwd=terramate_cloud_path, log_file=log_file, debug=DEBUG_MODE)
    
    return True

@dimmed_timed_step("Removing host from inventory and emails.yml...", lambda result, *a, **k: f"Removed {k.get('full_hostname', '<host>')} from inventory and emails.yml")
def remove_from_ansible_inventory(ansible_config_root, full_hostname, log_file):
    inventory_mgr = InventoryManager(ansible_config_root)
    inventory_mgr.remove_host(
        full_hostname=full_hostname,
        log_file=log_file
    )
    return ansible_config_root

# =============================
# INVENTORY/EMAIL MANAGEMENT
# =============================

class InventoryManager:
    def __init__(self, ansible_config_root: Path):
        self.ansible_config_root = Path(ansible_config_root)
        self.inventory_file = self.ansible_config_root / "inventory.yml"
        self.emails_file = self.ansible_config_root / "group_vars/all/emails.yml"

    def remove_host_from_inventory(self, full_hostname: str):
        """Remove host from inventory.yml using yq"""
        if not self.inventory_file.exists():
            console.print(f"[yellow]Warning: {self.inventory_file} not found[/yellow]")
            return False
        
        # Check if host exists in inventory
        result = subprocess.run(["yq", "eval", f".all.hosts | has(\"{full_hostname}\")", str(self.inventory_file)], 
                    capture_output=True, text=True, check=False)
        if "true" in result.stdout:
            run(["yq", "eval", f"del(.all.hosts.\"{full_hostname}\")", "-i", str(self.inventory_file)], 
                log_file=None, debug=DEBUG_MODE)
            console.print(f"Removed {full_hostname} from inventory.yml")
            return True
        else:
            console.print(f"{full_hostname} not found in inventory.yml")
            return False

    def remove_email_for_host(self, full_hostname: str):
        """Remove host from emails.yml using yq"""
        if not self.emails_file.exists():
            console.print(f"[yellow]Warning: {self.emails_file} not found[/yellow]")
            return False
        
        # Check if host exists in emails
        result = subprocess.run(["yq", "eval", f".host_emails | has(\"{full_hostname}\")", str(self.emails_file)], 
                    capture_output=True, text=True, check=False)
        if "true" in result.stdout:
            run(["yq", "eval", f"del(.host_emails.\"{full_hostname}\")", "-i", str(self.emails_file)], 
                log_file=None, debug=DEBUG_MODE)
            console.print(f"Removed {full_hostname} from emails.yml")
            return True
        else:
            console.print(f"{full_hostname} not found in emails.yml")
            return False

    def remove_host(self, full_hostname: str, log_file):
        """Remove host from both inventory and emails files"""
        inventory_removed = self.remove_host_from_inventory(full_hostname)
        emails_removed = self.remove_email_for_host(full_hostname)
        
        # Only commit if there were changes
        if inventory_removed or emails_removed:
            if DEBUG_MODE:
                console.print(f"[dim]Committing and pushing Ansible inventory changes...[/dim]")
            run(["git", "add", str(self.inventory_file), str(self.emails_file)], 
                cwd=self.ansible_config_root, log_file=log_file, debug=DEBUG_MODE)
            run(["git", "commit", "-m", f"Remove {full_hostname} from host_emails in emails.yml and inventory.yml"], 
                cwd=self.ansible_config_root, check=False, log_file=log_file, debug=DEBUG_MODE)
            run(["git", "push", "origin", "simple"], 
                cwd=self.ansible_config_root, log_file=log_file, debug=DEBUG_MODE)

# =============================
# MAIN EXECUTION
# =============================

def print_step_header(step_num, step_desc):
    # Use a pretty unicode box-drawing symbol for the header
    bar = '━'
    header = f"{bar*3} [{step_num}/3] {step_desc} {bar*3}"
    console.print(header, style="bold cyan")

def prompt_to_continue(ci):
    if not ci:
        Prompt.ask("Press Enter to continue...")

def main():
    global DEBUG_MODE
    args = parse_arguments()
    prefix = args.prefix
    full_hostname = f"{prefix}.aopstest.com"
    ci = args.ci or bool(os.environ.get("CI"))
    DEBUG_MODE = args.debug

    # Validate PREFIX format - allow alphanumeric, underscores, and dashes
    if not prefix.replace('_', '').replace('-', '').isalnum():
        stderr_console.print("[red]ERROR: PREFIX must be alphanumeric (letters, numbers, underscores, and dashes only).[/red]")
        sys.exit(1)

    # Config
    ansible_cfg_branch = get_env("ANSIBLE_CFG_BRANCH", DEFAULT_ANSIBLE_CFG_BRANCH)
    terramate_cloud_repo = get_env("TERRAMATE_CLOUD_REPO", DEFAULT_TERRAMATE_CLOUD_REPO)
    ansible_config_repo = get_env("ANSIBLE_CONFIG_REPO", DEFAULT_ANSIBLE_CONFIG_REPO)
    
    # Check for Cloudflare token
    if not get_env("CLOUDFLARE_API_TOKEN", required=True):
        stderr_console.print("[red]ERROR: CLOUDFLARE_API_TOKEN is not set in the environment.[/red]")
        sys.exit(1)

    log_file_ctx = tempfile.NamedTemporaryFile("w+t", delete=False, prefix="destroy-test-instance-", suffix=".log") if not DEBUG_MODE else None
    log_file = log_file_ctx if log_file_ctx else None
    log_path = log_file.name if log_file else None
    
    try:
        print_step_header(1, "Cloning code and setting up")
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        terramate_cloud_path = Path(os.environ.get("TERRAMATE_CLOUD_PATH") or f"/tmp/terramate-cloud-{prefix}-{unique_id}")
        ansible_config_root = Path(os.environ.get("ANSIBLE_CONFIG_ROOT") or f"/tmp/ansible-cfg-{prefix}-{unique_id}")
        
        if not terramate_cloud_path.exists():
            clone_terramate_repo(terramate_cloud_repo, terramate_cloud_path, log_file)
        if not ansible_config_root.exists():
            clone_ansible_repo(ansible_config_repo, ansible_config_root, ansible_cfg_branch, log_file)
        
        base_path = terramate_cloud_path / DEFAULT_STACK_ACCOUNT_PATH
        stack_path = base_path / full_hostname
        
        prompt_to_continue(ci)

        print_step_header(2, "Destroying Terraform stack and removing resources")
        destroy_terraform_stack(
            stack_path=stack_path,
            terramate_cloud_path=terramate_cloud_path,
            full_hostname=full_hostname,
            log_file=log_file
        )
        prompt_to_continue(ci)

        print_step_header(3, "Removing host from inventory and emails.yml")
        remove_from_ansible_inventory(
            ansible_config_root=ansible_config_root,
            full_hostname=full_hostname,
            log_file=log_file
        )
        
        if DEBUG_MODE:
            console.print(f"[green]Successfully destroyed {full_hostname}![/green]")
        else:
            console.print(f"Successfully destroyed {full_hostname}!", style="dim")
            console.print(f"Log file: {log_path}", style="dim")
        
        # Play a sound (optional, if play is available)
        if shutil.which("play"):
            for freq in (1100, 990, 880):  # Reverse order for destroy
                run(["play", "-q", "-n", "synth", "0.1", "sin", str(freq)], check=False, log_file=log_file, debug=DEBUG_MODE)
                
    except Exception as e:
        if DEBUG_MODE:
            console.print(f"[red]ERROR: {e}[/red]")
        else:
            console.print(f"[red]ERROR: {e}[/red]\n[dim]See log file for details: {log_path}[/dim]", style="dim")
        sys.exit(1)
    finally:
        if log_file_ctx:
            log_file_ctx.close()

if __name__ == "__main__":
    main()
