const axios = require('axios');
require('dotenv').config();

// Configuration
const ENDOR_NAMESPACE = process.env.ENDOR_NAMESPACE;
const API_URL = 'https://api.endorlabs.com/v1';

// Get token function
async function getToken() {
    const apiKey = process.env.API_KEY;
    const apiSecret = process.env.API_SECRET;
    
    if (!apiKey || !apiSecret) {
        throw new Error('API_KEY and API_SECRET must be set in .env file');
    }
    
    const url = `${API_URL}/auth/api-key`;
    
    const payload = {
        key: apiKey,
        secret: apiSecret
    };
    
    const headers = {
        'Content-Type': 'application/json',
        'Request-Timeout': '60'
    };

    try {
        const response = await axios.post(url, payload, { 
            headers, 
            timeout: 60000 
        });
        
        if (response.status === 200) {
            return response.data.token;
        } else {
            throw new Error(`Failed to get token: ${response.status}, ${response.data}`);
        }
    } catch (error) {
        throw new Error(`Failed to get token: ${error.message}`);
    }
}

// Initialize API token and headers
let API_TOKEN;
let HEADERS;

async function initializeAuth() {
    API_TOKEN = await getToken();
    HEADERS = {
        'User-Agent': 'curl/7.68.0',
        'Accept': '*/*',
        'Authorization': `Bearer ${API_TOKEN}`,
        'Request-Timeout': '600'
    };
}

// Get findings with grouping and aggregation
async function getFindings(namespace, projectUuid) {
    const url = `${API_URL}/namespaces/${namespace}/findings`;
    
    // Build the filter without finding level
    const filter = `((spec.project_uuid=="${projectUuid}" and context.type == "CONTEXT_TYPE_MAIN") and spec.finding_tags not contains ["FINDING_TAGS_EXCEPTION"]) and meta.parent_kind==PackageVersion and spec.finding_tags not contains [FINDING_TAGS_SELF]`;
    
    const params = {
        'list_parameters.filter': filter,
        'list_parameters.group.aggregation_paths': 'spec.target_dependency_package_name',
        'list_parameters.group.show_aggregation_uuids': 'true',
        'list_parameters.group.unique_count_paths': 'spec.project_uuid,meta.description',
        'list_parameters.group.unique_value_paths': 'meta.description',
        'list_parameters.timeout': '60s'
    };
    
    const findingsData = {
        projectUuid,
        totalFindings: 0,
        dependencyGroups: []
    };
    
    let nextPageId = null;

    while (true) {
        if (nextPageId) {
            params['list_parameters.page_id'] = nextPageId;
        }

        try {
            const response = await axios.get(url, { 
                headers: HEADERS, 
                params, 
                timeout: 60000 
            });

            if (response.status !== 200) {
                throw new Error(`Failed to get findings, Status Code: ${response.status}, Response: ${response.data}`);
            }

            const responseData = response.data;
            
            // Process grouped findings - updated to handle the actual response structure
            const groups = responseData.group_response?.groups || {};
            
            // Iterate through the groups object
            for (const [groupKey, groupData] of Object.entries(groups)) {
                // Parse the group key to extract the dependency name
                let dependencyName = 'Unknown';
                try {
                    const parsedKey = JSON.parse(groupKey);
                    if (parsedKey && parsedKey.length > 0 && parsedKey[0].value) {
                        dependencyName = parsedKey[0].value;
                    }
                } catch (e) {
                    // Silently handle parsing errors
                }
                
                const findingCount = groupData.aggregation_count?.count || 0;
                const uniqueDescriptions = groupData.unique_values?.['meta.description'] || [];
                const projectCount = groupData.unique_counts?.['spec.project_uuid']?.count || 0;
                const descriptionCount = groupData.unique_counts?.['meta.description']?.count || 0;
                
                findingsData.dependencyGroups.push({
                    dependencyPackageName: dependencyName,
                    findingCount,
                    uniqueDescriptions,
                    projectCount,
                    descriptionCount,
                    aggregationUuids: groupData.aggregation_uuids || []
                });
                
                findingsData.totalFindings += findingCount;
            }

            nextPageId = responseData.list?.response?.next_page_id;
            if (!nextPageId) {
                break;
            }
        } catch (error) {
            throw new Error(`Error fetching findings: ${error.message}`);
        }
    }

    return findingsData;
}

// Main function
async function main() {
    // Parse command line arguments
    const args = process.argv.slice(2);
    let projectUuid = null;
    
    // Get project UUID from command line arguments
    if (args.length > 0) {
        projectUuid = args[0];
    }
    
    // Also check for --project_uuid flag for backwards compatibility
    const projectUuidIndex = args.indexOf('--project_uuid');
    if (projectUuidIndex !== -1 && projectUuidIndex + 1 < args.length) {
        projectUuid = args[projectUuidIndex + 1];
    }
    
    if (!projectUuid) {
        console.error('Error: project_uuid is required');
        console.error('Usage: node script.js <project_uuid>');
        console.error('   or: node script.js --project_uuid <project_uuid>');
        process.exit(1);
    }

    try {
        // Initialize authentication
        await initializeAuth();
        
        // Get findings for the specified project
        const findingsData = await getFindings(ENDOR_NAMESPACE, projectUuid);
        
        const results = {
            summary: {
                namespace: ENDOR_NAMESPACE,
                projectUuid: projectUuid,
                totalFindings: findingsData.totalFindings,
                totalDependencies: findingsData.dependencyGroups.length,
                processedAt: new Date().toISOString()
            },
            dependencyGroups: findingsData.dependencyGroups
        };

        // Output only the final JSON results
        console.log(JSON.stringify(results, null, 2));
        
    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

// Run the script
if (require.main === module) {
    main();
} 