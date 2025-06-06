const EndorSDK = require('../endor_common/js/sdk');
const { getFormattedTimestamp } = require('../endor_common/js/utils');
const { buildFindingsFilter, processFinding } = require('./utils/findings');
const { consolidateDependencyData, generateFilename, writeToCSV } = require('./utils/output');
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
            'list_parameters.mask': 'uuid,spec.project_uuid,spec.summary,spec.target_dependency_name,spec.target_dependency_version,spec.relationship,context.type,context.id',
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
        const filename = generateFilename(NAMESPACE, PROJECT_UUID, BRANCH, timestamp);
        writeToCSV(enhancedDependencies, filename, REPORTS_DIR);

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