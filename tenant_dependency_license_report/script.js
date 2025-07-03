const EndorSDK = require('../endor_common/js/sdk');
const { getFormattedTimestamp } = require('../endor_common/js/utils');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Configuration
const NAMESPACE = process.env.NAMESPACE;
const REPORTS_DIR = 'generated_reports';

// Helper function to process SBOM components
function processComponents(components) {
    const uniqueComponents = new Map();

    components.forEach(component => {
        const bomRef = component["bom-ref"];
        const license = component.licenses?.[0]?.license?.name || 'No License';

        uniqueComponents.set(bomRef, {
            name: component.name,
            package: bomRef,
            version: component.version,
            license: license
        });
    });

    return Array.from(uniqueComponents.values());
}

// Helper function to write CSV header
function writeCSVHeader(filename) {
    // Create reports directory if it doesn't exist
    if (!fs.existsSync(REPORTS_DIR)) {
        fs.mkdirSync(REPORTS_DIR, { recursive: true });
    }

    const header = 'Project UUID,Project Name,Package,Name,Version,License\n';
    const filepath = path.join(REPORTS_DIR, filename);
    fs.writeFileSync(filepath, header);
}

// Helper function to append CSV rows
function appendToCSV(components, projectUuid, projectName, filename) {
    const filepath = path.join(REPORTS_DIR, filename);
    const rows = components.map(comp =>
        `"${projectUuid}","${projectName}","${comp.package}","${comp.name}","${comp.version}","${comp.license}"`
    ).join('\n');

    // Append to file (add newline if file is not empty)
    const content = fs.existsSync(filepath) && fs.statSync(filepath).size > 0 ? '\n' + rows : rows;
    fs.appendFileSync(filepath, content);
}

// Helper function to log errors to file
function logError(errorType, projectUuid, projectName, errorMessage, errorDetails = null, errorFile) {
    const timestamp = new Date().toISOString();
    const errorEntry = {
        timestamp,
        errorType,
        projectUuid: projectUuid || 'N/A',
        projectName: projectName || 'N/A',
        errorMessage,
        errorDetails: errorDetails || 'N/A'
    };

    const errorLine = `${timestamp} | ${errorType} | ${projectUuid} | ${projectName} | ${errorMessage} | ${errorDetails}\n`;
    fs.appendFileSync(errorFile, errorLine);
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

        // Get all projects
        console.log('Fetching projects...');
        const projectsResponse = await sdk.projects.getAllProjects(NAMESPACE);
        const projects = projectsResponse.list?.objects || [];

        console.log(`Found ${projects.length} projects. Fetching SBOM data...`);

        // Create CSV file with header
        const timestamp = getFormattedTimestamp();
        const filename = `${NAMESPACE}_dependency_license_${timestamp}.csv`;
        const errorFilename = `${NAMESPACE}_errors_${timestamp}.log`;
        const errorFile = path.join(REPORTS_DIR, errorFilename);

        writeCSVHeader(filename);

        // Create error log file with header
        if (!fs.existsSync(REPORTS_DIR)) {
            fs.mkdirSync(REPORTS_DIR, { recursive: true });
        }
        const errorHeader = 'Timestamp | Error Type | Project UUID | Project Name | Error Message | Error Details\n';
        fs.writeFileSync(errorFile, errorHeader);

        // Process each project
        let processedProjects = 0;
        let totalComponents = 0;
        let errorCount = 0;

        for (const project of projects) {
            try {
                console.log(`Processing project: ${project.meta.name} (${++processedProjects}/${projects.length})`);
                const sbomResponse = await sdk.sbom.generateSbom(project);

                if (sbomResponse.spec?.data) {
                    try {
                        const sbomData = JSON.parse(sbomResponse.spec.data);
                        if (sbomData.components) {
                            const components = processComponents(sbomData.components);
                            appendToCSV(components, project.uuid, project.meta.name, filename);
                            totalComponents += components.length;
                            console.log(`  Added ${components.length} dependencies`);
                        }
                    } catch (parseError) {
                        const errorMsg = `Error parsing SBOM data: ${parseError.message}`;
                        console.error(`Error parsing SBOM data for project ${project.meta.name}: ${parseError.message}`);
                        logError('PARSE_ERROR', project.uuid, project.meta.name, errorMsg, parseError.stack, errorFile);
                        errorCount++;
                    }
                } else {
                    logError('NO_SBOM_DATA', project.uuid, project.meta.name, 'No SBOM data in response', '', errorFile);
                    errorCount++;
                }
            } catch (error) {
                const errorMsg = `Error processing project: ${error.message}`;
                console.error(`Error processing project ${project.meta.name}: ${error.message}`);
                logError('PROCESSING_ERROR', project.uuid, project.meta.name, errorMsg, error.stack, errorFile);
                errorCount++;
            }
        }

        console.log(`\nProcessing complete. Results written to ${REPORTS_DIR}/${filename}`);
        console.log(`Total projects processed: ${processedProjects}`);
        console.log(`Total dependencies found: ${totalComponents}`);
        console.log(`Total errors encountered: ${errorCount}`);
        if (errorCount > 0) {
            console.log(`Errors logged to: ${REPORTS_DIR}/${errorFilename}`);
        }

    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

// Run the script
if (require.main === module) {
    main();
}