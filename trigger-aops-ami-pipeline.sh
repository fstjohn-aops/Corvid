#!/bin/bash

set -euox pipefail

ARN=arn:aws:imagebuilder:us-west-2:905418436535:image-pipeline/aops-baseline-al2023-x86

# trigger image pipeline execution
COMMAND="aws imagebuilder start-image-pipeline-execution --image-pipeline-arn $ARN --region us-west-2"
FORCE_NO_ALIAS=true assume Eng-Atlantis.AWSAdministratorAccess --exec -- $COMMAND | jq

# list most recent image version
COMMAND="aws imagebuilder list-image-pipeline-images --image-pipeline-arn $ARN --region us-west-2"
FORCE_NO_ALIAS=true assume Eng-Atlantis.AWSAdministratorAccess --exec -- $COMMAND | jq -r '.imageSummaryList | sort_by(.dateCreated) | reverse | .[0].arn | split("/") | .[-2:] | join("/")'
