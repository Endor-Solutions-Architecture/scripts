const EndorSDK = require('../endor_common/js/sdk');
const fs = require('fs');
require('dotenv').config();

// Configuration
const NAMESPACE = process.env.NAMESPACE;

// Helper function to process SBOM components
function processComponents(components) {
    const uniqueComponents = new Map();
    
    components.forEach(component => {
        const key = `${component.name}|${component.version}`;
        const license = component.licenses?.[0]?.license?.name || 'No License';
        
        uniqueComponents.set(key, {
            name: component.name,
            version: component.version,
            license: license
        });
    });
    
    return Array.from(uniqueComponents.values());
}

// Helper function to write CSV
function writeToCSV(components, filename) {
    const header = 'Name,Version,License\n';
    const rows = components.map(comp => 
        `"${comp.name}","${comp.version}","${comp.license}"`
    ).join('\n');
    
    fs.writeFileSync(filename, header + rows);
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
        
        // Process each project
        const allComponents = new Map();
        let processedProjects = 0;
        
        for (const project of projects) {
            try {
                console.log(`Processing project: ${project.meta.name} (${++processedProjects}/${projects.length})`);
                const sbomResponse = await sdk.sbom.generateSbom(NAMESPACE, project);
                
                if (sbomResponse.spec?.data) {
                    try {
                        const sbomData = JSON.parse(sbomResponse.spec.data);
                        if (sbomData.components) {
                            const components = processComponents(sbomData.components);
                            components.forEach(comp => {
                                const key = `${comp.name}|${comp.version}`;
                                allComponents.set(key, comp);
                            });
                        }
                    } catch (parseError) {
                        console.error(`Error parsing SBOM data for project ${project.meta.name}: ${parseError.message}`);
                    }
                }
            } catch (error) {
                console.error(`Error processing project ${project.meta.name}: ${error.message}`);
            }
        }
        
        // Write results to CSV
        const filename = `${NAMESPACE}_dependency_license.csv`;
        writeToCSV(Array.from(allComponents.values()), filename);
        
        console.log(`\nProcessing complete. Results written to ${filename}`);
        console.log(`Total unique dependencies found: ${allComponents.size}`);
        
    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

// Run the script
if (require.main === module) {
    main();
} 