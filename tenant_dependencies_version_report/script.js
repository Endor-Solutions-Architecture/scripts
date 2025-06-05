const EndorSDK = require('../endor_common/js/sdk');
const { getFormattedTimestamp } = require('../endor_common/js/utils');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Configuration
const NAMESPACE = process.env.NAMESPACE;
const REPORTS_DIR = 'generated_reports';

// Helper function to write CSV
function writeToCSV(dependencies, filename) {
    // Create reports directory if it doesn't exist
    if (!fs.existsSync(REPORTS_DIR)) {
        fs.mkdirSync(REPORTS_DIR, { recursive: true });
    }

    const header = 'Ecosystem,Dependency,Version,Dependent Packages Count\n';
    const rows = dependencies.map(dep => 
        `"${dep.ecosystem}","${dep.name}","${dep.version}","${dep.dependent_packages_count}"`
    ).join('\n');
    
    const filepath = path.join(REPORTS_DIR, filename);
    fs.writeFileSync(filepath, header + rows);
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
        
        // Write results to CSV
        const timestamp = getFormattedTimestamp();
        const filename = `${NAMESPACE}_dependency_versions_${timestamp}.csv`;
        writeToCSV(dependencies, filename);
        
        console.log(`\nProcessing complete. Results written to ${REPORTS_DIR}/${filename}`);
        console.log(`Total unique dependencies found: ${dependencies.length}`);
        
    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

// Run the script
if (require.main === module) {
    main();
} 