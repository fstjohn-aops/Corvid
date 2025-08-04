#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "boto3>=1.26.0",
#   "rich>=13.9.5",
# ]
# ///

import boto3
import argparse
import sys
from botocore.exceptions import ClientError, ProfileNotFound, CredentialRetrievalError
from rich.console import Console
from botocore.config import Config
import time

# Constants
HEADER = "account_role,instance_id,region,public_ip,private_ip,state,name,key_name"
DEFAULT_REGION_PREFIX = "us-"
EC2_READ_TIMEOUT = 10
EC2_CONNECT_TIMEOUT = 10
MIN_TERMINAL_WIDTH = 40
DEFAULT_TERMINAL_WIDTH = 120


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Find EC2 instances across AWS accounts')
    parser.add_argument('--limit', '-l', type=int, metavar='N', help='Limit to first N profiles (default: all profiles)')
    parser.add_argument('--search', '-s', type=str, default='i-', help='Comma-separated list of substrings to search for (default: "i-")')
    parser.add_argument('--sort', type=str, choices=['account_role', 'instance_id', 'region', 'public_ip', 'private_ip', 'state', 'name', 'key_name'], help='Sort output by column')
    return parser.parse_args()

def get_profiles(limit=None):
    """Get AWS profiles from the current session."""
    session = boto3.Session()
    profiles = session.available_profiles
    if limit and limit > 0:
        profiles = profiles[:limit]
    return profiles

def get_all_regions(profile: str) -> list[str]:
    """Return a list of regions for the given profile, filtered by DEFAULT_REGION_PREFIX."""
    try:
        session = boto3.Session(profile_name=profile)
        ec2 = session.client('ec2', region_name='us-east-1', config=Config(read_timeout=EC2_READ_TIMEOUT, connect_timeout=EC2_CONNECT_TIMEOUT))
        regions = [r['RegionName'] for r in ec2.describe_regions()['Regions']]
        filtered = [r for r in regions if r.startswith(DEFAULT_REGION_PREFIX)]
        return filtered
    except CredentialRetrievalError:
        # Suppress error message, just return empty list
        return []
    except Exception:
        return ['us-east-1']

def find_instances(profile, regions, search_terms):
    """Find EC2 instances matching search terms."""
    results = []
    for region in regions:
        try:
            session = boto3.Session(profile_name=profile, region_name=region)
            ec2 = session.resource('ec2')
            for instance in ec2.instances.all():
                line = [
                    profile,
                    instance.id,
                    region,
                    getattr(instance, 'public_ip_address', '') or '',
                    getattr(instance, 'private_ip_address', '') or '',
                    getattr(instance, 'state', {}).get('Name', ''),
                    next((tag['Value'] for tag in getattr(instance, 'tags', []) or [] if tag['Key'] == 'Name'), ''),
                    getattr(instance, 'key_name', '') or ''
                ]
                line_str = ','.join(str(x) for x in line)
                if any(term in line_str.lower() for term in search_terms):
                    results.append(line)
        except (ClientError, ProfileNotFound):
            continue
        except CredentialRetrievalError:
            print(f"[!] Could not retrieve credentials for profile '{profile}' in region '{region}'. If you use SSO, try running:\n    granted sso login --profile {profile}", file=sys.stderr)
            break
    return results

def print_progress(msg: str, use_single_line: bool, console=None) -> None:
    """Print a progress message, overwriting the current line if in a TTY."""
    import shutil
    if use_single_line:
        width = shutil.get_terminal_size().columns
        if width < MIN_TERMINAL_WIDTH:
            width = DEFAULT_TERMINAL_WIDTH
        sys.stderr.write("\r" + " " * width + "\r")
        sys.stderr.write(f"\x1b[90m{msg}\x1b[0m")
        sys.stderr.flush()
    elif console:
        console.print(msg, style="grey50")

def print_success(msg: str, use_single_line: bool, console=None, timing: float = None) -> None:
    """Print a success message, overwriting the current line if in a TTY. Optionally append timing info."""
    import shutil
    if timing is not None:
        msg = f"{msg} (completed in {timing:.2f}s)"
    if use_single_line:
        width = shutil.get_terminal_size().columns
        if width < MIN_TERMINAL_WIDTH:
            width = DEFAULT_TERMINAL_WIDTH
        sys.stderr.write("\r" + " " * width + "\r")
        sys.stderr.write(f"\x1b[90m{msg}\x1b[0m\n")
    elif console:
        console.print(msg, style="grey50")

def discover_regions(profiles: list[str], console, use_single_line: bool) -> tuple[dict, int, float]:
    """Discover all regions for each profile. Returns (regions_by_profile, total_pairs, elapsed_time). Profiles with no regions (e.g., due to credential errors) are skipped."""
    regions_by_profile = {}
    total_pairs = 0
    start = time.monotonic()
    for idx, profile in enumerate(profiles, 1):
        msg = f"({idx}/{len(profiles)}) Preparing to fetch regions for profile: {profile}"
        print_progress(msg, use_single_line, console)
        regions = get_all_regions(profile)
        if not regions:
            # Print error message on a new line, clear progress line first
            if use_single_line:
                import shutil
                width = shutil.get_terminal_size().columns
                if width < MIN_TERMINAL_WIDTH:
                    width = DEFAULT_TERMINAL_WIDTH
                sys.stderr.write("\r" + " " * width + "\r")
                sys.stderr.write("\n")
                sys.stderr.write("\x1b[2;31m[!] Skipping profile '{}' due to region discovery failure or missing credentials.\x1b[0m\n".format(profile))
                sys.stderr.flush()
                # Note: \x1b[2;31m is dim red, \x1b[0m resets
                
                # If not single line, use rich's dim red
            elif console:
                console.print(f"[!] Skipping profile '{profile}' due to region discovery failure or missing credentials.", style="red dim")
            continue
        regions_by_profile[profile] = regions
        total_pairs += len(regions)
    elapsed = time.monotonic() - start
    print_success("Region discovery complete!", use_single_line, console, elapsed)
    return regions_by_profile, total_pairs, elapsed

def discover_instances(
    profiles: list[str],
    regions_by_profile: dict,
    total_pairs: int,
    search_terms: list[str],
    use_single_line: bool,
    console
) -> list[list[str]]:
    """Discover EC2 instances for each profile/region, returning a list of CSV rows."""
    all_results = []
    current_pair = 0
    start = time.monotonic()
    for profile, regions in regions_by_profile.items():
        results = []
        for region in regions:
            current_pair += 1
            progress_msg = f"({current_pair}/{total_pairs}) Processing profile: {profile}, region: {region}"
            print_progress(progress_msg, use_single_line, console)
            try:
                session = boto3.Session(profile_name=profile, region_name=region)
                ec2 = session.resource('ec2', config=Config(read_timeout=EC2_READ_TIMEOUT, connect_timeout=EC2_CONNECT_TIMEOUT))
                for instance in ec2.instances.all():
                    line = [
                        profile,
                        instance.id,
                        region,
                        getattr(instance, 'public_ip_address', '') or '',
                        getattr(instance, 'private_ip_address', '') or '',
                        getattr(instance, 'state', {}).get('Name', ''),
                        next((tag['Value'] for tag in getattr(instance, 'tags', []) or [] if tag['Key'] == 'Name'), ''),
                        getattr(instance, 'key_name', '') or ''
                    ]
                    line_str = ','.join(str(x) for x in line)
                    if any(term in line_str.lower() for term in search_terms):
                        results.append(line)
            except (ClientError, ProfileNotFound):
                continue
            except CredentialRetrievalError:
                print(f"[!] Could not retrieve credentials for profile '{profile}' in region '{region}'. If you use SSO, try running:\n    granted sso login --profile {profile}", file=sys.stderr)
                break
        all_results.extend(results)
    elapsed = time.monotonic() - start
    print_success("Instance discovery complete!", use_single_line, console, elapsed)
    return all_results

def main() -> None:
    """Main entry point for the script."""
    console = Console(stderr=True)
    args = parse_arguments()
    search_terms = [t.strip().lower() for t in args.search.split(',') if t.strip()]
    profiles = get_profiles(args.limit)
    if not profiles:
        print("No AWS profiles found.", file=sys.stderr)
        sys.exit(1)
    use_single_line = sys.stderr.isatty()
    regions_by_profile, total_pairs, _ = discover_regions(profiles, console, use_single_line)
    all_results = discover_instances(profiles, regions_by_profile, total_pairs, search_terms, use_single_line, console)
    if args.sort:
        idx = HEADER.split(',').index(args.sort)
        all_results.sort(key=lambda x: x[idx])
    print(HEADER)
    for line in all_results:
        print(','.join(str(x) for x in line))
    # Print total hosts found to stderr
    summary = f"Found {len(all_results)} host(s)."
    if use_single_line:
        sys.stderr.write(f"\x1b[90m{summary}\x1b[0m\n")
    else:
        console.print(summary, style="grey50")

if __name__ == "__main__":
    main() 