class Projects {
    constructor(client) {
        this.client = client;
    }

    async getAllProjects(namespace, traverse = true, options = {}) {
        const defaultOptions = {
            'list_parameters.page_size': 500,
            'list_parameters.traverse': traverse,
            'list_parameters.mask': 'uuid,meta.name,tenant_meta.namespace'
        };

        const params = {
            ...defaultOptions,
            ...options
        };

        // Initialize variables for pagination
        let allProjects = [];
        let pageToken = null;

        do {
            const currentParams = pageToken
                ? { ...params, 'list_parameters.page_token': pageToken }
                : params;

            const response = await this.client.request(
                'GET',
                `/namespaces/${namespace}/projects`,
                currentParams
            );

            const projects = response.list?.objects || [];
            allProjects = allProjects.concat(projects);

            pageToken = response.list?.response?.next_page_token;
        } while (pageToken);

        return {
            list: {
                objects: allProjects,
                response: {
                    next_page_token: null
                }
            }
        };
    }

    // Add other project-related methods here
}

module.exports = Projects;