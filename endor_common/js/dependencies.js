class Dependencies {
    constructor(client) {
        this.client = client;
    }

    /**
     * List dependencies for a namespace with optional parameters
     * @param {string} namespace - The namespace to list dependencies for
     * @param {Object} params - Optional query parameters
     * @returns {Promise<Object>} The API response
     */
    async listDependencies(namespace, params = {}) {
        return await this.client.request(
            'GET',
            `/namespaces/${namespace}/dependency-metadata`,
            params
        );
    }

    /**
     * Extracts package information from a package identifier string
     * @param {string} packageId - Package identifier (e.g., "gem://activesupport@3.2.21")
     * @returns {Object} Object containing package, name, and version
     */
    _parsePackageId(packageId) {
        const [protocol, rest] = packageId.split('://')
        const [name, version] = rest.split('@')
        return {
            package: packageId,
            name: name,
            version: version,
            ecosystem: protocol,
            name_version: rest
        }
    }

    /**
     * List all dependencies for a tenant with grouping, returning processed results
     * @param {string} namespace - The namespace to list dependencies for
     * @returns {Promise<Array>} Array of processed dependency objects
     */
    async listAllForTenantGrouped(namespace) {
        const params = {
            'list_parameters.filter': 'context.type in ["CONTEXT_TYPE_MAIN","CONTEXT_TYPE_SBOM"]',
            'list_parameters.traverse': 'true',
            'list_parameters.count': 'false',
            'list_parameters.group.aggregation_paths': 'meta.name'
        };

        const response = await this.listDependencies(namespace, params);
        const groups = response.group_response?.groups || {};
        
        return Object.entries(groups).map(([key, value]) => {
            // Parse the key which is a stringified JSON array with a single object
            const keyObj = JSON.parse(key)[0];
            const packageInfo = this._parsePackageId(keyObj.value);
            
            return {
                ...packageInfo,
                dependent_packages_count: value.aggregation_count?.count || 0
            };
        });
    }
}

module.exports = Dependencies; 