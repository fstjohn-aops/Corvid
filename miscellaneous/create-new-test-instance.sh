#!/bin/bash

set -euo pipefail

# =============================
# CONFIGURATION (env vars/constants)
# =============================

if [ $# -ne 1 ]; then
    echo "Usage: $0 <PREFIX>"
    exit 1
fi

PREFIX="$1"
FULL_HOSTNAME="$PREFIX.aopstest.com"

ANSIBLE_CFG_BRANCH="simple"
VAULT_PASSWORD_FILE="${VAULT_PASSWORD_FILE:-$HOME/.aops_ansible_vault_pw}"
TERRAMATE_CLOUD_PATH="${TERRAMATE_CLOUD_PATH:-}"
ANSIBLE_CONFIG_ROOT="${ANSIBLE_CONFIG_ROOT:-}"
TERRAMATE_CLOUD_REPO="git@github.com:aops-ba/terramate-cloud.git"
ANSIBLE_CONFIG_REPO="git@github.com:aops-ba/ansible-cfg.git"
BOOTSTRAP_SSH_KEY="${BOOTSTRAP_SSH_KEY:-$HOME/.ssh/bootstrap_key}"
ANSIBLECONTROL_SSH_KEY="${ANSIBLECONTROL_SSH_KEY:-$HOME/.ssh/ansible_control_key}"
TERRAFORM_TEMPLATE_FILE="$(dirname "$0")/test_instance.tf.template"
EMAIL="${EMAIL:-devops@artofproblemsolving.com}"
OFFICE_VPN_IP="${OFFICE_VPN_IP:-50.203.25.222}"

# Flags indicating whether the repos were cloned by this script (and thus safe to delete on exit)
CLEANUP_TERRAMATE=0
CLEANUP_ANSIBLE=0

# =============================
# FUNCTION DEFINITIONS
# =============================

cleanup() {
    echo "Cleaning up..."
    if [ "${CLEANUP_TERRAMATE:-0}" = "1" ] && [ -n "${TERRAMATE_CLOUD_PATH:-}" ] && [ -d "$TERRAMATE_CLOUD_PATH" ]; then
        rm -rf "$TERRAMATE_CLOUD_PATH"
    fi
    if [ "${CLEANUP_ANSIBLE:-0}" = "1" ] && [ -n "${ANSIBLE_CONFIG_ROOT:-}" ] && [ -d "$ANSIBLE_CONFIG_ROOT" ]; then
        rm -rf "$ANSIBLE_CONFIG_ROOT"
    fi
}

validate_and_check_environment() {

    # Ensure script is being run from the office VPN public IP
    CURRENT_IP=$(curl -s https://checkip.amazonaws.com || curl -s https://ifconfig.me)
    if [ "$CURRENT_IP" != "$OFFICE_VPN_IP" ]; then
        echo "ERROR: Your public IP is $CURRENT_IP, but this script must be run from the office VPN ($OFFICE_VPN_IP)."
        echo "Please connect to the office VPN and try again."
        exit 1
    fi

	# Check required commands
	local dependencies=("git" "terraform" "aws" "ssh-import-db.sh" "yq" "play" "terramate")
	for cmd in "${dependencies[@]}"; do
		if ! command -v "$cmd" &> /dev/null; then
			echo "$cmd could not be found, please install it."
			exit 1
		fi
	done

    # Validate PREFIX
    if ! [[ "$PREFIX" =~ ^[a-zA-Z0-9-]+$ ]]; then
        echo "ERROR: PREFIX must be alphanumeric with optional dashes (letters, numbers, and dashes only)."
        exit 1
fi

    # Expand and resolve SSH keys and vault password file to absolute paths
    BOOTSTRAP_SSH_KEY=$(realpath "$BOOTSTRAP_SSH_KEY")
    ANSIBLECONTROL_SSH_KEY=$(realpath "$ANSIBLECONTROL_SSH_KEY")
    VAULT_PASSWORD_FILE=$(realpath "$VAULT_PASSWORD_FILE")

    # Check required files exist
    for file_var in VAULT_PASSWORD_FILE BOOTSTRAP_SSH_KEY ANSIBLECONTROL_SSH_KEY TERRAFORM_TEMPLATE_FILE; do
        file_path="${!file_var}"
        if [ ! -f "$file_path" ]; then
            echo "ERROR: $file_var not found at $file_path"
            exit 1
        fi
    done

    # Check CLOUDFLARE_API_TOKEN directly
    if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
        echo "ERROR: CLOUDFLARE_API_TOKEN is not set in the environment."
        exit 1
    fi

    # Check AWS credentials
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" && -z "${AWS_PROFILE:-}" ]]; then
        echo "ERROR: No AWS credentials found. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_PROFILE in the environment."
        exit 1
    fi
}

clone_code_and_setup() {
    if [ -z "$TERRAMATE_CLOUD_PATH" ]; then
        TERRAMATE_CLOUD_PATH=$(mktemp -d)
        echo "Cloning Terramate repo to $TERRAMATE_CLOUD_PATH"
        git clone "$TERRAMATE_CLOUD_REPO" "$TERRAMATE_CLOUD_PATH"
        CLEANUP_TERRAMATE=1
    fi
    if [ -z "$ANSIBLE_CONFIG_ROOT" ]; then
        ANSIBLE_CONFIG_ROOT=$(mktemp -d)
        echo "Cloning Ansible repo to $ANSIBLE_CONFIG_ROOT"
        git clone "$ANSIBLE_CONFIG_REPO" "$ANSIBLE_CONFIG_ROOT"
        pushd "$ANSIBLE_CONFIG_ROOT"
        git checkout "$ANSIBLE_CFG_BRANCH"
        popd
        CLEANUP_ANSIBLE=1
    fi
    BASE_PATH="$TERRAMATE_CLOUD_PATH/stacks/accounts/aops_dev.487718497406"
    STACK_PATH="$BASE_PATH/$FULL_HOSTNAME"
    trap cleanup EXIT
}

create_and_apply_terraform_stack() {
    pushd "$TERRAMATE_CLOUD_PATH"
    git checkout main
    git pull
    if [ ! -d "$STACK_PATH" ]; then
        echo "Stack doesn't exist! creating..."
        echo "Creating terraform stack..."
        echo "TERRAMATE_CLOUD_PATH: $TERRAMATE_CLOUD_PATH"
        terramate create stacks/accounts/aops_dev.487718497406/$FULL_HOSTNAME
        cp "$TERRAFORM_TEMPLATE_FILE" "$STACK_PATH/main.tf"
        sed -i '' "s/TERRAFORM_STACK_PREFIX_PLACEHOLDER/$PREFIX/g" "$STACK_PATH/main.tf"
        if [ -n "$(git status --porcelain)" ]; then
            git add .
            git commit -m "Create new test instance $FULL_HOSTNAME"
            echo "committing on branch: $(git branch --show-current)"
            git push origin main
        else
            echo "No changes to commit"
        fi
    else
        echo "Stack already exists! not creating..."
    fi
    # Ensure stack has a Terraform configuration if directory exists but is missing main.tf
    if [ ! -f "$STACK_PATH/main.tf" ]; then
        echo "main.tf missing for $FULL_HOSTNAME, populating from template..."
        cp "$TERRAFORM_TEMPLATE_FILE" "$STACK_PATH/main.tf"
        sed -i '' "s/TERRAFORM_STACK_PREFIX_PLACEHOLDER/$PREFIX/g" "$STACK_PATH/main.tf"
        # Only auto-commit if this script cloned the repo
        if [ "${CLEANUP_TERRAMATE:-0}" = "1" ]; then
            if [ -n "$(git status --porcelain "$STACK_PATH/main.tf")" ]; then
                git add "$STACK_PATH/main.tf"
                git commit -m "Populate main.tf for existing stack $FULL_HOSTNAME"
                git push origin main
            fi
        fi
    fi
    
    pushd "$STACK_PATH"
	echo "DEBUG: STACK_PATH=$STACK_PATH"
	ls -la
	terraform init
	if [ -n "${CI+x}" ]; then
		terraform apply -auto-approve
	else
		terraform apply
	fi
	popd
	popd
}

add_to_ansible_inventory() {
    echo "Adding host to ansible-cfg inventory..."
    pushd "$ANSIBLE_CONFIG_ROOT"
    git checkout "$ANSIBLE_CFG_BRANCH"
    git pull
    popd
    INVENTORY_FILE="$ANSIBLE_CONFIG_ROOT/inventory.yml"
    EMAILS_FILE="$ANSIBLE_CONFIG_ROOT/group_vars/all/emails.yml"
    # Ensure inventory file exists
    if [ ! -f "$INVENTORY_FILE" ]; then
        echo "ERROR: $INVENTORY_FILE does not exist!"
        exit 1
    fi
    if ! yq eval '.' "$INVENTORY_FILE" > /dev/null 2>&1; then
        echo "ERROR: $INVENTORY_FILE is not valid YAML. Aborting."; exit 1
    fi
    # Add host to inventory.yml using awk
    if ! grep -q "^        $FULL_HOSTNAME:" "$INVENTORY_FILE"; then
        # Insert new host line after "      hosts:" line using awk
        awk -v hostname="$FULL_HOSTNAME" '/^      hosts:/ { print; print "        " hostname ":"; next } { print }' "$INVENTORY_FILE" > temp_inventory.yml && mv temp_inventory.yml "$INVENTORY_FILE"
        echo "Added $FULL_HOSTNAME to inventory.yml"
    else
        echo "$FULL_HOSTNAME already present in inventory.yml"
    fi
    # Ensure emails file exists
    if [ ! -f "$EMAILS_FILE" ]; then
        echo "ERROR: $EMAILS_FILE does not exist!"
        exit 1
    fi
    if ! yq eval '.' "$EMAILS_FILE" > /dev/null 2>&1; then
        echo "ERROR: $EMAILS_FILE is not valid YAML. Aborting."; exit 1
    fi
    # Add host to emails.yml using yq
    if ! yq eval ".host_emails | has(\"$FULL_HOSTNAME\")" "$EMAILS_FILE" | grep -q true; then
        yq eval ".host_emails.\"$FULL_HOSTNAME\" = \"$EMAIL\"" -i "$EMAILS_FILE"
        echo "Added $FULL_HOSTNAME: $EMAIL to emails.yml"
    else
        echo "$FULL_HOSTNAME already present in emails.yml"
    fi
    pushd "$ANSIBLE_CONFIG_ROOT"
    # Validate YAML after modification before committing
    if ! yq eval '.' "$INVENTORY_FILE" > /dev/null 2>&1; then
        echo "ERROR: $INVENTORY_FILE is not valid YAML after modification. Aborting commit."; exit 1
    fi
    if ! yq eval '.' "$EMAILS_FILE" > /dev/null 2>&1; then
        echo "ERROR: $EMAILS_FILE is not valid YAML after modification. Aborting commit."; exit 1
    fi
    if [ -n "$(git status --porcelain)" ]; then
        git add "$INVENTORY_FILE" "$EMAILS_FILE"
        git commit -m "Add $FULL_HOSTNAME to inventory and emails.yml"
        git push origin "$ANSIBLE_CFG_BRANCH"
    fi
    popd
}

run_ansible() {
    echo "Waiting before running ansible..."
    sleep 60
    echo "Running ansible against the new host..."
    pushd "$ANSIBLE_CONFIG_ROOT"
    echo "Running initial_setup.yml with bootstrap key..."
    ansible-playbook initial_setup.yml \
        --private-key "$BOOTSTRAP_SSH_KEY" \
        --limit "$FULL_HOSTNAME" \
        --vault-password-file "$VAULT_PASSWORD_FILE" \
        --ssh-common-args="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
    echo "Running web_setup.yml with ansiblecontrol key..."
    ansible-playbook web_setup.yml \
        --private-key "$ANSIBLECONTROL_SSH_KEY" \
        --limit "$FULL_HOSTNAME" \
        --vault-password-file "$VAULT_PASSWORD_FILE" \
        --ssh-common-args="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
    popd
}

import_db() {
    echo "Importing database..."
    ssh-import-db.sh "$FULL_HOSTNAME"
}

prompt_to_continue() {
    if [ -n "${CI+x}" ]; then
        echo "CI: Continuing automatically..."
    else
        read -p "Press enter to continue..."
    fi
    echo
}

# =============================
# MAIN EXECUTION
# =============================

validate_and_check_environment

echo "========== [1/5] Cloning code and setting up... =========="
time { clone_code_and_setup; }
echo "Completed: Cloning code and setup!"
prompt_to_continue

echo "========== [2/5] Creating and applying terraform stack... =========="
time { create_and_apply_terraform_stack; }
echo "Completed: Terraform stack creation and apply!"
prompt_to_continue

echo "========== [3/5] Adding host to inventory and emails.yml... =========="
time { add_to_ansible_inventory; }
echo "Completed: Host added to inventory and emails.yml!"
prompt_to_continue

echo "========== [4/5] Running ansible against the new host... =========="
time { run_ansible; }
echo "Completed: Ansible run!"
prompt_to_continue

echo "========== [5/5] Importing database... =========="
time { import_db; }
echo "Completed: Database import!"
echo

echo "All steps completed successfully!"

play -q -n synth 0.1 sin 880
play -q -n synth 0.1 sin 990
play -q -n synth 0.1 sin 1100
