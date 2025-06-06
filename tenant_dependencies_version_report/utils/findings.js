/**
 * Utilities for processing and filtering findings
 */

/**
 * Build the findings filter based on parameters
 * @param {string} policyUuid - The policy UUID to filter by
 * @param {string|null} projectUuid - Optional project UUID
 * @param {string|null} branch - Optional branch name
 * @returns {string} The complete filter string
 */
function buildFindingsFilter(policyUuid, projectUuid, branch) {
    if (projectUuid && branch) {
        // Project and branch specific filter
        return `spec.project_uuid==${projectUuid} and context.type == CONTEXT_TYPE_REF and context.id==${branch} and spec.finding_metadata.source_policy_info.uuid==${policyUuid} and spec.finding_tags not contains [FINDING_TAGS_EXCEPTION]`;
    } else if (projectUuid) {
        // Project specific filter
        return `spec.project_uuid==${projectUuid} and context.type == CONTEXT_TYPE_MAIN and spec.finding_metadata.source_policy_info.uuid==${policyUuid} and spec.finding_tags not contains [FINDING_TAGS_EXCEPTION]`;
    } else {
        // Tenant-wide filter
        return `(spec.finding_metadata.source_policy_info.uuid==${policyUuid}) and context.type == "CONTEXT_TYPE_MAIN" and spec.finding_tags not contains [FINDING_TAGS_EXCEPTION]`;
    }
}

/**
 * Extract release information from summary text using regex
 * @param {string} summary - The finding summary text
 * @returns {Object} Object containing releases_behind and latest_release
 */
function extractReleaseInfo(summary = '') {
    const releasesRegex = /(\d+) releases behind/;
    const latestRegex = /latest release ([^\s.]*[0-9][^\s.]*(?:\.[^\s.]+)*|release-\d{4}-\d{2}-\d{2})\./i;

    const releasesMatch = summary.match(releasesRegex);
    const latestMatch = summary.match(latestRegex);

    return {
        releases_behind: releasesMatch ? parseInt(releasesMatch[1]) : null,
        latest_release: latestMatch ? latestMatch[1] : null
    };
}

/**
 * Process a finding object to extract relevant information
 * @param {Object} finding - The finding object from API
 * @returns {Object} Processed finding data
 */
function processFinding(finding) {
    const releaseInfo = extractReleaseInfo(finding.spec?.summary);

    return {
        uuid: finding.uuid,
        summary: finding.spec?.summary,
        project_uuid: finding.spec?.project_uuid,
        dependency_name: finding.spec?.target_dependency_name,
        dependency_version: finding.spec?.target_dependency_version,
        name_version: `${finding.spec?.target_dependency_name}@${finding.spec?.target_dependency_version}`,
        relationship: finding.spec?.relationship,
        context_type: finding.context?.type,
        context_id: finding.context?.id,
        ...releaseInfo
    };
}

module.exports = {
    buildFindingsFilter,
    extractReleaseInfo,
    processFinding
}; 