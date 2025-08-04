#!/bin/bash

set -euo pipefail

# Default CI to false if not set
CI=${CI:-false}

# Vault password file configuration
VAULT_PASSWORD_FILE="${VAULT_PASSWORD_FILE:-$HOME/.aops_ansible_vault_pw}"
if [ ! -f "$VAULT_PASSWORD_FILE" ]; then
    echo "ERROR: Vault password file not found at $VAULT_PASSWORD_FILE. Set VAULT_PASSWORD_FILE or create the file."
    exit 1
fi

if [ $# -ne 1 ]; then
    echo "Usage: $0 <PREFIX>"
    exit 1
fi

PREFIX="$1"
FULL_HOSTNAME="$PREFIX.aopstest.com"

# Configuration. Override with environment variables.
TERRAMATE_CLOUD_PATH=${TERRAMATE_CLOUD_PATH:-}
ANSIBLE_CONFIG_ROOT=${ANSIBLE_CONFIG_ROOT:-}
TERRAMATE_CLOUD_REPO="git@github.com:aops-ba/terramate-cloud.git"
ANSIBLE_CONFIG_REPO="git@github.com:aops-ba/ansible-cfg.git"

# Trap for cleanup
trap "echo 'Cleaning up...'; rm -rf '$TERRAMATE_CLOUD_PATH' '$ANSIBLE_CONFIG_ROOT'" EXIT

if [ -z "$TERRAMATE_CLOUD_PATH" ]; then
    TERRAMATE_CLOUD_PATH=$(mktemp -d)
    echo "Cloning Terramate repo to $TERRAMATE_CLOUD_PATH"
    git clone "$TERRAMATE_CLOUD_REPO" "$TERRAMATE_CLOUD_PATH"
fi

if [ -z "$ANSIBLE_CONFIG_ROOT" ]; then
    ANSIBLE_CONFIG_ROOT=$(mktemp -d)
    echo "Cloning Ansible repo to $ANSIBLE_CONFIG_ROOT"
    git clone "$ANSIBLE_CONFIG_REPO" "$ANSIBLE_CONFIG_ROOT"
fi

# Derived variables
BASE_PATH="$TERRAMATE_CLOUD_PATH/stacks/accounts/aops_dev.487718497406"
STACK_PATH="$BASE_PATH/$FULL_HOSTNAME"

################################################################################
# FUNCTIONS
################################################################################

check_dependencies() {
    local dependencies=("git" "terraform")
    for cmd in "${dependencies[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            echo "$cmd could not be found, please install it."
            exit 1
        fi
    done
}

create_and_apply_terraform_stack() {

    pushd "$TERRAMATE_CLOUD_PATH"
    git checkout main
    git pull

    # check if stack doesn't exist
    if [ ! -d "$STACK_PATH" ]; then
        echo "Stack doesn't exist! creating..."
        echo "Creating terraform stack..."

        # create new terraform stack
        terramate create stacks/accounts/aops_dev.487718497406/$FULL_HOSTNAME

        cat << EOF > "$STACK_PATH/main.tf"
module "ec2_instance" {
  source = "../modules/test_environment"

  providers = {
    aws.target = aws.target
  }

  hostname_prefix = "$PREFIX"
}

output "instance_id" {
  description = "The ID of the created EC2 instance"
  value       = module.ec2_instance.instance_id
}

output "instance_public_ip" {
  description = "The public IP address of the created EC2 instance"
  value       = module.ec2_instance.instance_public_ip
}

output "ami_id" {
  description = "AMI ID of the EC2 instance"
  value       = module.ec2_instance.ami_id
}
EOF

        # commit the changes, only if there are untracked changes
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

    # pushd to stack path
    pushd "$STACK_PATH"

    # set cloudflare credentials
    if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
        echo "ERROR: CLOUDFLARE_API_TOKEN is not set in the environment."
        exit 1
    fi

    terraform init

    if [ "$CI" = "false" ]; then
    # apply uninteractively
    echo "Applying terraform stack..."
    if [ "$CI" = "true" ]; then
        terraform apply -auto-approve
    else
        terraform apply
        fi
    fi

    popd
}

get_instance_details() {
    echo "Getting instance ID and IP address..."
    # TODO: implement getting instance ID and IP address
    pushd "$STACK_PATH"
    INSTANCE_ID=$(terraform output -raw instance_id)
    INSTANCE_IP=$(terraform output -raw instance_public_ip)

    echo "Found values:"
    echo "Instance ID: $INSTANCE_ID"
    echo "Instance IP: $INSTANCE_IP"

    popd
}

add_to_ansible_inventory() {
    echo "Adding host to ansible-cfg inventory..."

    pushd "$ANSIBLE_CONFIG_ROOT"
    git checkout main
    git pull
    popd

    # add host in three places to file:
    INVENTORY_FILE="$ANSIBLE_CONFIG_ROOT/inventories/inventory_aops_web_setup_test.yml"
    
    # Add hostname to the top of aops_web_setup_test hosts section
    sed -i '' "/aops_web_setup_test:/,/hosts:/{
        /hosts:/a\\
                        $FULL_HOSTNAME:
        }" "$INVENTORY_FILE"
    
    # Add hostname to the top of alpha_aws_aops_dev hosts section  
    sed -i '' "/alpha_aws_aops_dev:/,/hosts:/{
        /hosts:/a\\
                $FULL_HOSTNAME:
        }" "$INVENTORY_FILE"
    
    # Add hostname to the top of classroom6_and_aops_combined_servers hosts section
    sed -i '' "/classroom6_and_aops_combined_servers:/,/hosts:/{
        /hosts:/a\\
                $FULL_HOSTNAME:
        }" "$INVENTORY_FILE"

    # create host_vars directory
    HOST_VARS_DIR="$ANSIBLE_CONFIG_ROOT/host_vars/$FULL_HOSTNAME"
    mkdir -p "$HOST_VARS_DIR"

    # create aws_deployment_vars.yml file
    echo "---" > "$HOST_VARS_DIR/aws_deployment_vars.yml"
    echo "ec2_isntance_elastic_ip: \"$INSTANCE_IP\"" >> "$HOST_VARS_DIR/aws_deployment_vars.yml"
    echo "ansible_host: \"$INSTANCE_IP\"" >> "$HOST_VARS_DIR/aws_deployment_vars.yml"
    echo "aws_ec_instance_id: \"$INSTANCE_ID\""  >> "$HOST_VARS_DIR/aws_deployment_vars.yml"
    echo "ansible_user_initial_run: ec2-user" >> "$HOST_VARS_DIR/aws_deployment_vars.yml"

    # get email input from user
    if [ "$CI" = "true" ]; then
        EMAIL="devops@artofproblemsolving.com"
    else
        read -p "Enter instance email: " EMAIL
    fi

    # create vars.yml file
    echo "---" > "$HOST_VARS_DIR/vars.yml"
    echo "academy_domain: $PREFIX.aopsacademy.club" >> "$HOST_VARS_DIR/vars.yml"
    echo "academy_debug_emails:" >> "$HOST_VARS_DIR/vars.yml"
    echo "    - $EMAIL" >> "$HOST_VARS_DIR/vars.yml"
    echo "aops_debug_emails:" >> "$HOST_VARS_DIR/vars.yml"
    echo "    - $EMAIL" >> "$HOST_VARS_DIR/vars.yml"

    # remove programmatically_created_vars.yml file if it exists
    if [ -f "$HOST_VARS_DIR/programmatically_created_vars.yml" ]; then
        rm "$HOST_VARS_DIR/programmatically_created_vars.yml"
    fi

    # commit and push
    pushd "$ANSIBLE_CONFIG_ROOT"
    if [ -n "$(git status --porcelain)" ]; then
        git add .
        git commit -m "Add host $FULL_HOSTNAME to inventory"
        git push origin main
    fi
    popd
}

run_ansible() {
    echo "Running ansible against the new host..."
    pushd "$ANSIBLE_CONFIG_ROOT"
    ansible-playbook aops_web_setup.yml -vv \
      --limit $FULL_HOSTNAME \
      --vault-password-file "$VAULT_PASSWORD_FILE"
    popd
}

import_db() {
    echo "Adding host to teleport and importing database..."
    ssh-import-db.sh "$FULL_HOSTNAME"
}

################################################################################
# MAIN EXECUTION
################################################################################

check_dependencies

echo "🚀 Creating and applying terraform stack..."
time { create_and_apply_terraform_stack; }
echo "✅ Terraform stack created and applied successfully!"
echo

echo "Stopping after terraform stack creation..."
exit 0

if [ "$CI" = "true" ]; then
    echo "CI: Continuing automatically..."
else
    read -p "Press enter to continue to the next step (get_instance_details)..."
fi
echo

echo "🔍 Getting instance details..."
time { get_instance_details; }
echo "✅ Instance details retrieved successfully!"
echo

if [ "$CI" = "true" ]; then
    echo "CI: Continuing automatically..."
else
    read -p "Press enter to continue to the next step (add_to_ansible_inventory)..."
fi
echo

echo "🔍 Adding host to ansible inventory..."
time { add_to_ansible_inventory; }
echo "✅ Host added to ansible inventory successfully!"
echo

if [ "$CI" = "true" ]; then
    echo "CI: Continuing automatically..."
else
    read -p "Press enter to continue to the next step (run_ansible)..."
fi
echo

echo "🔍 Running ansible against the new host..."
time { run_ansible; }
echo "✅ Ansible run completed successfully!"
echo

if [ "$CI" = "true" ]; then
    echo "CI: Continuing automatically..."
else
    read -p "Press enter to continue to the next step (import_db)..."
fi
echo

echo "🔍 Adding host to teleport and importing database..."
time { import_db; }
echo "✅ Host added to teleport and database imported successfully!"
echo
echo "🎉 All steps completed successfully!"

play -q -n synth 0.1 sin 880
play -q -n synth 0.1 sin 990
play -q -n synth 0.1 sin 1100
