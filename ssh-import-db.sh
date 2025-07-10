#!/bin/bash

# Exit immediately if any command fails
set -ex

if [ $# -ne 2 ]; then
    exit 1
fi

SSH_KEY="$1"
TARGET_HOSTNAME="$2"

if [ ! -f "$SSH_KEY" ]; then
    exit 1
fi

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ec2-user@"$TARGET_HOSTNAME" << 'EOF'
set -e
hostname
sudo su - website << 'WEBSITE_EOF'
set -e

echo "Importing database!"
cd /var/www/aops3
echo "YES" | sudo ./bin/import-test-database
echo "Database imported!"
WEBSITE_EOF

sudo systemctl restart php-fpm

EOF
