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
DEFAULT_VAULT_PASSWORD_FILE = str(Path.home() / ".aops_ansible_vault_pw")
DEFAULT_TERRAMATE_CLOUD_REPO = "git@github.com:aops-ba/terramate-cloud.git"
DEFAULT_ANSIBLE_CONFIG_REPO = "git@github.com:aops-ba/ansible-cfg.git"
DEFAULT_BOOTSTRAP_SSH_KEY = str(Path.home() / ".ssh/bootstrap_key")
DEFAULT_ANSIBLECONTROL_SSH_KEY = str(Path.home() / ".ssh/ansible_control_key")
DEFAULT_TERRAFORM_TEMPLATE_FILE = str(Path(__file__).parent / "test_instance.tf.template")
DEFAULT_EMAIL = "devops@artofproblemsolving.com"
DEFAULT_OFFICE_VPN_IP = "50.203.25.222"
DEFAULT_STACK_ACCOUNT_PATH = "stacks/accounts/aops_dev.487718497406"
REQUIRED_DEPENDENCIES = [
    "git", "terraform", "aws", "ssh-import-db.sh", "yq", "play", "terramate"
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
    parser = argparse.ArgumentParser(description="Create a new test EC2 instance and configure it.")
    parser.add_argument("prefix", help="Prefix for the new instance (alphanumeric)")
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

# Timed operation for creating stack directory
@dimmed_timed_step("Creating stack directory", lambda result, *a, **k: f"Created stack directory at {result}")
def create_stack_directory(stack_path, terramate_cloud_path, full_hostname, verbose, log_file, debug):
    run(["terramate", "create", f"stacks/accounts/aops_dev.487718497406/{full_hostname}"], cwd=terramate_cloud_path, verbose=verbose, log_file=log_file, debug=debug)
    return stack_path

# Timed operation for copying template
def copy_template(terraform_template_file, main_tf, prefix):
    with open(terraform_template_file) as src, open(main_tf, "w") as dst:
        dst.write(src.read().replace("TERRAFORM_STACK_PREFIX_PLACEHOLDER", prefix))
    return main_tf

# =============================
# MAJOR STEP FUNCTIONS
# =============================

# Redefine all major operations to use only dimmed_timed_step
@dimmed_timed_step("Creating and applying terraform stack...", lambda result, *a, **k: f"Created and applied Terraform stack at {k.get('stack_path', '<unknown>')}")
def create_and_apply_terraform_stack(stack_path, terramate_cloud_path, prefix, full_hostname, terraform_template_file, log_file, ci):
    if not stack_path.exists():
        run(["terramate", "create", f"stacks/accounts/aops_dev.487718497406/{full_hostname}"], cwd=terramate_cloud_path, log_file=log_file, debug=DEBUG_MODE)
    main_tf = stack_path / "main.tf"
    if not main_tf.exists():
        with open(terraform_template_file) as src, open(main_tf, "w") as dst:
            dst.write(src.read().replace("TERRAFORM_STACK_PREFIX_PLACEHOLDER", prefix))
    run(["git", "add", "."], cwd=terramate_cloud_path, log_file=log_file, debug=DEBUG_MODE)
    run(["git", "commit", "-m", f"Create or update test instance {full_hostname}"], cwd=terramate_cloud_path, check=False, log_file=log_file, debug=DEBUG_MODE)
    run(["git", "push", "origin", "main"], cwd=terramate_cloud_path, log_file=log_file, debug=DEBUG_MODE)
    run(["terraform", "init"], cwd=stack_path, log_file=log_file, debug=DEBUG_MODE)
    # Add auto-approve flag when running in CI mode
    terraform_apply_cmd = ["terraform", "apply"]
    if ci:
        terraform_apply_cmd.append("-auto-approve")
    run(terraform_apply_cmd, cwd=stack_path, log_file=log_file, debug=DEBUG_MODE)
    return stack_path

@dimmed_timed_step("Adding host to inventory and emails.yml...", lambda result, *a, **k: f"Added {k.get('full_hostname', '<host>')} to inventory and emails.yml in {k.get('ansible_config_root', '<root>')}")
def add_to_ansible_inventory(ansible_config_root, full_hostname, email, log_file):
    inventory_mgr = InventoryManager(ansible_config_root)
    inventory_mgr.ensure_host(
        full_hostname=full_hostname,
        email=email,
        log_file=log_file
    )
    return ansible_config_root

@dimmed_timed_step("Running ansible against the new host...", lambda result, *a, **k: f"Ran Ansible playbooks for {k.get('full_hostname', '<host>')}")
def run_ansible(ansible_config_root, full_hostname, bootstrap_ssh_key, ansiblecontrol_ssh_key, vault_password_file, log_file):
    run([
        "ansible-playbook", "initial_setup.yml",
        "--private-key", bootstrap_ssh_key,
        "--limit", full_hostname,
        "--vault-password-file", vault_password_file,
        "--ssh-common-args", "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
    ], cwd=ansible_config_root, log_file=log_file, debug=DEBUG_MODE)
    run([
        "ansible-playbook", "web_setup.yml",
        "--private-key", ansiblecontrol_ssh_key,
        "--limit", full_hostname,
        "--vault-password-file", vault_password_file,
        "--ssh-common-args", "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
    ], cwd=ansible_config_root, log_file=log_file, debug=DEBUG_MODE)
    return full_hostname

@dimmed_timed_step("Importing database", lambda result, *a, **k: f"Imported database for {result}")
def import_db(full_hostname, log_file):
    run(["ssh-import-db.sh", full_hostname], log_file=log_file, debug=DEBUG_MODE)
    return full_hostname

# =============================
# INVENTORY/EMAIL MANAGEMENT
# =============================

class InventoryManager:
    def __init__(self, ansible_config_root: Path):
        self.ansible_config_root = Path(ansible_config_root)
        self.inventory_file = self.ansible_config_root / "inventory.yml"
        self.emails_file = self.ansible_config_root / "group_vars/all/emails.yml"

    def add_host_to_inventory(self, full_hostname: str):
        lines = self.inventory_file.read_text().splitlines(keepends=True)
        out = []
        inserted = False
        for i, line in enumerate(lines):
            out.append(line)
            if not inserted and line.strip() == 'hosts:':
                indent = len(line) - len(line.lstrip()) + 2
                out.append(' ' * indent + f'{full_hostname}:\n')
                inserted = True
        self.inventory_file.write_text(''.join(out))

    def add_email_for_host(self, full_hostname: str, email: str):
        with open(self.emails_file) as f:
            emails = yaml.safe_load(f)
        if "host_emails" not in emails:
            emails["host_emails"] = {}
        if full_hostname not in emails["host_emails"]:
            emails["host_emails"][full_hostname] = email
            with open(self.emails_file, "w") as f:
                yaml.safe_dump(emails, f, default_flow_style=False)
            return True
        return False

    def ensure_host(self, full_hostname: str, email: str, log_file):
        inventory_lines = self.inventory_file.read_text()
        if f'{full_hostname}:' not in inventory_lines:
            self.add_host_to_inventory(full_hostname)
        self.add_email_for_host(full_hostname, email)
        if DEBUG_MODE:
            console.print(f"[dim]Committing and pushing Ansible inventory changes...[/dim]")
        run(["git", "add", str(self.inventory_file), str(self.emails_file)], cwd=self.ansible_config_root, log_file=log_file, debug=DEBUG_MODE)
        run(["git", "commit", "-m", f"Add {full_hostname} to inventory and emails.yml"], cwd=self.ansible_config_root, check=False, log_file=log_file, debug=DEBUG_MODE)
        run(["git", "push", "origin", "simple"], cwd=self.ansible_config_root, log_file=log_file, debug=DEBUG_MODE)

# =============================
# MAIN EXECUTION
# =============================

def print_step_header(step_num, step_desc):
    # Use a pretty unicode box-drawing symbol for the header
    bar = '━'
    header = f"{bar*3} [{step_num}/5] {step_desc} {bar*3}"
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

    # Config
    ansible_cfg_branch = get_env("ANSIBLE_CFG_BRANCH", DEFAULT_ANSIBLE_CFG_BRANCH)
    vault_password_file = get_env("VAULT_PASSWORD_FILE", DEFAULT_VAULT_PASSWORD_FILE)
    terramate_cloud_repo = get_env("TERRAMATE_CLOUD_REPO", DEFAULT_TERRAMATE_CLOUD_REPO)
    ansible_config_repo = get_env("ANSIBLE_CONFIG_REPO", DEFAULT_ANSIBLE_CONFIG_REPO)
    bootstrap_ssh_key = get_env("BOOTSTRAP_SSH_KEY", DEFAULT_BOOTSTRAP_SSH_KEY)
    ansiblecontrol_ssh_key = get_env("ANSIBLECONTROL_SSH_KEY", DEFAULT_ANSIBLECONTROL_SSH_KEY)
    terraform_template_file = DEFAULT_TERRAFORM_TEMPLATE_FILE
    email = get_env("EMAIL", DEFAULT_EMAIL)
    office_vpn_ip = get_env("OFFICE_VPN_IP", DEFAULT_OFFICE_VPN_IP)

    log_file_ctx = tempfile.NamedTemporaryFile("w+t", delete=False, prefix="create-test-instance-", suffix=".log") if not DEBUG_MODE else None
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

        print_step_header(2, "Creating and applying terraform stack")
        create_and_apply_terraform_stack(
            log_file=log_file,
            stack_path=stack_path,
            terramate_cloud_path=terramate_cloud_path,
            prefix=prefix,
            full_hostname=full_hostname,
            terraform_template_file=terraform_template_file,
            ci=ci
        )
        prompt_to_continue(ci)

        print_step_header(3, "Adding host to inventory and emails.yml")
        add_to_ansible_inventory(
            ansible_config_root=ansible_config_root,
            full_hostname=full_hostname,
            email=email,
            log_file=log_file
        )
        prompt_to_continue(ci)

        print_step_header(4, "Running ansible against the new host")
        run_ansible(
            ansible_config_root=ansible_config_root,
            full_hostname=full_hostname,
            bootstrap_ssh_key=bootstrap_ssh_key,
            ansiblecontrol_ssh_key=ansiblecontrol_ssh_key,
            vault_password_file=vault_password_file,
            log_file=log_file
        )
        prompt_to_continue(ci)

        print_step_header(5, "Importing database")
        import_db(full_hostname, log_file)
        if DEBUG_MODE:
            console.print(f"[green]All steps completed successfully![/green]")
        else:
            console.print(f"All steps completed successfully!", style="dim")
            console.print(f"Log file: \n{log_path}", style="dim")
        # Play a sound (optional, if play is available)
        if shutil.which("play"):
            for freq in (880, 990, 1100):
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
