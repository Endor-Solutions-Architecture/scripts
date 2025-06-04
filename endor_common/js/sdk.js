const EndorClient = require('./client');
const Projects = require('./projects');
const SBOM = require('./sbom');

class EndorSDK {
    constructor(options = {}) {
        this.client = new EndorClient({
            apiKey: options.apiKey,
            apiSecret: options.apiSecret,
            apiToken: options.apiToken
        });
        this.projects = new Projects(this.client);
        this.sbom = new SBOM(this.client);
    }

    async authenticate() {
        await this.client.authenticate();
    }
}

module.exports = EndorSDK; 