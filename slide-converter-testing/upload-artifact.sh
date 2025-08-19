#!/bin/bash

echo "Creating dummy artifact with environment variables and SQS data..."

echo "=== DUMMY ARTIFACT CREATED AT $(date) ===" > /tmp/dummy-artifact.txt
echo "" >> /tmp/dummy-artifact.txt

echo "=== ALL ENVIRONMENT VARIABLES ===" >> /tmp/dummy-artifact.txt
env | sort >> /tmp/dummy-artifact.txt
echo "" >> /tmp/dummy-artifact.txt

echo "=== CONTAINER INFO ===" >> /tmp/dummy-artifact.txt
echo "Hostname: $(hostname)" >> /tmp/dummy-artifact.txt
echo "Current directory: $(pwd)" >> /tmp/dummy-artifact.txt
echo "User: $(whoami)" >> /tmp/dummy-artifact.txt
echo "" >> /tmp/dummy-artifact.txt

echo "=== SQS QUEUE DATA ===" >> /tmp/dummy-artifact.txt

# Get queue attributes to show message counts
echo "Getting queue attributes..." >> /tmp/dummy-artifact.txt
QUEUE_ATTRIBUTES=$(aws sqs get-queue-attributes --queue-url ${SQS_QUEUE_URL} --attribute-names All --output json 2>/dev/null || echo "{}")
VISIBLE_MESSAGES=$(echo "$QUEUE_ATTRIBUTES" | jq -r '.Attributes.ApproximateNumberOfMessages // "0"')
NOT_VISIBLE_MESSAGES=$(echo "$QUEUE_ATTRIBUTES" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible // "0"')
DELAYED_MESSAGES=$(echo "$QUEUE_ATTRIBUTES" | jq -r '.Attributes.ApproximateNumberOfMessagesDelayed // "0"')

echo "Queue Statistics:" >> /tmp/dummy-artifact.txt
echo "  Visible messages: $VISIBLE_MESSAGES" >> /tmp/dummy-artifact.txt
echo "  Messages in flight: $NOT_VISIBLE_MESSAGES" >> /tmp/dummy-artifact.txt
echo "  Delayed messages: $DELAYED_MESSAGES" >> /tmp/dummy-artifact.txt
echo "" >> /tmp/dummy-artifact.txt

echo "Attempting to receive message from SQS queue..." >> /tmp/dummy-artifact.txt

SQS_MESSAGE=$(aws sqs receive-message --queue-url ${SQS_QUEUE_URL} --max-number-of-messages 1 --wait-time-seconds 5 --query "Messages[0]" --output json 2>/dev/null || echo "null")

if [ "$SQS_MESSAGE" != "null" ]; then
  echo "Received SQS message:" >> /tmp/dummy-artifact.txt
  echo "$SQS_MESSAGE" | jq '.' >> /tmp/dummy-artifact.txt
  
  MESSAGE_ID=$(echo "$SQS_MESSAGE" | jq -r ".MessageId")
  RECEIPT_HANDLE=$(echo "$SQS_MESSAGE" | jq -r ".ReceiptHandle")
  BODY=$(echo "$SQS_MESSAGE" | jq -r ".Body")
  
  echo "Message ID: $MESSAGE_ID" >> /tmp/dummy-artifact.txt
  echo "Receipt Handle: $RECEIPT_HANDLE" >> /tmp/dummy-artifact.txt
  echo "Message Body: $BODY" >> /tmp/dummy-artifact.txt
  
  # Check if this message should fail (random_number = 3)
  RANDOM_NUMBER=$(echo "$BODY" | jq -r '.data.random_number // 0')
  echo "Random number from message: $RANDOM_NUMBER" >> /tmp/dummy-artifact.txt
  
  # Set filename suffix based on whether this will fail
  if [ "$RANDOM_NUMBER" = "3" ]; then
    echo "SIMULATING FAILURE: Random number is 3, this message will fail processing" >> /tmp/dummy-artifact.txt
    echo "Message will become visible again after visibility timeout and eventually go to DLQ" >> /tmp/dummy-artifact.txt
  else
    echo "Processing message successfully..." >> /tmp/dummy-artifact.txt
    echo "Deleting message from queue..." >> /tmp/dummy-artifact.txt
    aws sqs delete-message --queue-url ${SQS_QUEUE_URL} --receipt-handle "$RECEIPT_HANDLE" >> /tmp/dummy-artifact.txt 2>&1
  fi
else
  echo "No messages available in SQS queue" >> /tmp/dummy-artifact.txt
fi

echo "" >> /tmp/dummy-artifact.txt
echo "Uploading dummy artifact to S3..."

# Determine filename based on whether we processed a message that will fail
if [ "$SQS_MESSAGE" != "null" ] && [ "$RANDOM_NUMBER" = "3" ]; then
  FILENAME="dummy-artifact-$(date +%Y%m%d-%H%M%S)-dlq.txt"
else
  FILENAME="dummy-artifact-$(date +%Y%m%d-%H%M%S).txt"
fi

aws s3 cp /tmp/dummy-artifact.txt s3://${S3_BUCKET_NAME}/dummy-artifacts/$FILENAME

echo "Upload complete!"

# Exit with error if this was a failure simulation
if [ "$SQS_MESSAGE" != "null" ] && [ "$RANDOM_NUMBER" = "3" ]; then
  echo "Exiting with error code 1 to simulate processing failure..."
  exit 1
fi 