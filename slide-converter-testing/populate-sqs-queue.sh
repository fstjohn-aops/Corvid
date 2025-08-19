#!/bin/bash

# Exit on any error
set -e

# Check if argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <number_of_messages>"
    echo "Example: $0 5"
    exit 1
fi

# Get the number of messages from argument
NUM_MESSAGES=$1

# Validate that it's a number
if ! [[ "$NUM_MESSAGES" =~ ^[0-9]+$ ]]; then
    echo "Error: Number of messages must be a positive integer"
    exit 1
fi

# Configuration
AWS_REGION="us-west-2"
QUEUE_NAME="slide-converter-queue"

echo "Populating SQS queue with $NUM_MESSAGES test messages..."

# Get the queue URL
QUEUE_URL=$(aws sqs get-queue-url --queue-name $QUEUE_NAME --region $AWS_REGION --query 'QueueUrl' --output text)

if [ $? -ne 0 ]; then
    echo "Error: Could not find SQS queue '$QUEUE_NAME'. Please ensure the queue exists."
    exit 1
fi

echo "Queue URL: $QUEUE_URL"

# Send messages
for i in $(seq 1 $NUM_MESSAGES); do
    MESSAGE_BODY=$(cat <<EOF
{
    "message_id": "test-message-$i",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "data": {
        "test_field": "test_value_$i",
        "random_number": $((RANDOM % 5 + 1)),
        "iteration": $i
    },
    "metadata": {
        "source": "test-script",
        "environment": "staging"
    }
}
EOF
)
    
    echo "Sending message $i/$NUM_MESSAGES..."
    aws sqs send-message \
        --queue-url "$QUEUE_URL" \
        --message-body "$MESSAGE_BODY" \
        --region $AWS_REGION \
        --message-attributes '{"MessageType":{"StringValue":"test","DataType":"String"}}' > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✓ Message $i sent successfully"
    else
        echo "✗ Failed to send message $i"
    fi
done

echo ""
echo "Successfully sent $NUM_MESSAGES messages to SQS queue: $QUEUE_NAME"

# Show queue attributes
echo ""
echo "Queue attributes:"
aws sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names All \
    --region $AWS_REGION \
    --query 'Attributes.{ApproximateNumberOfMessages:ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible:ApproximateNumberOfMessagesNotVisible,ApproximateNumberOfMessagesDelayed:ApproximateNumberOfMessagesDelayed}' \
    --output table 