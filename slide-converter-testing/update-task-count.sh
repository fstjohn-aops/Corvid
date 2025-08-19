#!/bin/bash

# Exit on any error
set -e

# Check if argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <task_count>"
    echo "Example: $0 3"
    exit 1
fi

# Get the task count from argument
TASK_COUNT=$1

# Validate that it's a number
if ! [[ "$TASK_COUNT" =~ ^[0-9]+$ ]]; then
    echo "Error: Task count must be a positive integer"
    exit 1
fi

# Configuration
AWS_REGION="us-west-2"
PROJECT_NAME="${PROJECT_NAME:-torchboard}"
RULE_NAME="${PROJECT_NAME}-slide-converter-schedule"

echo "Updating EventBridge target task count to $TASK_COUNT for rule: $RULE_NAME"

# Get the current target configuration
CURRENT_TARGET=$(aws events list-targets-by-rule --rule $RULE_NAME --region $AWS_REGION --query 'Targets[0]' --output json)

if [ "$CURRENT_TARGET" = "null" ]; then
    echo "Error: No targets found for EventBridge rule '$RULE_NAME'"
    exit 1
fi

# Update the target with new task count
aws events put-targets \
    --rule $RULE_NAME \
    --targets "[{\"Id\":\"SlideConverterTarget\",\"Arn\":\"$(echo $CURRENT_TARGET | jq -r '.Arn')\",\"RoleArn\":\"$(echo $CURRENT_TARGET | jq -r '.RoleArn')\",\"EcsParameters\":{\"TaskDefinitionArn\":\"$(echo $CURRENT_TARGET | jq -r '.EcsParameters.TaskDefinitionArn')\",\"TaskCount\":$TASK_COUNT,\"LaunchType\":\"FARGATE\",\"PlatformVersion\":\"LATEST\",\"NetworkConfiguration\":$(echo $CURRENT_TARGET | jq -r '.EcsParameters.NetworkConfiguration')}}]" \
    --region $AWS_REGION

echo "Successfully updated task count to $TASK_COUNT" 