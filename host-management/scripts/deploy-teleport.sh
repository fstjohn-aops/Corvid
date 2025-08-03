#!/bin/bash

set -eou pipefail

# Configuration
HOSTS=(
    "teleport-test.aopstest.com"
)
TARGET_USER="ec2-user"
KEY="/Users/finnstjohn/.ssh/id_ed25519_devops"

# Loop through each host
for TARGET_HOST in "${HOSTS[@]}"; do
    echo "About to deploy to $TARGET_HOST..."
    read -p "Press Enter to continue or Ctrl+C to abort: "
    
    echo "Deploying to $TARGET_HOST..."
    
    # Copy ansible playbooks to remote host
    scp -i "$KEY" -r aops-ansible-playbooks "$TARGET_USER@$TARGET_HOST:/tmp/"
    
    # Check if apt update works first
    echo "Checking if apt update works on $TARGET_HOST..."
    if ! ssh -i "$KEY" "$TARGET_USER@$TARGET_HOST" "sudo apt update"; then
        echo "apt update failed on $TARGET_HOST. This is likely due to broken repository configurations."
        echo "Would you like to disable problematic repositories and retry?"
        echo "This will rename postgresql_org_pub.list and nginx.list to .bak files"
        read -p "Continue with repo cleanup? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Disabling problematic repositories on $TARGET_HOST..."
            ssh -i "$KEY" "$TARGET_USER@$TARGET_HOST" << 'EOF'
                sudo mv /etc/apt/sources.list.d/postgresql_org_pub.list /etc/apt/sources.list.d/postgresql_org_pub.list.bak 2>/dev/null || true
                sudo mv /etc/apt/sources.list.d/nginx.list /etc/apt/sources.list.d/nginx.list.bak 2>/dev/null || true
                echo "Retrying apt update..."
                sudo apt update
EOF
        else
            echo "Skipping repo cleanup. Installation may fail."
        fi
    fi
    
    # SSH to host and run installation commands
    ssh -i "$KEY" "$TARGET_USER@$TARGET_HOST" << 'EOF'
        # Install ansible via pip for latest version
        echo "Installing python3-pip..."
        sudo apt install python3-pip -y
        
        # Install ansible and boto dependencies with pip
        echo "Installing ansible and AWS dependencies..."
        # Install PyYAML first with a compatible version for Python 3.5
        pip3 install --user ansible boto3 botocore
        
        # Add ~/.local/bin to PATH for this session
        export PATH="$HOME/.local/bin:$PATH"
        
        # Install required ansible collections
        ansible-galaxy collection install amazon.aws
        
        # Go to playbooks directory and run teleport installation
        cd /tmp/aops-ansible-playbooks/playbooks/install-teleport
        ansible-playbook local.yml
        
        # Clean up
        rm -rf /tmp/aops-ansible-playbooks
EOF
    
    echo "Finished deploying to $TARGET_HOST"
done

echo "All deployments completed!" 