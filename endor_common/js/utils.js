/**
 * Common utility functions used across Endor Labs scripts
 */

/**
 * Returns a formatted timestamp string in the format YYYY-MM-DD-HH-MM-SS using local time
 * @returns {string} Formatted timestamp
 */
function getFormattedTimestamp() {
    const now = new Date();
    const pad = (num) => String(num).padStart(2, '0');
    
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}-${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
}

module.exports = {
    getFormattedTimestamp
}; 