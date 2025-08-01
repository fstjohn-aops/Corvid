#!/bin/bash

# Exit immediately if any command fails
set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <SEARCH_QUERY>"
    exit 1
fi

SEARCH_QUERY="$1"

# Find the first matching node using tsh ls and jq
NODE_NAME=$(tsh ls --search "$SEARCH_QUERY" --format=json | jq -r '.[0].spec.hostname')

if [ -z "$NODE_NAME" ] || [ "$NODE_NAME" = "null" ]; then
    echo "No matching Teleport node found for query: $SEARCH_QUERY"
    exit 1
fi

echo "Connecting to Teleport node: website@$NODE_NAME"

set +e
tsh ssh website@"$NODE_NAME" "set -e
hostname
echo 'Importing database!'
cd /var/www/aops3
echo 'YES' | sudo ./bin/import-test-database
echo 'Database imported!'
sudo systemctl restart php-fpm
" 
SSH_EXIT_CODE=$?
set -e

if [ $SSH_EXIT_CODE -ne 0 ]; then
    echo "ERROR: Failed to connect as website to $NODE_NAME. The user website may not be valid for this node."
    exit $SSH_EXIT_CODE
fi
