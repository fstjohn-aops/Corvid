#!/bin/bash

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <hostname>"
    exit 1
fi

HOSTNAME="$1"

# Remove the host from known_hosts
ssh-keygen -R "$HOSTNAME"

echo "✅ Removed $HOSTNAME from known_hosts"
