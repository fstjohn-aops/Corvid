#!/bin/bash

# Check EC2 instance power state using AWS CLI with assume role
# Usage: ./check-ec2-power-state.sh <instance-id>

if [ $# -ne 1 ]; then
    echo "Usage: $0 <instance-id>"
    exit 1
fi

INSTANCE_ID=$1
ROLE="AoPS-Dev.AWSAdministratorAccess"

# Use assume to set up the environment and run the command
# eval $(FORCE_NO_ALIAS=true assume $ROLE --export)
# RESULT=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region us-west-2 --query 'Reservations[0].Instances[0].State.Name' --output text 2>&1)
# assume --unset

COMMAND="aws ec2 describe-instances --instance-ids $INSTANCE_ID --region us-west-2 --query Reservations[0].Instances[0].State.Name --output text"
RESULT=$(FORCE_NO_ALIAS=true assume $ROLE --exec -- $COMMAND 2>&1 | tail -n 1)

# Check if the command failed
if [ $? -ne 0 ]; then
    echo "Error executing command: $RESULT"
    exit 1
fi

echo "instance power state: $RESULT"