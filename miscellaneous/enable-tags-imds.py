#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "boto3>=1.26.0",
#   "rich>=13.0.0",
# ]
# ///

import sys
import argparse
from typing import List, Tuple

import boto3
from botocore.exceptions import ClientError
from rich.console import Console

console = Console()
stderr_console = Console(stderr=True)

DEFAULT_US_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enable EC2 Instance Metadata Tags for specified instance IDs across regions"
    )
    parser.add_argument(
        "--ids",
        "-i",
        required=True,
        help="Comma-separated list of EC2 instance IDs (e.g. i-abc123,i-def456)",
    )
    parser.add_argument(
        "--regions",
        "-r",
        default=None,
        help="Comma-separated AWS regions to search (default: us-east-1,us-east-2,us-west-1,us-west-2)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose error output to stderr",
    )
    args = parser.parse_args()

    # Normalize regions
    if args.regions:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    else:
        regions = list(DEFAULT_US_REGIONS)

    # Normalize instance IDs
    instance_ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    if not instance_ids:
        stderr_console.print("No instance IDs provided after parsing.", style="red")
        sys.exit(2)

    args.instance_ids = instance_ids
    args.region_list = regions
    return args


def find_instance_region(instance_id: str, regions: List[str]) -> Tuple[str, str]:
    """Return (region, message) where the instance was found, or ("", reason) if not found.

    Does lightweight describe to determine presence. Continues on NotFound; surfaces
    other errors as message while continuing to other regions.
    """
    last_error_message = ""
    for region in regions:
        ec2 = boto3.client("ec2", region_name=region)
        try:
            ec2.describe_instances(InstanceIds=[instance_id])
            return region, ""
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("InvalidInstanceID.NotFound", "InvalidInstanceID.Malformed"):
                continue
            last_error_message = f"{region}:{code}"
            # Try next region regardless
            continue
        except Exception as e:  # pragma: no cover - defensive
            last_error_message = f"{region}:{type(e).__name__}"
            continue
    return "", (last_error_message or "not_found")


def enable_imds_tags(instance_id: str, region: str) -> Tuple[str, str]:
    """Enable Instance Metadata Tags for the instance in the specified region.

    Returns (status, message) where status is one of: enabled, already_enabled, error.
    """
    ec2 = boto3.client("ec2", region_name=region)
    try:
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        inst = desc["Reservations"][0]["Instances"][0]
        current = inst.get("MetadataOptions", {}).get("InstanceMetadataTags", "disabled")
        if current == "enabled":
            return "already_enabled", ""
        ec2.modify_instance_metadata_options(
            InstanceId=instance_id,
            InstanceMetadataTags="enabled",
        )
        return "enabled", ""
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        return "error", code
    except Exception as e:  # pragma: no cover - defensive
        return "error", type(e).__name__


def main():
    args = parse_arguments()

    total = len(args.instance_ids)

    for index, instance_id in enumerate(args.instance_ids, start=1):
        with stderr_console.status(
            f"[{index}/{total}] Searching {instance_id} across regions...", spinner="dots"
        ):
            region, find_message = find_instance_region(instance_id, args.region_list)

        if not region:
            # Not found anywhere
            stderr_console.print(f"{index}/{total} complete", style="dim")
            continue

        with stderr_console.status(
            f"[{index}/{total}] Enabling IMDS tags for {instance_id} in {region}...",
            spinner="line",
        ):
            status, message = enable_imds_tags(instance_id, region)

        stderr_console.print(f"{index}/{total} complete", style="dim")


if __name__ == "__main__":
    main()
