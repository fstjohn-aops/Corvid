#!/bin/bash

# Script to check and clean up environment variable exports from shell history
# across all Teleport nodes

set -u
# NOTE: We do NOT use 'set -euo pipefail' here because we want the script to continue even if some nodes or users fail.
# set -euo pipefail

# Signal handling for graceful interruption
cleanup() {
    print_status $YELLOW "\nReceived interrupt signal. Cleaning up..."
    print_status $YELLOW "Script interrupted. Summary of progress:"
    print_status $GREEN "Successfully processed: $processed nodes"
    if [[ $failed -gt 0 ]]; then
        print_status $RED "Failed to process: $failed nodes"
    fi
    exit 1
}

# Set up signal handlers
trap cleanup INT TERM

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Array to store hosts with found secrets
HOSTS_WITH_SECRETS=()

# Global counters for summary
processed=0
failed=0

# Predefined list of users to try
USERS=("website" "ubuntu" "ec2-user" "centos" "cloud-user")

# Environment variables to check for and remove from history
ENV_VARS=(
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_SESSION_TOKEN"
    # add more here if necessary...
)

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] ${message}${NC}"
}

# Function to check if tsh is available and authenticated
check_tsh() {
    if ! command -v tsh &> /dev/null; then
        print_status $RED "Error: tsh is not installed or not in PATH"
        exit 1
    fi
    
    if ! tsh status &> /dev/null; then
        print_status $RED "Error: Not authenticated with Teleport. Please run 'tsh login' first"
        exit 1
    fi
}

# Function to get all hostnames from tsh ls
get_hostnames() {
    # # TEMPORARY: Hardcoded list of 5 test hosts
    # # Replace these with actual hostnames from your environment
    # echo "aops-dev-i-0d7c0bbf0989fa1cf"
    # echo "aops-dev-i-0d91b5f7b05934a5a"
    # echo "aops-dev-i-0f472dd8c40e73a11"
    # echo "aops-dev-i-0cf4f2c7d3e258e7f"
    
    # ORIGINAL CODE (commented out):
    # Get the list of nodes using JSON format
    local json_output
    json_output=$(tsh ls --format=json)
    if [[ $? -ne 0 ]]; then
        print_status $RED "Error: Failed to get node list from tsh ls"
        exit 1
    fi
    
    # Extract hostnames from JSON
    jq -r '.[] | .spec.hostname' <<< "$json_output"
}

# Function to check if a user can connect to a node
can_connect() {
    local hostname=$1
    local user=$2

    tsh ssh "${user}@${hostname}" "echo 'Connection test successful'"
    return $?
}

# Function to clean up environment variable exports from history
# (now: only search and report, do not modify)
report_history_secrets() {
    local hostname=$1
    local user=$2
    
    print_status $YELLOW "Checking for sensitive exports in history on ${user}@${hostname}..."
    
    # Create a script to run on the remote node
    local report_script
    report_script=$(cat <<'EOF'
#!/bin/bash
set -euo pipefail

# Environment variables to check for
ENV_VARS=(
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_SESSION_TOKEN"
    # add more here if necessary...
)

# Function to search a history file for sensitive exports
search_history_file() {
    local history_file=$1
    if [[ ! -f "$history_file" ]]; then
        return 0
    fi
    local found=false
    while IFS= read -r env_var; do
        # Use grep to find lines and print line numbers
        # Look for both export and non-export forms
        grep -nE "^[[:space:]]*(export[[:space:]]+)?$env_var[[:space:]]*=" "$history_file" && found=true
    done < <(printf "%s\n" "${ENV_VARS[@]}")
    if [[ "$found" == "true" ]]; then
        echo "[!] Sensitive exports found in $history_file"
        exit 1
    fi
}

# Bash history
if [[ -n "${HISTFILE:-}" ]]; then
    search_history_file "$HISTFILE"
elif [[ -f "$HOME/.bash_history" ]]; then
    search_history_file "$HOME/.bash_history"
fi

# Zsh history
if [[ -f "$HOME/.zsh_history" ]]; then
    search_history_file "$HOME/.zsh_history"
fi

# Fish history
if [[ -f "$HOME/.local/share/fish/fish_history" ]]; then
    search_history_file "$HOME/.local/share/fish/fish_history"
fi
exit 0
EOF
)
    
    # Execute the report script on the remote node
    echo "$report_script" | tsh ssh "${user}@${hostname}" "bash -s"
    local status=$?
    if [[ $status -eq 0 ]]; then
        print_status $GREEN "Checked history for ${user}@${hostname} - No secrets found"
    else
        print_status $RED "Found secrets in history for ${user}@${hostname}"
        HOSTS_WITH_SECRETS+=("${hostname}:${user}")
    fi
}

# Function to process a single node (read-only mode)
process_node() {
    local hostname=$1
    local success=false
    print_status $BLUE "Processing node: $hostname"
    for user in "${USERS[@]}"; do
        print_status $YELLOW "  Trying user: $user"
        if can_connect "$hostname" "$user"; then
            print_status $GREEN "  Successfully connected as $user@$hostname"
            report_history_secrets "$hostname" "$user"
            success=true
        else
            print_status $YELLOW "  Could not connect as $user@$hostname"
        fi
    done
    if [[ "$success" == "true" ]]; then
        return 0
    else
        print_status $RED "  Could not connect to $hostname with any user"
        return 1
    fi
}

# Main execution
main() {
    print_status $BLUE "Starting Teleport node history cleanup script"
    
    # Check prerequisites
    check_tsh
    
    print_status $BLUE "Getting list of all Teleport nodes..."
    hostnames=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && hostnames+=("$line")
    done < <(get_hostnames)
    
    local total_nodes=${#hostnames[@]}
    if [[ $total_nodes -eq 0 ]]; then
        print_status $RED "Error: No nodes found"
        exit 1
    fi
    
    print_status $GREEN "Found $total_nodes nodes to process"
    
    # Process each node
    local current_node=0
    
    for hostname in "${hostnames[@]}"; do
        ((current_node++))
        print_status $BLUE "Processing node $current_node of $total_nodes: $hostname"
        if process_node "$hostname"; then
            ((processed++))
            print_status $GREEN "Processed $processed nodes so far"
        else
            ((failed++))
            print_status $RED "Failed $failed nodes so far"
        fi
    done
    
    # Summary
    print_status $GREEN "Script completed!"
    print_status $GREEN "Successfully processed: $processed nodes"
    if [[ $failed -gt 0 ]]; then
        print_status $RED "Failed to process: $failed nodes"
    fi

    # Display hosts with secrets found
    if [[ ${#HOSTS_WITH_SECRETS[@]} -gt 0 ]]; then
        print_status $RED "\nFound sensitive environment variables in history on the following hosts:"
        for host_user in "${HOSTS_WITH_SECRETS[@]}"; do
            IFS=':' read -r host user <<< "$host_user"
            echo -e "${RED}  - $host (user: $user)${NC}"
        done
    else
        print_status $GREEN "\nNo sensitive environment variables found in any host's history"
    fi
}

# Run main function
main "$@"
