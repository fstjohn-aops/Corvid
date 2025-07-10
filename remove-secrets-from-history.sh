#!/bin/bash

################################################################################
# CONFIGURATION - Variables to Clean from History
################################################################################

# List of variable names to clean from history
# Add your secret/sensitive variable names here
VARIABLES_TO_CLEAN=(
    "API_KEY"
    "SECRET_KEY" 
    "PASSWORD"
    "TOKEN"
    "DATABASE_URL"
    "PRIVATE_KEY"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_SESSION_TOKEN"
    "CLOUDFLARE_API_TOKEN"
    # Add more variable names as needed
)

################################################################################
# HISTORY FILE DETECTION
################################################################################

# Determine the history file based on the shell
if [[ "$SHELL" == *"zsh"* ]]; then
    HISTORY_FILE="$HOME/.zsh_history"
elif [[ "$SHELL" == *"bash"* ]]; then
    HISTORY_FILE="$HOME/.bash_history"
else
    # Default to bash history if can't determine
    HISTORY_FILE="$HOME/.bash_history"
fi

# Check if history file exists
if [[ ! -f "$HISTORY_FILE" ]]; then
    echo "History file not found: $HISTORY_FILE"
    exit 1
fi

################################################################################
# INITIALIZATION & BACKUP
################################################################################

echo "Cleaning history file: $HISTORY_FILE"
echo "Variables to clean:"
for var in "${VARIABLES_TO_CLEAN[@]}"; do
    echo "  - $var"
done
echo

# Create a backup of the history file
BACKUP_FILE="${HISTORY_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$HISTORY_FILE" "$BACKUP_FILE"
echo "Created backup: $BACKUP_FILE"
echo

################################################################################
# COLLECT MATCHING LINES
################################################################################

echo "Scanning for matching lines..."
declare -a MATCHING_LINES
declare -a LINE_NUMBERS

# Read the history file line by line and collect matches
line_num=0
while IFS= read -r line; do
    ((line_num++))
    
    # Check each variable for matches
    for var in "${VARIABLES_TO_CLEAN[@]}"; do
        # Check for regular patterns
        regular_pattern="^[^#]*[[:space:]]*(export[[:space:]]+)?${var}[[:space:]]*="
        if [[ "$line" =~ $regular_pattern ]]; then
            MATCHING_LINES+=("$line")
            LINE_NUMBERS+=("$line_num")
            break
        fi
        
        # Also check zsh history format
        if [[ "$SHELL" == *"zsh"* ]]; then
            zsh_pattern="^:[^;]*;[^#]*[[:space:]]*(export[[:space:]]+)?${var}[[:space:]]*="
            if [[ "$line" =~ $zsh_pattern ]]; then
                MATCHING_LINES+=("$line")
                LINE_NUMBERS+=("$line_num")
                break
            fi
        fi
    done
done < "$HISTORY_FILE"

echo -e "\rFound ${#MATCHING_LINES[@]} matching lines to review."

if [[ ${#MATCHING_LINES[@]} -eq 0 ]]; then
    echo "No matching lines found. Exiting."
    exit 0
fi

################################################################################
# INTERACTIVE CONFIRMATION
################################################################################

echo
echo "Press ENTER to delete each line, or 'n' + ENTER to keep it:"
echo "========================================================"

# Array to store line numbers to delete
declare -a LINES_TO_DELETE
confirmed_count=0

for i in "${!MATCHING_LINES[@]}"; do
    line_num="${LINE_NUMBERS[$i]}"
    line_content="${MATCHING_LINES[$i]}"
    
    # Extract just the command part (handle zsh history format)
    if [[ "$SHELL" == *"zsh"* ]]; then
        zsh_extract_pattern="^:[^;]*;(.*)$"
        if [[ "$line_content" =~ $zsh_extract_pattern ]]; then
            command_only="${BASH_REMATCH[1]}"
        else
            command_only="$line_content"
        fi
    else
        command_only="$line_content"
    fi
    
    # Display current progress and line
    printf "\r\033[K[%d/%d] Line %d: %s" $((i+1)) ${#MATCHING_LINES[@]} "$line_num" "$command_only"
    
    # Get user input
    read -r response
    
    if [[ "$response" != "n" && "$response" != "N" ]]; then
        LINES_TO_DELETE+=("$line_num")
        ((confirmed_count++))
        printf "\r\033[K✓ Marked for deletion: Line %d\n" "$line_num"
    else
        printf "\r\033[K• Keeping: Line %d\n" "$line_num"
    fi
done

################################################################################
# PERFORM DELETIONS
################################################################################

if [[ ${#LINES_TO_DELETE[@]} -eq 0 ]]; then
    echo
    echo "No lines marked for deletion. Exiting."
    exit 0
fi

echo
echo "Deleting $confirmed_count lines..."

# Sort line numbers in descending order (delete from bottom up to preserve line numbers)
IFS=$'\n' LINES_TO_DELETE=($(sort -nr <<<"${LINES_TO_DELETE[*]}"))

# Create temporary file for the cleaned history
temp_file=$(mktemp)
cp "$HISTORY_FILE" "$temp_file"

# Delete lines in descending order
for line_num in "${LINES_TO_DELETE[@]}"; do
    sed -i.tmp "${line_num}d" "$temp_file"
    rm -f "${temp_file}.tmp" 2>/dev/null
    printf "\r\033[KDeleted line %d" "$line_num"
done

# Replace the original history file
mv "$temp_file" "$HISTORY_FILE"

################################################################################
# COMPLETION & RESULTS
################################################################################

echo
echo
echo "Cleanup complete!"
echo "Total lines deleted: $confirmed_count"
echo "Backup saved as: $BACKUP_FILE"
echo
echo "Note: You may need to restart your shell or run 'history -r' to reload the cleaned history."

# Optional: Clear the current session's history cache
if [[ "$SHELL" == *"zsh"* ]]; then
    echo "Run 'fc -R' to reload history in the current session."
elif [[ "$SHELL" == *"bash"* ]]; then
    echo "Run 'history -r' to reload history in the current session."
fi 