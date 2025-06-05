class Findings {
    constructor(client) {
        this.client = client;
    }

    /**
     * List findings for a namespace with pagination
     * @param {string} namespace - The namespace to list findings for
     * @param {Object} params - Optional query parameters
     * @returns {Promise<Array>} Array of finding objects
     */
    async listFindings(namespace, params = {}) {
        let allFindings = [];
        let pageToken = null;
        
        do {
            const currentParams = pageToken 
                ? { ...params, 'list_parameters.page_token': pageToken }
                : params;

            const response = await this.client.request(
                'GET',
                `/namespaces/${namespace}/findings`,
                currentParams
            );

            const findings = response.list?.objects || [];
            allFindings = allFindings.concat(findings);

            pageToken = response.list?.response?.next_page_token;
        } while (pageToken);

        return allFindings;
    }
}

module.exports = Findings; 