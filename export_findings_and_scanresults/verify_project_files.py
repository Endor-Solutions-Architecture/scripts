#!/usr/bin/env python3
"""
Verify exported files for projects.

This script checks the exported JSON files for a given namespace and optionally
a specific project UUID. If no project UUID is provided, it verifies all projects
in the manifest and provides a summary.

Usage:
    # Verify a specific project
    python verify_project_files.py --namespace principal-prod --project-uuid 6643aa5c1fb5ef3c39fd15ec
    
    # Verify all projects in manifest
    python verify_project_files.py --namespace principal-prod
"""

import argparse
import json
import os
import sys
from pathlib import Path
from tqdm import tqdm


def count_records_in_file(file_path: str) -> int:
    """
    Count records in a JSON file.
    
    Args:
        file_path: Path to JSON file
    
    Returns:
        Number of records, or -1 if file doesn't exist or is invalid
    """
    if not os.path.exists(file_path):
        return -1
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return len(data)
            elif isinstance(data, dict):
                # Some files might be wrapped in a dict
                if 'list' in data and 'objects' in data['list']:
                    return len(data['list']['objects'])
                return 1  # Single object
            else:
                return 0
    except json.JSONDecodeError as e:
        print(f"  Error: Invalid JSON in {file_path}: {e}")
        return -1
    except Exception as e:
        print(f"  Error reading {file_path}: {e}")
        return -1


def verify_single_project(namespace: str, project_uuid: str, project_name: str = None) -> dict:
    """
    Verify exported files for a single project.
    
    Args:
        namespace: Namespace name
        project_uuid: Project UUID
        project_name: Optional project name for display
    
    Returns:
        Dictionary with verification results
    """
    exports_dir = Path("exports") / namespace
    
    findings_file = exports_dir / f"findings_{project_uuid}.json"
    scanresults_file = exports_dir / f"scanresults_{project_uuid}.json"
    
    result = {
        'project_uuid': project_uuid,
        'project_name': project_name or project_uuid[:8],
        'findings_file_exists': findings_file.exists(),
        'scanresults_file_exists': scanresults_file.exists(),
        'findings_count': -1,
        'scanresults_count': -1,
        'manifest_findings': -1,
        'manifest_scanresults': -1,
        'findings_match': False,
        'scanresults_match': False,
        'findings_error': None,
        'scanresults_error': None
    }
    
    # Check findings file
    if findings_file.exists():
        findings_count = count_records_in_file(str(findings_file))
        result['findings_count'] = findings_count
        if findings_count < 0:
            result['findings_error'] = "Error reading file"
    else:
        result['findings_error'] = "File not found"
    
    # Check scan results file
    if scanresults_file.exists():
        scanresults_count = count_records_in_file(str(scanresults_file))
        result['scanresults_count'] = scanresults_count
        if scanresults_count < 0:
            result['scanresults_error'] = "Error reading file"
    else:
        result['scanresults_error'] = "File not found"
    
    # Get manifest counts
    manifest_file = exports_dir / "export_manifest.csv"
    if manifest_file.exists():
        import csv
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('project_uuid') == project_uuid:
                        result['manifest_findings'] = int(row.get('findings_count', 0) or 0)
                        result['manifest_scanresults'] = int(row.get('scanresults_count', 0) or 0)
                        
                        # Compare
                        if result['findings_count'] >= 0:
                            result['findings_match'] = result['findings_count'] == result['manifest_findings']
                        if result['scanresults_count'] >= 0:
                            result['scanresults_match'] = result['scanresults_count'] == result['manifest_scanresults']
                        break
        except Exception as e:
            result['findings_error'] = f"Manifest error: {e}"
            result['scanresults_error'] = f"Manifest error: {e}"
    
    return result


def verify_project_files(namespace: str, project_uuid: str = None):
    """
    Verify exported files for a project or all projects in manifest.
    
    Args:
        namespace: Namespace name
        project_uuid: Optional project UUID (if None, verifies all projects)
    """
    exports_dir = Path("exports") / namespace
    
    if not exports_dir.exists():
        print(f"Error: Exports directory not found: {exports_dir}")
        sys.exit(1)
    
    manifest_file = exports_dir / "export_manifest.csv"
    if not manifest_file.exists():
        print(f"Error: Manifest file not found: {manifest_file}")
        sys.exit(1)
    
    # Read all projects from manifest
    import csv
    projects = []
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                projects.append({
                    'uuid': row.get('project_uuid', '').strip(),
                    'name': row.get('project_name', '').strip(),
                    'manifest_findings': int(row.get('findings_count', 0) or 0),
                    'manifest_scanresults': int(row.get('scanresults_count', 0) or 0)
                })
    except Exception as e:
        print(f"Error reading manifest: {e}")
        sys.exit(1)
    
    if not projects:
        print(f"Error: No projects found in manifest")
        sys.exit(1)
    
    # Filter to single project if specified
    if project_uuid:
        projects = [p for p in projects if p['uuid'] == project_uuid]
        if not projects:
            print(f"Error: Project {project_uuid} not found in manifest")
            sys.exit(1)
        verbose = True
    else:
        verbose = False
    
    print(f"Verifying files for namespace: {namespace}")
    if project_uuid:
        print(f"Project: {project_uuid}")
    else:
        print(f"Projects: {len(projects)}")
    print("=" * 60)
    
    results = []
    
    for project in tqdm(projects, desc="Verifying projects", unit=" project", disable=verbose):
        result = verify_single_project(namespace, project['uuid'], project['name'])
        results.append(result)
        
        if verbose:
            # Detailed output for single project
            print(f"\nFindings file: exports/{namespace}/findings_{result['project_uuid']}.json")
            if result['findings_file_exists']:
                if result['findings_count'] >= 0:
                    print(f"  ✓ File exists")
                    print(f"  Count: {result['findings_count']:,} finding(s)")
                    file_size = os.path.getsize(exports_dir / f"findings_{result['project_uuid']}.json")
                    print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
                else:
                    print(f"  ✗ {result['findings_error']}")
            else:
                print(f"  ✗ {result['findings_error']}")
            
            print(f"\nScan Results file: exports/{namespace}/scanresults_{result['project_uuid']}.json")
            if result['scanresults_file_exists']:
                if result['scanresults_count'] >= 0:
                    print(f"  ✓ File exists")
                    print(f"  Count: {result['scanresults_count']:,} scan result(s)")
                    file_size = os.path.getsize(exports_dir / f"scanresults_{result['project_uuid']}.json")
                    print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
                else:
                    print(f"  ✗ {result['scanresults_error']}")
            else:
                print(f"  ✗ {result['scanresults_error']}")
            
            if result['manifest_findings'] >= 0:
                print(f"\nManifest:")
                print(f"  Findings: {result['manifest_findings']:,}")
                print(f"  ScanResults: {result['manifest_scanresults']:,}")
                
                print(f"\nComparison:")
                if result['findings_count'] >= 0:
                    diff = result['findings_count'] - result['manifest_findings']
                    status = "✓ Match" if result['findings_match'] else f"✗ Mismatch (diff: {diff:+,})"
                    print(f"  Findings: File={result['findings_count']:,}, Manifest={result['manifest_findings']:,} - {status}")
                else:
                    print(f"  Findings: Cannot compare (file error)")
                
                if result['scanresults_count'] >= 0:
                    diff = result['scanresults_count'] - result['manifest_scanresults']
                    status = "✓ Match" if result['scanresults_match'] else f"✗ Mismatch (diff: {diff:+,})"
                    print(f"  ScanResults: File={result['scanresults_count']:,}, Manifest={result['manifest_scanresults']:,} - {status}")
                else:
                    print(f"  ScanResults: Cannot compare (file error)")
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    total_projects = len(results)
    findings_matches = sum(1 for r in results if r['findings_match'])
    scanresults_matches = sum(1 for r in results if r['scanresults_match'])
    both_match = sum(1 for r in results if r['findings_match'] and r['scanresults_match'])
    
    findings_missing = sum(1 for r in results if not r['findings_file_exists'])
    scanresults_missing = sum(1 for r in results if not r['scanresults_file_exists'])
    both_missing = sum(1 for r in results if not r['findings_file_exists'] and not r['scanresults_file_exists'])
    
    findings_mismatches = sum(1 for r in results if r['findings_file_exists'] and r['findings_count'] >= 0 and not r['findings_match'])
    scanresults_mismatches = sum(1 for r in results if r['scanresults_file_exists'] and r['scanresults_count'] >= 0 and not r['scanresults_match'])
    
    print(f"\nTotal Projects: {total_projects}")
    print(f"\nFindings:")
    print(f"  ✓ Matches: {findings_matches}/{total_projects}")
    print(f"  ✗ Mismatches: {findings_mismatches}")
    print(f"  ✗ Missing files: {findings_missing}")
    
    print(f"\nScanResults:")
    print(f"  ✓ Matches: {scanresults_matches}/{total_projects}")
    print(f"  ✗ Mismatches: {scanresults_mismatches}")
    print(f"  ✗ Missing files: {scanresults_missing}")
    
    print(f"\nOverall:")
    print(f"  ✓ Both match: {both_match}/{total_projects}")
    print(f"  ✗ Both missing: {both_missing}")
    
    # Show mismatches if any
    if findings_mismatches > 0 or scanresults_mismatches > 0:
        print(f"\nProjects with mismatches:")
        for r in results:
            if (r['findings_file_exists'] and r['findings_count'] >= 0 and not r['findings_match']) or \
               (r['scanresults_file_exists'] and r['scanresults_count'] >= 0 and not r['scanresults_match']):
                findings_info = ""
                if r['findings_file_exists'] and r['findings_count'] >= 0:
                    diff = r['findings_count'] - r['manifest_findings']
                    findings_info = f"Findings: {r['findings_count']:,} vs {r['manifest_findings']:,} (diff: {diff:+,})"
                
                scanresults_info = ""
                if r['scanresults_file_exists'] and r['scanresults_count'] >= 0:
                    diff = r['scanresults_count'] - r['manifest_scanresults']
                    scanresults_info = f"ScanResults: {r['scanresults_count']:,} vs {r['manifest_scanresults']:,} (diff: {diff:+,})"
                
                print(f"  {r['project_name']} ({r['project_uuid'][:8]}...): {findings_info} {scanresults_info}")
    
    # Show missing files if any
    if findings_missing > 0 or scanresults_missing > 0:
        print(f"\nProjects with missing files:")
        for r in results:
            if not r['findings_file_exists'] or not r['scanresults_file_exists']:
                missing = []
                if not r['findings_file_exists']:
                    missing.append("findings")
                if not r['scanresults_file_exists']:
                    missing.append("scanresults")
                print(f"  {r['project_name']} ({r['project_uuid'][:8]}...): Missing {', '.join(missing)}")
    
    # Exit code
    if both_match == total_projects:
        print(f"\n✓ All projects verified successfully!")
        sys.exit(0)
    else:
        print(f"\n✗ Some projects have mismatches or missing files")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify exported files for a specific project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify a specific project
  python verify_project_files.py --namespace principal-prod --project-uuid 6643aa5c1fb5ef3c39fd15ec
  
  # Verify all projects in manifest (provides summary)
  python verify_project_files.py --namespace principal-prod
        """
    )
    parser.add_argument(
        '--namespace',
        required=True,
        help='Namespace name'
    )
    parser.add_argument(
        '--project-uuid',
        help='Project UUID (optional - if not provided, verifies all projects in manifest)'
    )
    args = parser.parse_args()
    
    verify_project_files(args.namespace, args.project_uuid)


if __name__ == "__main__":
    main()

