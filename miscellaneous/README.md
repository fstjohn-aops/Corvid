# Miscellaneous Scripts and Tools

This directory contains various utility scripts and tools for AWS management, Teleport configuration, and system administration.

## AWS Management

### Instance Management
- **`create-new-test-instance.py`** - Create and configure new test EC2 instances with Terraform and Ansible
- **`create-new-test-instance.sh`** - Shell script wrapper for creating test instances
- **`destroy-test-instance.py`** - Python script to destroy test instances
- **`destroy-test-instance.sh`** - Shell script to destroy test instances
- **`find-ec2-instance.sh`** - Find EC2 instances by ID and check their status
- **`check-ec2-power-state.sh`** - Check the power state of a specific EC2 instance

### Infrastructure Discovery
- **`find-nat-gateways.py`** - Find NAT gateways across all AWS profiles and regions
- **`replace-a-record-in-tf-state.sh`** - Replace A records in Terraform state files

### Tagging and Configuration
- **`add-tags-wizard.py`** - Interactive wizard for adding tags to EC2 instances
- **`apply-tags-to-instances.sh`** - Apply tags to multiple EC2 instances
- **`enable-tags-imds.py`** - Enable IMDSv2 and configure instance metadata tags

## Teleport Management

### User Configuration
- **`add-default-user-to-teleport-nodes.sh`** - Add default users to Teleport nodes and configure commands
- **`show-default-teleport-users.sh`** - Display default Teleport users
- **`check-secrets-on-all-teleport-nodes.sh`** - Check for secrets across all Teleport nodes

### Node Management
- **`reload-teleport-on-hosts.py`** - Reload Teleport service on multiple hosts
- **`ssh-import-db.sh`** - Import SSH keys to Teleport database

## Security and Cleanup

### History and Secrets
- **`remove-secrets-from-history.sh`** - Clean sensitive variables from shell history files
- **`remove-host-from-known-hosts.sh`** - Remove hosts from SSH known_hosts file

### Access Control
- **`run-ansible-cfg-against-old-host.sh`** - Run Ansible configuration against old hosts

## Testing and Development

### Instance Templates
- **`test_instance.tf.template`** - Terraform template for test instances

### Pipeline and Monitoring
- **`trigger-aops-ami-pipeline.sh`** - Trigger AMI pipeline for AoPS
- **`simulate-cloudwatch-log.sh`** - Simulate CloudWatch log entries for testing

### Inventory Management
- **`test-inventory-add.sh`** - Add hosts to Ansible inventory for testing

## Usage

Most scripts include help text or usage instructions. For Python scripts, ensure you have the required dependencies installed (usually via `uv run`).

### Common Patterns
- Python scripts use `uv run` for dependency management
- Shell scripts often require AWS credentials via `assume` command
- Many scripts support `--help` or `-h` flags for usage information

### Search Tips
Use Ctrl+F to search for:
- **Keywords**: "teleport", "aws", "ec2", "terraform", "ansible"
- **File types**: ".py", ".sh", ".tf"
- **Actions**: "create", "destroy", "check", "find", "add"
