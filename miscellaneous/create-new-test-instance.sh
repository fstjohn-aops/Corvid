#!/bin/bash

set -euo pipefail

# =============================
# COLOR CODES
# =============================

BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
BOOTSTRAP_SSH_KEY="${BOOTSTRAP_SSH_KEY:-$HOME/.ssh/id_rsa}"
ANSIBLECONTROL_SSH_KEY="${ANSIBLECONTROL_SSH_KEY:-$HOME/.ssh/id_ansiblecontrol}"
CI="${CI:-false}"
TERRAFORM_TEMPLATE_FILE="$(dirname "$0")/test_instance.tf.template"
EMAIL="${EMAIL:-devops@artofproblemsolving.com}"
DEBUG="${DEBUG:-false}"

# =============================
# FUNCTION DEFINITIONS
# =============================

validate_and_check_environment() {
    # Check required commands
    local dependencies=("git" "terraform" "aws" "ssh-import-db.sh" "yq")
    for cmd in "${dependencies[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            echo "$cmd could not be found, please install it."
            exit 1
        fi
    done

    # Validate PREFIX
    if ! [[ "$PREFIX" =~ ^[a-zA-Z0-9]+$ ]]; then
        echo "ERROR: PREFIX must be alphanumeric (letters and numbers only)."
        exit 1
    fi

    # Expand ~ to $HOME in SSH keys
    if [[ "$BOOTSTRAP_SSH_KEY" == ~* ]]; then
        BOOTSTRAP_SSH_KEY="$HOME${BOOTSTRAP_SSH_KEY:1}"
    fi
    if [[ "$ANSIBLECONTROL_SSH_KEY" == ~* ]]; then
        ANSIBLECONTROL_SSH_KEY="$HOME${ANSIBLECONTROL_SSH_KEY:1}"
    fi
    
    # Ensure SSH keys are absolute paths
    if [ "${BOOTSTRAP_SSH_KEY:0:1}" != "/" ]; then
        BOOTSTRAP_SSH_KEY="$HOME/$BOOTSTRAP_SSH_KEY"
    fi
    if [ "${ANSIBLECONTROL_SSH_KEY:0:1}" != "/" ]; then
        ANSIBLECONTROL_SSH_KEY="$HOME/$ANSIBLECONTROL_SSH_KEY"
    fi

    # Expand ~ to $HOME in VAULT_PASSWORD_FILE
    if [[ "$VAULT_PASSWORD_FILE" == ~* ]]; then
        VAULT_PASSWORD_FILE="$HOME${VAULT_PASSWORD_FILE:1}"
    fi
    # Ensure VAULT_PASSWORD_FILE is absolute
    if [ "${VAULT_PASSWORD_FILE:0:1}" != "/" ]; then
        VAULT_PASSWORD_FILE="$HOME/$VAULT_PASSWORD_FILE"
    fi

    # Check vault password file
    if [ ! -f "$VAULT_PASSWORD_FILE" ]; then
        echo "ERROR: Vault password file not found at $VAULT_PASSWORD_FILE. Set VAULT_PASSWORD_FILE or create the file."
        exit 1
    fi

    # Check SSH keys exist
    if [ ! -f "$BOOTSTRAP_SSH_KEY" ]; then
        echo "ERROR: Bootstrap SSH key not found at $BOOTSTRAP_SSH_KEY"
        exit 1
    fi
    if [ ! -f "$ANSIBLECONTROL_SSH_KEY" ]; then
        echo "ERROR: Ansible control SSH key not found at $ANSIBLECONTROL_SSH_KEY"
        exit 1
    fi

    # Check Terraform template file
    if [ ! -f "$TERRAFORM_TEMPLATE_FILE" ]; then
        echo "ERROR: Terraform template file not found at $TERRAFORM_TEMPLATE_FILE."
        exit 1
    fi

    # Check CLOUDFLARE_API_TOKEN
    if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
        echo "ERROR: CLOUDFLARE_API_TOKEN is not set in the environment."
        exit 1
    fi

    # Check AWS authentication (env vars or profile)
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
    fi
    if [ -z "$ANSIBLE_CONFIG_ROOT" ]; then
        ANSIBLE_CONFIG_ROOT=$(mktemp -d)
        echo "Cloning Ansible repo to $ANSIBLE_CONFIG_ROOT"
        git clone "$ANSIBLE_CONFIG_REPO" "$ANSIBLE_CONFIG_ROOT"
        pushd "$ANSIBLE_CONFIG_ROOT"
        git checkout "$ANSIBLE_CFG_BRANCH"
        popd
    fi
    BASE_PATH="$TERRAMATE_CLOUD_PATH/stacks/accounts/aops_dev.487718497406"
    STACK_PATH="$BASE_PATH/$FULL_HOSTNAME"
    trap "echo 'Cleaning up...'; rm -rf '$TERRAMATE_CLOUD_PATH' '$ANSIBLE_CONFIG_ROOT'" EXIT
}

create_and_apply_terraform_stack() {
    pushd "$TERRAMATE_CLOUD_PATH"
    git checkout main
    git pull
    if [ ! -d "$STACK_PATH" ]; then
        echo "Stack doesn't exist! creating..."
        echo "Creating terraform stack..."
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
    pushd "$STACK_PATH"
    terraform init
    if [ "$CI" = "false" ]; then
        echo "Applying terraform stack..."
        if [ "$CI" = "true" ]; then
            terraform apply -auto-approve
        else
            terraform apply
        fi
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
    # Add host to inventory.yml using yq
    if ! yq eval ".all.hosts | has(\"$FULL_HOSTNAME\")" "$INVENTORY_FILE" | grep -q true; then
        yq eval ".all.hosts.\"$FULL_HOSTNAME\" = {}" -i "$INVENTORY_FILE"
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
    echo "Running ansible against the new host..."
    pushd "$ANSIBLE_CONFIG_ROOT"
    echo "Running initial_setup.yml with bootstrap key..."
    ansible-playbook initial_setup.yml --private-key "$BOOTSTRAP_SSH_KEY" --limit "$FULL_HOSTNAME" --vault-password-file "$VAULT_PASSWORD_FILE" --ssh-common-args="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
    echo "Running web_setup.yml with ansiblecontrol key..."
    ansible-playbook web_setup.yml --private-key "$ANSIBLECONTROL_SSH_KEY" --limit "$FULL_HOSTNAME" --vault-password-file "$VAULT_PASSWORD_FILE" --ssh-common-args="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
    popd
}

import_db() {
    echo "Importing database..."
    ssh-import-db.sh "$FULL_HOSTNAME"
}

prompt_to_continue() {
    if [ "$CI" = "true" ]; then
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

echo -e "${BLUE}========== [1/5] Cloning code and setting up... ==========${NC}"
time { clone_code_and_setup; }
echo "Completed: Cloning code and setup!"
prompt_to_continue

echo -e "${BLUE}========== [2/5] Creating and applying terraform stack... ==========${NC}"
time { create_and_apply_terraform_stack; }
echo "Completed: Terraform stack creation and apply!"
prompt_to_continue

echo -e "${BLUE}========== [3/5] Adding host to inventory and emails.yml... ==========${NC}"
time { add_to_ansible_inventory; }
echo "Completed: Host added to inventory and emails.yml!"
prompt_to_continue

echo -e "${BLUE}========== [4/5] Running ansible against the new host... ==========${NC}"
time { run_ansible; }
echo "Completed: Ansible run!"
prompt_to_continue

echo -e "${BLUE}========== [5/5] Importing database... ==========${NC}"
# time { import_db; }
echo "Completed: Database import!"
echo

echo "All steps completed successfully!"

play -q -n synth 0.1 sin 880
play -q -n synth 0.1 sin 990
play -q -n synth 0.1 sin 1100
