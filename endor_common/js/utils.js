/**
 * Common utility functions used across Endor Labs scripts
 */

/**
 * Returns a formatted timestamp string in the format YYYY-MM-DD-HH-MM-SS
 * @returns {string} Formatted timestamp
 */
function getFormattedTimestamp() {
    const now = new Date();
    return now.toISOString()
        .replace(/[:.]/g, '-')
        .replace('T', '-')
        .split('-')
        .slice(0, 6)
        .join('-');
}

module.exports = {
    getFormattedTimestamp
}; 