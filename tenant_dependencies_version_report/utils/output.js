const fs = require('fs');
const path = require('path');

/**
 * Consolidate dependencies with findings data
 * @param {Array} dependencies - List of dependencies
 * @param {Array} findings - List of processed findings
 * @returns {Array} Enhanced dependencies with findings data
 */
function consolidateDependencyData(dependencies, findings) {
    // Create a map of findings by name@version for quick lookup
    const findingsMap = new Map(
        findings.map(finding => [finding.name_version, finding])
    );

    return dependencies.map(dep => {
        const nameVersion = `${dep.name}@${dep.version}`;
        const finding = findingsMap.get(nameVersion);

        return {
            ecosystem: dep.ecosystem,
            name: dep.name,
            version: dep.version,
            dependent_packages_count: parseInt(dep.dependent_packages_count) || 0,
            is_outdated: !!finding,
            latest_release: finding?.latest_release || null,
            releases_behind: finding?.releases_behind || null
        };
    });
}

/**
 * Generate the output filename based on parameters
 * @param {string} namespace - The namespace
 * @param {string|null} projectUuid - Optional project UUID
 * @param {string|null} branch - Optional branch name
 * @param {string} timestamp - Formatted timestamp
 * @returns {string} The generated filename
 */
function generateFilename(namespace, projectUuid, branch, timestamp) {
    let filePrefix;
    if (projectUuid) {
        // For project-specific reports
        const branchPart = branch || 'main';
        filePrefix = `${namespace}_${projectUuid}_${branchPart}`;
    } else {
        // For tenant-wide reports
        filePrefix = namespace;
    }
    return `${filePrefix}_dependency_versions_${timestamp}.csv`;
}

/**
 * Write enhanced dependency data to CSV
 * @param {Array} enhancedDependencies - Dependencies with findings data
 * @param {string} filename - Output filename
 * @param {string} reportsDir - Directory to write the file to
 */
function writeToCSV(enhancedDependencies, filename, reportsDir) {
    // Create reports directory if it doesn't exist
    if (!fs.existsSync(reportsDir)) {
        fs.mkdirSync(reportsDir, { recursive: true });
    }

    const header = 'Ecosystem,Dependency,Version,Dependent Packages,Is Outdated,Latest Release,Releases Behind\n';
    const rows = enhancedDependencies.map(dep => 
        `"${dep.ecosystem}","${dep.name}","${dep.version}",${dep.dependent_packages_count},${dep.is_outdated},"${dep.latest_release || ''}",${dep.releases_behind || ''}`
    ).join('\n');
    
    const filepath = path.join(reportsDir, filename);
    fs.writeFileSync(filepath, header + rows);
}

module.exports = {
    consolidateDependencyData,
    generateFilename,
    writeToCSV
}; 