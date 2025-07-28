#!/bin/bash

set -eu

if [ $# -ne 1 ]; then
    echo "Usage: $0 <PREFIX>"
    exit 1
fi

PREFIX="$1"
FULL_HOSTNAME="$PREFIX.aopstest.com"

# expects the stack to exist

source ~/tokens

pushd ~/Source/terramate-cloud/stacks/accounts/aops_dev.487718497406/$FULL_HOSTNAME

terraform init || {
    echo
    echo "    ❌ terraform init failed!"
    echo "    💡 try running this command: assume Eng-Atlantis.AWSAdministratorAccess"
    echo
    exit 1
}

terraform destroy || {
    echo
    echo "    ❌ terraform destroy failed!"
    echo "    💡 try running this command: assume Eng-Atlantis.AWSAdministratorAccess"
    echo
    exit 1
}

popd

echo "🧹 Cleaning up ansible inventory..."

# Remove from inventory file
INVENTORY_FILE="/Users/finnstjohn/Source/Dev-Environment-Ansible-Cfg/inventories/inventory_aops_web_setup_test.yml"

# Remove hostname from all three inventory groups
sed -i '' "/$FULL_HOSTNAME:/d" "$INVENTORY_FILE"

# Remove host_vars directory
HOST_VARS_DIR="/Users/finnstjohn/Source/Dev-Environment-Ansible-Cfg/host_vars/$FULL_HOSTNAME"
if [ -d "$HOST_VARS_DIR" ]; then
    rm -rf "$HOST_VARS_DIR"
    echo "✅ Removed host_vars directory for $FULL_HOSTNAME"
else
    echo "ℹ️  No host_vars directory found for $FULL_HOSTNAME"
fi

echo "✅ Cleaned up ansible inventory for $FULL_HOSTNAME"

remove-host-from-known-hosts.sh "$FULL_HOSTNAME"

echo "✅ Destroyed $FULL_HOSTNAME"