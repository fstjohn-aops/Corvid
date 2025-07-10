#!/bin/bash

# Check if instance ID or IP is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <instance-id-or-public-ip>"
    exit 1
fi

SEARCH_TERM=$1

# Predefined roles and regions
ROLES=(
    "Academy-Dev.AWSAdministratorAccess"
    "Academy-Prod.AWSAdministratorAccess"
    "Academy-Staging.AWSAdministratorAccess"
    "AoPS-Dev.AWSAdministratorAccess"
    "AoPS-Hackathon.AWSAdministratorAccess"
    "AoPS-Prod.AWSAdministratorAccess"
    "AoPS-Root.AWSAdministratorAccess"
    "Asymphost-Prod.AWSAdministratorAccess"
    "Audit.AWSAdministratorAccess"
    "B2B-Transfer-Prod.AWSAdministratorAccess"
    "BAClassroom-Dev.AWSAdministratorAccess"
    "BAClassroom-Prod.AWSAdministratorAccess"
    "BAClassroom-Staging.AWSAdministratorAccess"
    "BACurriculum-Dev.AWSAdministratorAccess"
    "BACurriculum-Prod.AWSAdministratorAccess"
    "BACurriculum-Staging.AWSAdministratorAccess"
    "Classroom-Prod.AWSAdministratorAccess"
    "CodeWoot-Dev.AWSAdministratorAccess"
    "CodeWoot-Prod.AWSAdministratorAccess"
    "CryptGrid-Dev.AWSAdministratorAccess"
    "CryptGrid-Prod.AWSAdministratorAccess"
    "CS-Dev.AWSAdministratorAccess"
    "CS-Development.AWSAdministratorAccess"
    "CS-Prod.AWSAdministratorAccess"
    "CS-Staging.AWSAdministratorAccess"
    "CSCurriculum-Dev.AWSAdministratorAccess"
    "Data.AWSAdministratorAccess"
    "Encounter-Dev.AWSAdministratorAccess"
    "Encounter-Prod.AWSAdministratorAccess"
    "Eng-Atlantis.AWSAdministratorAccess"
    "Eng-Experiments.AWSAdministratorAccess"
    "Eng-Trove.AWSAdministratorAccess"
    "Grader-Dev.AWSAdministratorAccess"
    "Grader-Prod.AWSAdministratorAccess"
    "Log-Archive.AWSAdministratorAccess"
    "ML-Dev.AWSAdministratorAccess"
    "ML-Staging.AWSAdministratorAccess"
    "Monitoring.AWSAdministratorAccess"
    "Network.AWSAdministratorAccess"
    "PartnerApi-Dev.AWSAdministratorAccess"
    "PartnerApi-Prod.AWSAdministratorAccess"
    "PartnerApi-Staging.AWSAdministratorAccess"
    "Platform-Dev.AWSAdministratorAccess"
    "Platform-Prod.AWSAdministratorAccess"
    "Platform-Staging.AWSAdministratorAccess"
    "Python-Analytics.AWSAdministratorAccess"
    "Services-Dev.AWSAdministratorAccess"
    "Services-Prod.AWSAdministratorAccess"
    "Services-Staging.AWSAdministratorAccess"
    "SRE-Interview.AWSAdministratorAccess"
    "Strapi-Dev.AWSAdministratorAccess"
    "Strapi-Prod.AWSAdministratorAccess"
    "Strapi-Staging.AWSAdministratorAccess"
    "Thrid-Prod.AWSAdministratorAccess"
    "Thrid-Staging.AWSAdministratorAccess"
    "Timesheets-Dev.AWSAdministratorAccess"
    "Timesheets-Prod.AWSAdministratorAccess"
    "Torchboard-Prod.AWSAdministratorAccess"
    "VCVC-Dev.AWSAdministratorAccess"
)
REGIONS=("us-west-1" "us-west-2")

# Function to check if instance exists in a role/region
check_instance() {
    local role=$1
    local region=$2
    local search_term=$3
    
    # Check if it's an IP address
    if [[ $search_term =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        # Try public IP
        result=$(FORCE_NO_ALIAS=true assume $role --exec -- aws ec2 describe-instances --filters "Name=ip-address,Values=$search_term" --region $region 2>&1 | grep -v "\[.*\]" | grep -v "Please select" | grep -v "Use arrows" | grep -v "interrupt" | grep -v "> " | grep -v "^[[:space:]]*[A-Za-z]" 2>/dev/null)
        if [ $? -eq 0 ] && [[ "$result" =~ ^[{\[] ]] && [ "$(echo "$result" | jq -r '.Reservations | length // 0')" -gt 0 ]; then
            echo "FOUND (Public IP)"
            return 0
        fi
        
        # Try private IP
        result=$(FORCE_NO_ALIAS=true assume $role --exec -- aws ec2 describe-instances --filters "Name=private-ip-address,Values=$search_term" --region $region 2>&1 | grep -v "\[.*\]" | grep -v "Please select" | grep -v "Use arrows" | grep -v "interrupt" | grep -v "> " | grep -v "^[[:space:]]*[A-Za-z]" 2>/dev/null)
        if [ $? -eq 0 ] && [[ "$result" =~ ^[{\[] ]] && [ "$(echo "$result" | jq -r '.Reservations | length // 0')" -gt 0 ]; then
            echo "FOUND (Private IP)"
            return 0
        fi
    else
        # Search by instance ID
        result=$(FORCE_NO_ALIAS=true assume $role --exec -- aws ec2 describe-instances --instance-ids $search_term --region $region 2>&1 | grep -v "\[.*\]" | grep -v "Please select" | grep -v "Use arrows" | grep -v "interrupt" | grep -v "> " | grep -v "^[[:space:]]*[A-Za-z]" 2>/dev/null)
        if [ $? -eq 0 ] && [[ "$result" =~ ^[{\[] ]] && [ "$(echo "$result" | jq -r '.Reservations | length // 0')" -gt 0 ]; then
            echo "FOUND"
            return 0
        fi
    fi
    
    return 1
}

# Main search loop
total_checks=$((${#ROLES[@]} * ${#REGIONS[@]}))
current_check=0

for role in "${ROLES[@]}"; do
    for region in "${REGIONS[@]}"; do
        current_check=$((current_check + 1))
        echo -n "[$current_check/$total_checks] Checking $role ($region)... "
        
        if check_instance "$role" "$region" "$SEARCH_TERM"; then
            echo -e "\033[32m$result\033[0m"
            exit 0
        else
            echo "not found"
        fi
    done
done

echo "Instance not found in any account/region"
exit 1
