#!/bin/bash

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <PREFIX>"
    exit 1
fi

PREFIX="$1"
FULL_HOSTNAME="$PREFIX.aopstest.com"

if ! [[ "$PREFIX" =~ ^[a-zA-Z0-9]+$ ]]; then
    echo "ERROR: PREFIX must be alphanumeric (letters and numbers only)."
    exit 1
fi

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
        echo "    ❌ terraform init failed!"
        echo "    💡 try running this command: assume DevOps.AWSAdministratorAccess"
        echo
        exit 1
    }
    terraform destroy -auto-approve || {
        echo
        echo "    ❌ terraform destroy failed!"
        echo "    💡 try running this command: assume DevOps.AWSAdministratorAccess"
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

# Remove from Ansible inventory and host_vars
echo "🧹 Cleaning up ansible inventory..."
pushd "$ANSIBLE_CONFIG_ROOT"
git checkout main
git pull

# Remove hostname from all inventory groups
sed -i '' "/$FULL_HOSTNAME:/d" "$INVENTORY_FILE"

# Remove host_vars directory
if [ -d "$HOST_VARS_DIR" ]; then
    rm -rf "$HOST_VARS_DIR"
    echo "✅ Removed host_vars directory for $FULL_HOSTNAME"
else
    echo "ℹ️  No host_vars directory found for $FULL_HOSTNAME"
fi

git add .
git commit -m "Remove $FULL_HOSTNAME from inventory and host_vars" || echo "No changes to commit in Ansible repo."
git push origin main
popd

echo "✅ Cleaned up ansible inventory for $FULL_HOSTNAME"

remove-host-from-known-hosts.sh "$FULL_HOSTNAME"
echo "✅ Destroyed $FULL_HOSTNAME"

play -q -n synth 0.1 sin 1100
play -q -n synth 0.1 sin 990
play -q -n synth 0.1 sin 880
