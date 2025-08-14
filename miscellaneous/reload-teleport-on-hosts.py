#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=13.0.0",
# ]
# ///

import sys
import argparse
import subprocess
from typing import List, Tuple

from rich.console import Console

console = Console()
stderr_console = Console(stderr=True)

# Ordered preference of users to try for SSH
DEFAULT_USERS: List[str] = [
    "ec2-user",
    "cloud-user",
    "website",
    "ubuntu",
    "root",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reload Teleport service on given hosts using tsh ssh"
    )
    parser.add_argument(
        "hosts",
        help="Comma-separated list of hostnames (e.g. node1,node2,node3)",
    )
    parser.add_argument(
        "--users",
        "-u",
        help="Comma-separated list of users to try in order (default: root,ubuntu,ec2-user,admin)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-connection timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print command stderr on failures",
    )
    args = parser.parse_args()

    host_list = [h.strip() for h in args.hosts.split(",") if h.strip()]
    if not host_list:
        stderr_console.print("No hostnames provided after parsing.", style="red")
        sys.exit(2)

    if args.users:
        user_list = [u.strip() for u in args.users.split(",") if u.strip()]
    else:
        user_list = list(DEFAULT_USERS)

    args.host_list = host_list
    args.user_list = user_list
    return args


def reload_teleport_on_host(
    hostname: str,
    users_to_try: List[str],
    timeout_seconds: int,
    verbose: bool,
) -> Tuple[bool, str, str]:
    """Attempt to reload Teleport on the host by trying each user in order.

    Returns (success, user_used, message).
    """
    last_error_message = ""

    for candidate_user in users_to_try:
        cmd = [
            "tsh",
            "ssh",
            f"{candidate_user}@{hostname}",
            "sudo",
            "-n",
            "systemctl",
            "reload",
            "teleport",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            if result.returncode == 0:
                return True, candidate_user, ""
            # Capture stderr if available for diagnostics
            if result.stderr:
                last_error_message = result.stderr.strip().splitlines()[-1]
            else:
                last_error_message = f"exit_code_{result.returncode}"
        except FileNotFoundError:
            return False, "", "tsh_not_found"
        except subprocess.TimeoutExpired:
            last_error_message = "timeout"
        except Exception as e:  # pragma: no cover - defensive
            last_error_message = type(e).__name__

    return False, "", last_error_message or "unknown_error"


def main():
    args = parse_arguments()

    total = len(args.host_list)
    completed = 0

    for index, host in enumerate(args.host_list, start=1):
        with stderr_console.status(
            f"[{index}/{total}] Reloading Teleport on {host}...",
            spinner="dots",
        ):
            success, user_used, message = reload_teleport_on_host(
                host, args.user_list, args.timeout, args.verbose
            )

        completed += 1
        if success:
            stderr_console.print(
                f"[{completed}/{total}] {host}: reloaded via user '{user_used}'",
                style="green",
            )
        else:
            detail = f" ({message})" if (args.verbose and message) else ""
            stderr_console.print(
                f"[{completed}/{total}] {host}: failed{detail}",
                style="red",
            )


if __name__ == "__main__":
    main()
