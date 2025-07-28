#!/bin/bash

set -euo pipefail

# Configuration - modify these values as needed
ROLE="AoPS-Dev.AWSAdministratorAccess"
REGION="us-west-2"

echo "=== EC2 Instance Tagging Wizard ==="
echo

# Get tag key
read -p "Enter tag key: " TAG_KEY
if [ -z "$TAG_KEY" ]; then
    echo "Error: Tag key cannot be empty"
    exit 1
fi

# Get tag value
read -p "Enter tag value: " TAG_VALUE
if [ -z "$TAG_VALUE" ]; then
    echo "Error: Tag value cannot be empty"
    exit 1
fi

echo
echo "Enter instance IDs or names (one per line). Type 'done' when finished:"
echo

# Collect instances
INSTANCES=()
while true; do
    read -p "Instance: " INSTANCE
    if [ "$INSTANCE" = "done" ] || [ "$INSTANCE" = "Done" ] || [ "$INSTANCE" = "DONE" ]; then
        break
    fi
    if [ -n "$INSTANCE" ]; then
        INSTANCES+=("$INSTANCE")
    fi
done

# Check if we have any instances
if [ ${#INSTANCES[@]} -eq 0 ]; then
    echo "Error: No instances provided"
    exit 1
fi

echo
echo "=== Summary ==="
echo "Tag: $TAG_KEY=$TAG_VALUE"
echo "Instances: ${INSTANCES[*]}"
echo "Role: $ROLE"
echo "Region: $REGION"
echo

read -p "Proceed with tagging? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Operation cancelled"
    exit 0
fi

echo
echo "=== Applying Tags ==="

# Apply tag to each instance
for INSTANCE in "${INSTANCES[@]}"; do
    echo "Applying tag $TAG_KEY=$TAG_VALUE to instance: $INSTANCE"
    
    COMMAND="aws ec2 create-tags --resources $INSTANCE --tags Key=$TAG_KEY,Value=$TAG_VALUE --region $REGION"
    FORCE_NO_ALIAS=true assume $ROLE --exec -- $COMMAND
    
    echo "Tag applied successfully to $INSTANCE"
    echo
done

echo "All tags applied successfully!"
