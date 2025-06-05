const EndorSDK = require('../endor_common/js/sdk');
const { getFormattedTimestamp } = require('../endor_common/js/utils');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Configuration
const NAMESPACE = process.env.NAMESPACE;
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
    const latestRegex = /latest release (v\d+\.\d+\.\d+)/i;

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
        const dependencies = await sdk.dependencies.listAllForTenantGrouped(NAMESPACE);
        console.log(`Found ${dependencies.length} dependencies. Processing...`);

        // Get findings for a specific policy
        console.log('\nFetching findings...');
        const findingsParams = {
            'list_parameters.mask': 'uuid,spec.project_uuid,spec.summary,spec.target_dependency_name,spec.target_dependency_version,spec.relationship,context.type,context.id',
            'list_parameters.traverse': 'true',
            'list_parameters.count': 'false',
            'list_parameters.filter': '(spec.finding_metadata.source_policy_info.uuid==67eed613ac4c5329347e0764) and context.type == "CONTEXT_TYPE_MAIN"'
        };
        
        const rawFindings = await sdk.findings.listFindings(NAMESPACE, findingsParams);
        const findings = rawFindings.map(processFinding);
        console.log(`Found ${findings.length} findings with the specified policy.`);

        // Consolidate data and write to CSV
        const enhancedDependencies = consolidateDependencyData(dependencies, findings);
        
        const timestamp = getFormattedTimestamp();
        const filename = `${NAMESPACE}_dependency_versions_${timestamp}.csv`;
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