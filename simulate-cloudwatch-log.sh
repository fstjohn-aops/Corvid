#!/bin/bash

# Hardcoded values
# CloudWatch log group to write to
LOG_GROUP="/torchboard/node"
# Stream within the log group (creates new if doesn't exist)
LOG_STREAM="test-stream"
# AWS role to assume
ROLE_NAME="VCVC-Dev.AWSAdministratorAccess"
# "0" for new streams, actual token for existing streams
SEQUENCE_TOKEN="0"

# Create a simple log event
# The actual log message
LOG_EVENT="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ) - Simulated log event from test script"
# JSON array with timestamp (ms) and message
LOG_EVENTS_JSON="[{\"timestamp\": $(date +%s)000, \"message\": \"$LOG_EVENT\"}]"

# Send the log event to CloudWatch using assume with --exec
echo "Sending log event to: $LOG_GROUP"
assume "$ROLE_NAME" --exec -- aws logs put-log-events \
    --log-group-name "$LOG_GROUP" \
    --log-stream-name "$LOG_STREAM" \
    --log-events "$LOG_EVENTS_JSON" \
    --sequence-token "$SEQUENCE_TOKEN"

echo "Log event sent successfully"
