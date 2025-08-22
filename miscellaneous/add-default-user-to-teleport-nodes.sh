#!/bin/bash

# Simple script to list all teleport nodes as JSON
# Store hostnames in an array for iteration
hostnames=($(tsh ls --format=json | jq -r '.[].spec.hostname'))

# List of users to try (you can populate this)
users=("ec2-user" "ubuntu" "cloud-user" "centos")

# Limit the number of hosts to run SSH commands on
limit=1

# Show max 10 nodes, add ellipses if more
max_display=10

# Function to manage teleport configuration
manage_teleport_config() {
    local target_user="${1:-}"
    
    echo "=== Teleport Configuration Management ==="
    
    # Task 1: Check if user variable is defined
    echo "Task 1: Checking if user variable is defined..."
    if [[ -z "$target_user" ]]; then
        echo "  Error: No user specified. Usage: manage_teleport_config <username>"
        return 1
    fi
    echo "  User variable defined: $target_user"
    
    # Task 2: Check if that user exists
    echo "Task 2: Checking if user '$target_user' exists..."
    if id "$target_user" &>/dev/null; then
        echo "  User '$target_user' exists"
    else
        echo "  Error: User '$target_user' does not exist"
        return 1
    fi
    
    # Task 3: Add user's name to /etc/teleport/aops-default-user
    echo "Task 3: Adding user name to /etc/teleport/aops-default-user..."
    if [[ ! -d "/etc/teleport" ]]; then
        echo "  Creating /etc/teleport directory..."
        sudo mkdir -p /etc/teleport
    fi
    echo "$target_user" | sudo tee /etc/teleport/aops-default-user > /dev/null
    echo "  User name written to /etc/teleport/aops-default-user"
    
    # Task 4: Install yq
    echo "Task 4: Installing yq..."
    if ! command -v yq &> /dev/null; then
        echo "  Downloading yq from GitHub releases..."
        # Detect architecture for Linux hosts
        if [[ "$(uname -m)" == "aarch64" ]]; then
            yq_url="https://github.com/mikefarah/yq/releases/download/v4.47.1/yq_linux_arm64"
        else
            yq_url="https://github.com/mikefarah/yq/releases/download/v4.47.1/yq_linux_amd64"
        fi
        
        # Download and install yq
        sudo curl -L "$yq_url" -o /usr/local/bin/yq
        sudo chmod +x /usr/local/bin/yq
        echo "  yq installed successfully"
    else
        echo "  yq already installed"
    fi
    
    # Task 5: Read /etc/teleport.yaml and add the new command
    echo "Task 5: Modifying /etc/teleport.yaml..."
    if [[ ! -f "/etc/teleport.yaml" ]]; then
        echo "  Error: /etc/teleport.yaml not found"
        return 1
    fi
    
    # Create backup
    sudo cp /etc/teleport.yaml /etc/teleport.yaml.backup
    echo "  Backup created: /etc/teleport.yaml.backup"
    
    # Add the new command to ssh_service.commands
    if yq eval '.ssh_service.commands[0].name == "AoPS Default User"' /etc/teleport.yaml &>/dev/null; then
        echo "  Command already exists, updating..."
        yq eval '.ssh_service.commands[0] = {"name": "AoPS-Default-User", "command": ["/bin/cat", "/etc/teleport/aops-default-user"], "period": "12h0m0s"}' /etc/teleport.yaml | sudo tee /etc/teleport.yaml > /dev/null
    else
        echo "  Adding new command..."
        yq eval '.ssh_service.commands += [{"name": "AoPS-Default-User", "command": ["/bin/cat", "/etc/teleport/aops-default-user"], "period": "12h0m0s"}]' /etc/teleport.yaml | sudo tee /etc/teleport.yaml > /dev/null
    fi
    echo "  /etc/teleport.yaml updated successfully"
    
    # Task 6: Uninstall yq
    echo "Task 6: Uninstalling yq..."
    if command -v yq &> /dev/null; then
        if command -v brew &> /dev/null; then
            echo "  Uninstalling yq via Homebrew..."
            brew uninstall yq
        elif command -v apt-get &> /dev/null; then
            echo "  Uninstalling yq via apt..."
            sudo apt-get remove -y yq
        elif command -v yum &> /dev/null; then
            echo "  Uninstalling yq via yum..."
            sudo yum remove -y yq
        else
            echo "  Warning: Could not uninstall yq automatically"
        fi
    fi
    
    # Task 7: Reload teleport service
    echo "Task 7: Reloading teleport service..."
    if sudo systemctl reload teleport; then
        echo "  Teleport service reloaded successfully"
    else
        echo "  Warning: Failed to reload teleport service. You may need to restart manually."
        echo "  Try: sudo systemctl restart teleport"
    fi
    
    echo "=== Teleport Configuration Management Complete ==="
    echo "Summary:"
    echo "  - User '$target_user' verified and configured"
    echo "  - /etc/teleport/aops-default-user created"
    echo "  - /etc/teleport.yaml updated with new command"
    echo "  - Backup created at /etc/teleport.yaml.backup"
}

# Now you can iterate over the hostnames
echo "Found ${#hostnames[@]} nodes:"

for i in "${!hostnames[@]}"; do
    if [[ $i -ge $max_display ]]; then
        echo "  ... and $(( ${#hostnames[@]} - max_display )) more nodes"
        break
    fi
    echo "  - ${hostnames[$i]}"
done

echo ""
echo "SSH'ing to each host and running command (limited to $limit hosts)..."

# SSH to each host and run the command (limited by the limit constant)
host_count=0
for hostname in "${hostnames[@]}"; do
    if [[ $host_count -ge $limit ]]; then
        echo "Reached limit of $limit hosts, stopping..."
        break
    fi
    
    echo "Connecting to $hostname..."
    
    # Try each user until one works
    connected=false
    successful_user=""
    for user in "${users[@]}"; do
        if tsh ssh "$user@$hostname" echo "Connection test successful" 2>/dev/null; then
            echo "  Success with user: $user"
            connected=true
            successful_user="$user"
            break
        else
            echo "  Failed with user: $user"
        fi
    done
    
    if [[ "$connected" == "true" ]]; then
        echo "  Running teleport configuration management as $successful_user..."
        # Run the teleport config management function on this host
        tsh ssh "$successful_user@$hostname" "$(declare -f manage_teleport_config); manage_teleport_config '$successful_user'"
    else
        echo "  Failed to connect with any user"
    fi
    
    echo ""
    ((host_count++))
done
