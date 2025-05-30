const axios = require('axios');
require('dotenv').config();

const API_URL = 'https://api.endorlabs.com/v1';

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

async function initializeAuth() {
    const token = await getToken();
    const headers = {
        'User-Agent': 'curl/7.68.0',
        'Accept': '*/*',
        'Authorization': `Bearer ${token}`,
        'Request-Timeout': '600'
    };
    return { token, headers };
}

module.exports = {
    API_URL,
    getToken,
    initializeAuth
}; 