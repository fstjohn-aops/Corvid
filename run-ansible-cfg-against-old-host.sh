#!/bin/bash

# define parameters
TARGET_HOSTNAME=devops1.aopstest.com
ANSIBLE_DIR=/Users/finnstjohn/Source/Dev-Environment-Ansible-Cfg

# pushd to ansible
pushd $ANSIBLE_DIR

# build container for CentOS 8
podman build -t ansible:2.11 - < Dockerfile

# run ansible against host
podman run --rm \
  -v $(pwd):/ansible \
  -v ./.aops_ansible_vault_pw:/root/.aops_ansible_vault_pw \
  ansible:2.11 \
  ansible-playbook --limit $TARGET_HOSTNAME aops_web_setup.yml

# popd
popd
