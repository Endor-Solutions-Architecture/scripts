class SBOM {
    constructor(client) {
        this.client = client;
    }

    async generateSbom(namespace, project) {
        const payload = {
            meta: {
                name: project.meta.name,
            },
            spec: {
                kind: "SBOM_KIND_CYCLONEDX",
                component_type: "COMPONENT_TYPE_APPLICATION",
                format: "FORMAT_JSON",
                export_parameters: {
                    project_uuid: project.uuid
                }
            }

        };


        return await this.client.request(
            'POST',
            `/namespaces/${namespace}/sbom-export`,
            {},  // no query params
            payload
        );
    }

    // Add other SBOM-related methods here
}

module.exports = SBOM; 