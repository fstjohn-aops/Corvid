#!/bin/bash

set -euox pipefail

ARN="${1:-arn:aws:imagebuilder:us-west-2:905418436535:image-pipeline/aops-baseline-al2023-x86}"

# trigger image pipeline execution
COMMAND="aws imagebuilder start-image-pipeline-execution --image-pipeline-arn $ARN --region us-west-2"
FORCE_NO_ALIAS=true assume Eng-Atlantis.AWSAdministratorAccess --exec -- $COMMAND | jq
