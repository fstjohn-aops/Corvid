#!/bin/bash

set -euo pipefail

# Test hostname - change this to whatever you want to test with
FULL_HOSTNAME="deploytest1.aopstest.com"

INVENTORY_FILE="/Users/finnstjohn/Source/Dev-Environment-Ansible-Cfg/inventories/inventory_aops_web_setup_test.yml"

echo "Adding $FULL_HOSTNAME to inventory groups..."

# Add hostname to the top of aops_web_setup_test hosts section
sed -i '' "/aops_web_setup_test:/,/hosts:/{
    /hosts:/a\\
                        $FULL_HOSTNAME:
    }" "$INVENTORY_FILE"

# Add hostname to the top of alpha_aws_aops_dev hosts section  
sed -i '' "/alpha_aws_aops_dev:/,/hosts:/{
    /hosts:/a\\
                $FULL_HOSTNAME:
    }" "$INVENTORY_FILE"

# Add hostname to the top of classroom6_and_aops_combined_servers hosts section
sed -i '' "/classroom6_and_aops_combined_servers:/,/hosts:/{
    /hosts:/a\\
                $FULL_HOSTNAME:
    }" "$INVENTORY_FILE"

echo "✅ Added $FULL_HOSTNAME to all three inventory groups!" 