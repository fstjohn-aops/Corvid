#!/bin/bash

# Simple script to replace A records in Terraform state for all aops_dev environments

set -e

echo "=== Terraform DNS Record State Replacement Script ==="
echo

# Check if Cloudflare API token is set
if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo "❌ Error: CLOUDFLARE_API_TOKEN environment variable is not set"
    echo "Please set it with: export CLOUDFLARE_API_TOKEN=your_token_here"
    exit 1
fi

echo "✅ Cloudflare API token found"
echo

# Get zone ID
read -p "Enter the Cloudflare Zone ID: " ZONE_ID

echo
echo "=== Fetching all A records from zone ==="
echo

# Get all A records with pagination
page=1
while true; do
    echo "=== Page $page ==="
    response=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=A&page=$page&per_page=100" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type: application/json")
    
    echo "$response" | jq -r '.result[] | "\(.name) - ID: \(.id)"'
    
    total_pages=$(echo "$response" | jq -r '.result_info.total_pages')
    if [ "$page" -ge "$total_pages" ]; then
        break
    fi
    ((page++))
done

echo
echo "=== Starting import process ==="
echo

# Base directory
BASE_DIR="/Users/finnstjohn/Source/terramate-cloud/stacks/accounts/aops_dev.487718497406"

# List of environment directories (hardcoded for speed)
ENVIRONMENTS=(
    "curriculum-systems-1.aopstest.com"
    "curriculum-systems-2.aopstest.com"
    "deploy-test-2.aopstest.com"
    "eg.aopstest.com"
    "ha.aopstest.com"
    "jp.aopstest.com"
    "operations-hub-1.aopstest.com"
    "operations-hub-2.aopstest.com"
    "ow.aopstest.com"
    "rg.aopstest.com"
    "school-partnerships.aopstest.com"
    "th.aopstest.com"
)

# Process each environment
for env in "${ENVIRONMENTS[@]}"; do
    echo "----------------------------------------"
    echo "Processing: $env"
    echo "----------------------------------------"
    
    # Get record ID for this environment
    read -p "Enter DNS Record ID for $env (or 'skip' to skip): " RECORD_ID
    
    if [ "$RECORD_ID" = "skip" ]; then
        echo "Skipping $env"
        continue
    fi
    
    # Change to environment directory
    cd "$BASE_DIR/$env"
    echo "Changed to: $(pwd)"
    
    # Remove from state
    echo "Removing from state..."
    terraform state rm module.ec2_instance.cloudflare_dns_record.a_record || echo "Record not in state (might be OK)"
    
    # Import new record
    echo "Importing new record..."
    terraform import module.ec2_instance.cloudflare_dns_record.a_record "$ZONE_ID/$RECORD_ID"
    
    echo "✅ Completed $env"
    echo
done

echo "=== All done! ==="
