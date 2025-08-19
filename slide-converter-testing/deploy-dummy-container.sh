#!/bin/bash

# Exit on any error
set -e

# Configuration
PROJECT_NAME="${PROJECT_NAME:-torchboard}"
AWS_REGION="us-west-2"
echo "AWS_REGION: $AWS_REGION"
ECR_REPO_NAME="slide-converter"
IMAGE_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if Podman is installed and running
if ! command -v podman &> /dev/null; then
    print_error "Podman is not installed. Please install it first."
    exit 1
fi

if ! podman info &> /dev/null; then
    print_error "Podman is not running. Please start Podman first."
    exit 1
fi

print_status "Starting deployment process..."

# Get AWS account ID
print_status "Getting AWS account ID..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region $AWS_REGION)
if [ $? -ne 0 ]; then
    print_error "Failed to get AWS account ID. Please ensure AWS credentials are configured in your environment."
    exit 1
fi

print_status "AWS Account ID: $AWS_ACCOUNT_ID"

# Construct ECR repository URI
ECR_REPO_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME"

print_status "ECR Repository URI: $ECR_REPO_URI"

# Check if ECR repository exists
print_status "Checking if ECR repository exists..."
if ! aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION &> /dev/null; then
    print_warning "ECR repository '$ECR_REPO_NAME' does not exist in region $AWS_REGION."
    print_status "Available repositories in $AWS_REGION:"
    aws ecr describe-repositories --region $AWS_REGION --query 'repositories[].repositoryName' --output table 2>/dev/null || echo "Could not list repositories"
    print_error "Please run 'terraform apply' first to create the infrastructure, or check if you're using the correct region."
    exit 1
fi

# Get ECR login token
print_status "Getting ECR login token..."
aws ecr get-login-password --region $AWS_REGION | podman login --username AWS --password-stdin $ECR_REPO_URI

# Build the container image
print_status "Building container image for ARM64..."
podman build --platform linux/arm64 -t $ECR_REPO_NAME:$IMAGE_TAG .

# Tag the image for ECR
print_status "Tagging image for ECR..."
podman tag $ECR_REPO_NAME:$IMAGE_TAG $ECR_REPO_URI:$IMAGE_TAG

# Push the image to ECR
print_status "Pushing image to ECR..."
podman push $ECR_REPO_URI:$IMAGE_TAG

print_status "Deployment completed successfully!"
print_status "Image pushed to: $ECR_REPO_URI:$IMAGE_TAG"