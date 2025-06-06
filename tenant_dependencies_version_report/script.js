const EndorSDK = require('../endor_common/js/sdk');
const { getFormattedTimestamp } = require('../endor_common/js/utils');
const fs = require('fs');
const path = require('path');
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');
require('dotenv').config();

// Parse command line arguments
const argv = yargs(hideBin(process.argv))
    .option('project-uuid', {
        alias: 'p',
        type: 'string',
        description: 'Project UUID to analyze'
    })
    .option('branch-name', {
        alias: 'b',
        type: 'string',
        description: 'Branch name to analyze'
    })
    .help()
    .argv;

const PROJECT_UUID = argv['project-uuid'] || null;
const BRANCH = argv['branch-name'] || null;

// Validate branch parameter
if (BRANCH && !PROJECT_UUID) {
    console.error('Error: --branch-name can only be used when --project-uuid is specified');
    process.exit(1);
}

// Configuration
const NAMESPACE = process.env.NAMESPACE;
const OUTDATED_POLICY_UUID = process.env.OUTDATED_POLICY_UUID;
const REPORTS_DIR = 'generated_reports';

/**
 * Consolidate dependencies with findings data
 * @param {Array} dependencies - List of dependencies
 * @param {Array} findings - List of processed findings
 * @returns {Array} Enhanced dependencies with findings data
 */
function consolidateDependencyData(dependencies, findings) {
    // Create a map of findings by name@version for quick lookup
    const findingsMap = new Map(
        findings.map(finding => [finding.name_version, finding])
    );

    return dependencies.map(dep => {
        const nameVersion = `${dep.name}@${dep.version}`;
        const finding = findingsMap.get(nameVersion);

        return {
            ecosystem: dep.ecosystem,
            name: dep.name,
            version: dep.version,
            dependent_packages_count: parseInt(dep.dependent_packages_count) || 0,
            is_outdated: !!finding,
            latest_release: finding?.latest_release || null,
            releases_behind: finding?.releases_behind || null
        };
    });
}

/**
 * Write enhanced dependency data to CSV
 * @param {Array} enhancedDependencies - Dependencies with findings data
 * @param {string} filename - Output filename
 */
function writeToCSV(enhancedDependencies, filename) {
    // Create reports directory if it doesn't exist
    if (!fs.existsSync(REPORTS_DIR)) {
        fs.mkdirSync(REPORTS_DIR, { recursive: true });
    }

    const header = 'Ecosystem,Dependency,Version,Dependent Packages,Is Outdated,Latest Release,Releases Behind\n';
    const rows = enhancedDependencies.map(dep => 
        `"${dep.ecosystem}","${dep.name}","${dep.version}",${dep.dependent_packages_count},${dep.is_outdated},"${dep.latest_release || ''}",${dep.releases_behind || ''}`
    ).join('\n');
    
    const filepath = path.join(REPORTS_DIR, filename);
    fs.writeFileSync(filepath, header + rows);
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

async function main() {
    // Validate environment variables
    if (!process.env.API_TOKEN && (!process.env.API_KEY || !process.env.API_SECRET)) {
        console.error('Error: Either API_TOKEN or both API_KEY and API_SECRET must be set in .env file');
        process.exit(1);
    }

    if (!NAMESPACE) {
        console.error('Error: NAMESPACE must be set in .env file');
        process.exit(1);
    }

    if (!OUTDATED_POLICY_UUID) {
        console.error('Error: OUTDATED_POLICY_UUID must be set in .env file');
        process.exit(1);
    }

    try {
        // Initialize SDK with options
        const sdk = new EndorSDK({
            apiKey: process.env.API_KEY,
            apiSecret: process.env.API_SECRET,
            apiToken: process.env.API_TOKEN
        });
        await sdk.authenticate();
        
        // Get dependency metadata
        console.log('Fetching dependency metadata...');
        let dependencies;
        if (PROJECT_UUID) {
            console.log(`Fetching dependencies for project ${PROJECT_UUID}${BRANCH ? ` (branch: ${BRANCH})` : ''}...`);
            dependencies = await sdk.dependencies.listAllForProjectGrouped(NAMESPACE, PROJECT_UUID, BRANCH);
        } else {
            console.log('Fetching dependencies for entire tenant...');
            dependencies = await sdk.dependencies.listAllForTenantGrouped(NAMESPACE);
        }
        console.log(`Found ${dependencies.length} dependencies. Processing...`);

        // Get findings for a specific policy
        console.log('\nFetching findings...');
        const findingsParams = {
            'list_parameters.mask': 'uuid,spec.project_uuid,spec.summary,spec.target_dependency_name,spec.target_dependency_version,spec.relationship,context.type,context.id,meta',
            'list_parameters.traverse': 'true',
            'list_parameters.count': 'false',
            'list_parameters.filter': buildFindingsFilter(OUTDATED_POLICY_UUID, PROJECT_UUID, BRANCH)
        };
        
        const rawFindings = await sdk.findings.listFindings(NAMESPACE, findingsParams);
        const findings = rawFindings.map(processFinding);
        console.log(`Found ${findings.length} findings with the specified policy.`);

        // Consolidate data and write to CSV
        const enhancedDependencies = consolidateDependencyData(dependencies, findings);
        
        const timestamp = getFormattedTimestamp();
        let filePrefix;
        if (PROJECT_UUID) {
            // For project-specific reports
            const branchPart = BRANCH || 'main';
            filePrefix = `${NAMESPACE}_${PROJECT_UUID}_${branchPart}`;
        } else {
            // For tenant-wide reports
            filePrefix = NAMESPACE;
        }
        const filename = `${filePrefix}_dependency_versions_${timestamp}.csv`;
        writeToCSV(enhancedDependencies, filename);

        console.log(`\nProcessing complete. Results written to ${REPORTS_DIR}/${filename}`);
        console.log(`Total unique dependencies found: ${dependencies.length}`);
        console.log(`Dependencies with outdated versions: ${enhancedDependencies.filter(d => d.is_outdated).length}`);
        
    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

// Run the script
if (require.main === module) {
    main();
} 