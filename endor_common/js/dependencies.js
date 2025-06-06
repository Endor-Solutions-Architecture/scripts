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
     * @param {string} packageId - Package identifier (e.g., "npm://@ampproject/remapping@2.3.0" or "npm://strip-bom@https://registry.npmjs.org/strip-bom/-/strip-bom-1.0.0.tgz")
     * @returns {Object} Object containing package, name, version, and ecosystem
     */
    _parsePackageId(packageId) {
        // Find the first occurrence of :// to get the protocol
        const protocolIndex = packageId.indexOf('://');
        if (protocolIndex === -1) {
            throw new Error(`Invalid package identifier (no protocol): ${packageId}`);
        }

        const protocol = packageId.substring(0, protocolIndex);
        const rest = packageId.substring(protocolIndex + 3);

        // Find the first @ that's not part of the scope
        const isScoped = rest.startsWith('@');
        const startSearchIndex = isScoped ? rest.indexOf('/', 1) : 0;
        const versionIndex = rest.indexOf('@', startSearchIndex);

        if (versionIndex === -1) {
            throw new Error(`Invalid package identifier (no version): ${packageId}`);
        }

        const name = rest.substring(0, versionIndex);
        const version = rest.substring(versionIndex + 1);

        return {
            package: packageId,
            name: name,
            version: version,
            ecosystem: protocol,
            name_version: rest
        }
    }

    /**
     * List and process dependencies with grouping
     * @param {string} namespace - The namespace to list dependencies for
     * @param {Object} params - Query parameters for the API request
     * @returns {Promise<Array>} Array of processed dependency objects
     * @private
     */
    async _listAndProcessDependencies(namespace, params) {
        const baseParams = {
            'list_parameters.traverse': 'true',
            'list_parameters.count': 'false',
            'list_parameters.group.aggregation_paths': 'meta.name',
            ...params
        };

        const response = await this.listDependencies(namespace, baseParams);
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

    /**
     * List all dependencies for a tenant with grouping, returning processed results
     * @param {string} namespace - The namespace to list dependencies for
     * @returns {Promise<Array>} Array of processed dependency objects
     */
    async listAllForTenantGrouped(namespace) {
        return await this._listAndProcessDependencies(namespace, {
            'list_parameters.filter': 'context.type in ["CONTEXT_TYPE_MAIN","CONTEXT_TYPE_SBOM"]'
        });
    }

    /**
     * List all dependencies for a specific project
     * @param {string} namespace - The namespace to list dependencies for
     * @param {string} project_uuid - The project UUID to filter by
     * @param {string} branch - Optional branch parameter
     * @returns {Promise<Array>} Array of processed dependency objects
     */
    async listAllForProjectGrouped(namespace, project_uuid, branch) {
        const context_type = branch ? '[CONTEXT_TYPE_MAIN,CONTEXT_TYPE_REF]' : '[CONTEXT_TYPE_MAIN]';
        return await this._listAndProcessDependencies(namespace, {
            'list_parameters.group.aggregation_paths': 'meta.name',
            // 'list_parameters.filter': `spec.importer_data.project_uuid=="682cbadc6ca8b05216d995bf" and context.type in ["CONTEXT_TYPE_MAIN"]`
            'list_parameters.filter': `spec.importer_data.project_uuid==${project_uuid} and context.type in ${context_type}`
        });
    }
}

module.exports = Dependencies; 