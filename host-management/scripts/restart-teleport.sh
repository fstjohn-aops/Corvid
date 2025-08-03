#!/bin/bash

set -eou pipefail

HOSTS=(
  baclassroom.aopstest.com
  baclassroom2.aopstest.com
  baclassroom3.aopstest.com
  baclassroom4.aopstest.com
)

KEY_FILE="/Users/finnstjohn/.ssh/id_ed25519_devops"
TARGET_USER="ansiblecontrol"

echo "Teleport will be restarted on the following hosts:"
for h in "${HOSTS[@]}"; do
  echo "  $h"
done
read -p "Press Enter to continue or Ctrl+C to abort: "

for host in "${HOSTS[@]}"; do
  ssh -i "$KEY_FILE" "$TARGET_USER@$host" "sudo systemctl restart teleport"
done
