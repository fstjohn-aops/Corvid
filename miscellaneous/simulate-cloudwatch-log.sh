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
# AWS region
REGION="us-west-2"
# Set to "true" to bootstrap (create stream and first event), "false" to just add events
BOOTSTRAP="true"

# Create a simple log event
# The actual log message as JSON (properly escaped)
LOG_EVENT='{"timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'", "level": "INFO", "message": "Simulated log event from test script", "service": "/torchboard/node"}'
# JSON array with timestamp (ms) and message (properly escaped)
LOG_EVENTS_JSON=$(jq -n --arg timestamp "$(date +%s)000" --arg message "$LOG_EVENT" '[{"timestamp": ($timestamp | tonumber), "message": $message}]')

# Bootstrap function to create stream and first event
if [ "$BOOTSTRAP" = "true" ]; then
    echo "Bootstrapping: Creating log stream and first event..."
    
    # Create the log stream
    FORCE_NO_ALIAS=true assume "$ROLE_NAME" --exec -- aws logs create-log-stream \
        --region $REGION \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LOG_STREAM"
    
    # Send the first log event with sequence token "0"
    FORCE_NO_ALIAS=true assume "$ROLE_NAME" --exec -- aws logs put-log-events \
        --region $REGION \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LOG_STREAM" \
        --log-events "$LOG_EVENTS_JSON" \
        --sequence-token "0"
    
    echo "Bootstrap complete!"
else
    # Send additional log events (no sequence token needed)
    echo "Sending log event to: $LOG_GROUP"
    FORCE_NO_ALIAS=true assume "$ROLE_NAME" --exec -- aws logs put-log-events \
        --region $REGION \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LOG_STREAM" \
        --log-events "$LOG_EVENTS_JSON"
fi

echo "Log event sent successfully"
