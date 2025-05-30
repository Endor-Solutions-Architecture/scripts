class Projects {
    constructor(client) {
        this.client = client;
    }

    async getAllProjects(namespace, options = {}) {
        const defaultOptions = {
            'list_parameters.page_size': 500,
            'list_parameters.traverse': true,
            'list_parameters.mask': 'uuid,meta.name,tenant_meta.namespace'
        };

        const params = {
            ...defaultOptions,
            ...options
        };

        return await this.client.request(
            'GET',
            `/namespaces/${namespace}/projects`,
            params
        );
    }

    // Add other project-related methods here
}

module.exports = Projects; 