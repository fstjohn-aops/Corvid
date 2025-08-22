#!/bin/bash

set -euo pipefail

# Branch to use for ansible-cfg
ANSIBLE_CFG_BRANCH="simple"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <PREFIX>"
    exit 1
fi

PREFIX="$1"
FULL_HOSTNAME="$PREFIX.aopstest.com"

if ! [[ "$PREFIX" =~ ^[a-zA-Z0-9-]+$ ]]; then
    echo "ERROR: PREFIX must be alphanumeric with optional dashes (letters, numbers, and dashes only)."
    exit 1
fi

# Validate required tools
validate_environment() {
    local dependencies=("git" "terraform" "aws" "yq")
    for cmd in "${dependencies[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            echo "ERROR: $cmd could not be found, please install it."
            exit 1
        fi
    done
}

validate_environment

# Configuration. Override with environment variables.
TERRAMATE_CLOUD_PATH=${TERRAMATE_CLOUD_PATH:-}
ANSIBLE_CONFIG_ROOT=${ANSIBLE_CONFIG_ROOT:-}
TERRAMATE_CLOUD_REPO="git@github.com:aops-ba/terramate-cloud.git"
ANSIBLE_CONFIG_REPO="git@github.com:aops-ba/ansible-cfg.git"

# Trap for cleanup
trap "echo 'Cleaning up...'; rm -rf '$TERRAMATE_CLOUD_PATH' '$ANSIBLE_CONFIG_ROOT'" EXIT

if [ -z "$TERRAMATE_CLOUD_PATH" ]; then
    TERRAMATE_CLOUD_PATH=$(mktemp -d)
    echo "Cloning Terramate repo to $TERRAMATE_CLOUD_PATH"
    git clone "$TERRAMATE_CLOUD_REPO" "$TERRAMATE_CLOUD_PATH"
fi

if [ -z "$ANSIBLE_CONFIG_ROOT" ]; then
    ANSIBLE_CONFIG_ROOT=$(mktemp -d)
    echo "Cloning Ansible repo to $ANSIBLE_CONFIG_ROOT"
    git clone "$ANSIBLE_CONFIG_REPO" "$ANSIBLE_CONFIG_ROOT"
    pushd "$ANSIBLE_CONFIG_ROOT"
    git checkout "$ANSIBLE_CFG_BRANCH"
    popd
fi

# Derived variables
BASE_PATH="$TERRAMATE_CLOUD_PATH/stacks/accounts/aops_dev.487718497406"
STACK_PATH="$BASE_PATH/$FULL_HOSTNAME"
INVENTORY_FILE="$ANSIBLE_CONFIG_ROOT/inventories/inventory_aops_web_setup_test.yml"
HOST_VARS_DIR="$ANSIBLE_CONFIG_ROOT/host_vars/$FULL_HOSTNAME"

# Check for Cloudflare token
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
    echo "ERROR: CLOUDFLARE_API_TOKEN is not set in the environment."
    exit 1
fi

# Remove Terraform stack and destroy resources
pushd "$TERRAMATE_CLOUD_PATH"
git checkout main
git pull

if [ -d "$STACK_PATH" ]; then
    pushd "$STACK_PATH"
    terraform init || {
        echo
        echo "    terraform init failed!"
        echo "    try running this command: assume DevOps.AWSAdministratorAccess"
        echo
        exit 1
    }
    terraform destroy -auto-approve || {
        echo
        echo "    terraform destroy failed!"
        echo "    try running this command: assume DevOps.AWSAdministratorAccess"
        echo
        exit 1
    }
    popd
    echo "Removing stack directory $STACK_PATH..."
    rm -rf "$STACK_PATH"
    git add .
    git commit -m "Destroy test instance $FULL_HOSTNAME (remove stack)" || echo "No changes to commit in Terramate repo."
    git push origin main
else
    echo "Stack directory $STACK_PATH does not exist. Skipping terraform destroy and removal."
fi
popd

# Remove from emails.yml and inventory.yml
EMAILS_FILE="$ANSIBLE_CONFIG_ROOT/group_vars/all/emails.yml"
INVENTORY_FILE="$ANSIBLE_CONFIG_ROOT/inventory.yml"

# Remove the host entry from host_emails using yq
if [ -f "$EMAILS_FILE" ]; then
    if yq eval ".host_emails | has(\"$FULL_HOSTNAME\")" "$EMAILS_FILE" | grep -q true; then
        yq eval "del(.host_emails.\"$FULL_HOSTNAME\")" -i "$EMAILS_FILE"
        echo "Removed $FULL_HOSTNAME from emails.yml"
    else
        echo "$FULL_HOSTNAME not found in emails.yml"
    fi
else
    echo "Warning: $EMAILS_FILE not found"
fi

# Remove the host entry from inventory.yml using yq
if [ -f "$INVENTORY_FILE" ]; then
    if yq eval ".all.hosts | has(\"$FULL_HOSTNAME\")" "$INVENTORY_FILE" | grep -q true; then
        yq eval "del(.all.hosts.\"$FULL_HOSTNAME\")" -i "$INVENTORY_FILE"
        echo "Removed $FULL_HOSTNAME from inventory.yml"
    else
        echo "$FULL_HOSTNAME not found in inventory.yml"
    fi
else
    echo "Warning: $INVENTORY_FILE not found"
fi

# Commit and push to simple branch
pushd "$ANSIBLE_CONFIG_ROOT"
if [ -n "$(git status --porcelain)" ]; then
    git add "$EMAILS_FILE" "$INVENTORY_FILE"
    git commit -m "Remove $FULL_HOSTNAME from host_emails in emails.yml and inventory.yml"
    git push origin "$ANSIBLE_CFG_BRANCH"
fi
popd

echo "Destroyed $FULL_HOSTNAME"

play -q -n synth 0.1 sin 1100
play -q -n synth 0.1 sin 990
play -q -n synth 0.1 sin 880
