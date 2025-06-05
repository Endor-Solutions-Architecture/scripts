class SBOM {
    constructor(client) {
        this.client = client;
    }

    async generateSbom(project) {
        const payload = {
            meta: {
                kind: "ExportedSBOM",
                name: project.meta.name,
                version: "v1"
            },
            spec: {
                kind: "SBOM_KIND_CYCLONEDX",
                component_type: "COMPONENT_TYPE_APPLICATION",
                format: "FORMAT_JSON",
                export_parameters: {
                    project_uuid: project.uuid
                }
            },
            tenant_meta: {
                namespace: project.tenant_meta.namespace
            }
        };


        return await this.client.request(
            'POST',
            `/namespaces/${project.tenant_meta.namespace}/sbom-export`,
            {},  // no query params
            payload
        );
    }

    // Add other SBOM-related methods here
}

module.exports = SBOM; 