const axios = require('axios');
const path = require('path');
require('dotenv').config({ path: path.resolve(process.cwd(), '.env') });
const { API_URL } = require('./config');

class EndorClient {
    constructor(options = {}) {
        this.apiKey = options.apiKey;
        this.apiSecret = options.apiSecret;
        this.token = options.apiToken;
        this.headers = null;
    }

    async authenticate() {
        if (this.token) {
            this.headers = {
                'User-Agent': 'curl/7.68.0',
                'Accept': '*/*',
                'Authorization': `Bearer ${this.token}`,
                'Request-Timeout': '600'
            };
            return;
        }

        if (!this.apiKey || !this.apiSecret) {
            throw new Error('Either API token or both API key and secret must be provided');
        }

        const url = `${API_URL}/auth/api-key`;
        const payload = {
            key: this.apiKey,
            secret: this.apiSecret
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
                this.token = response.data.token;
                this.headers = {
                    'User-Agent': 'curl/7.68.0',
                    'Accept': '*/*',
                    'Authorization': `Bearer ${this.token}`,
                    'Request-Timeout': '600'
                };
            } else {
                throw new Error(`Failed to get token: ${response.status}, ${response.data}`);
            }
        } catch (error) {
            throw new Error(`Failed to get token: ${error.message}`);
        }
    }

    async request(method, endpoint, params = {}, data = null) {
        if (!this.headers) {
            await this.authenticate();
        }

        try {
            const response = await axios({
                method,
                url: `${API_URL}${endpoint}`,
                headers: this.headers,
                params,
                data,
                timeout: 300000
            });
            return response.data;
        } catch (error) {
            throw new Error(`Request failed: ${error.message}`);
        }
    }
}

module.exports = EndorClient;