#!/bin/bash

set -e  # Exit on any error

# Check if namespace argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <namespace>"
    echo "Example: $0 your-namespace"
    echo ""
    echo "This script will:"
    echo "1. Get all child namespaces from the specified namespace"
    echo "2. Find all projects in each namespace"
    echo "3. Disable automated scan for all projects"
    exit 1
fi

PARENT_NAMESPACE="$1"

# Define jagg alias for JSON aggregation
alias jagg='jq -r -c '\''.group_response.groups | to_entries | map_values((.key | fromjson | from_entries) + (.value | .aggregation_count + .unique_values?)) | .[]'\'
alias endorctl='~/endorctl'

echo "Starting automated scan disable process for parent namespace: $PARENT_NAMESPACE"

echo "Step 1: Fetching all namespaces..."
all_namespaces=$(endorctl api list -n "$PARENT_NAMESPACE" -r DependencyMetadata --traverse --group-aggregation-paths tenant_meta.namespace | jagg | jq -r '.["tenant_meta.namespace"]')

if [ -z "$all_namespaces" ]; then
    echo "Error: No namespaces found!"
    exit 1
fi

namespace_count=$(echo "$all_namespaces" | wc -l)
echo "Found $namespace_count namespaces"

echo "Step 2: Processing each namespace and updating projects..."
total_projects=0
processed_projects=0

while read -r ns; do
    echo "Processing namespace: $ns"
    project_uuids=$(endorctl api list -n $ns -r Project --list-all -t 3600s | jq -r '.list.objects[].uuid' 2>/dev/null || echo "")
    echo "project_uuids: "

    if [ -z "$project_uuids" ]; then
        echo "  No projects found in namespace: $ns"
        continue
    fi
    
    project_count=$(echo "$project_uuids" | wc -l)
    total_projects=$((total_projects + project_count))
    echo "Found $project_count projects in namespace: $ns"
    
    while read -r project_uuid; do
        if [ -n "$project_uuid" ]; then
            echo "    Updating project: $project_uuid"
            if endorctl --namespace "$ns" api update -r project --uuid="$project_uuid" --field-mask=processing_status.disable_automated_scan --data='{"processing_status":{"disable_automated_scan": true }}' 2>/dev/null; then
                processed_projects=$((processed_projects + 1))
                echo "Successfully updated project: $project_uuid"
            else
                echo "Failed to update project: $project_uuid"
            fi
        fi
    done <<< "$project_uuids"
    
    echo "Completed namespace: $ns"
    echo ""
done <<< "$all_namespaces"

echo "Process completed!"
echo "Total projects found: $total_projects"
echo "Projects successfully processed: $processed_projects"
echo "Done!"