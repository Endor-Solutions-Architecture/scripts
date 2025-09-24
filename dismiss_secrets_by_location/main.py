#!/usr/bin/env python3

import os
import sys
import re
import requests
import argparse
import subprocess
import time
import json
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

def get_endor_token() -> str:
    """Get Endor token either directly or by authenticating with API credentials."""
    # Try to get token directly first
    token = os.getenv('ENDOR_TOKEN')
    if token:
        return token

    # If no token, try to get API credentials
    key = os.getenv('ENDOR_API_CREDENTIALS_KEY')
    secret = os.getenv('ENDOR_API_CREDENTIALS_SECRET')
    
    if not key or not secret:
        print("Error: Either ENDOR_TOKEN or both ENDOR_API_CREDENTIALS_KEY and ENDOR_API_CREDENTIALS_SECRET must be set")
        sys.exit(1)

    # Get token using API credentials
    try:
        response = requests.post(
            "https://api.endorlabs.com/v1/auth/api-key",
            json={"key": key, "secret": secret}
        )
        if response.status_code != 200:
            print(f"Error: Failed to get token from API. Status code: {response.status_code}")
            sys.exit(1)
        
        token = response.json().get('token')
        if not token:
            print("Error: No token in API response")
            sys.exit(1)
            
        return token
    except Exception as e:
        print(f"Error getting token from API: {e}")
        sys.exit(1)

class SecretExcepter:
    """Handles Excepting secrets in Endor Labs given a set of locations."""
    
    def __init__(self, namespace: str, debug: bool = False, dry_run: bool = True, project_uuid: str = None, locations_file: str = None, timeout_seconds: int = 60):
        self.namespace = namespace
        self.debug = debug
        self.dry_run = dry_run
        self.project_uuid = project_uuid
        self.locations_file = locations_file
        self.locations = []
        self.base_url = "https://api.endorlabs.com"
        self.policy_name_base = "Scripted Secret Exceptions - Do Not Modify"
        self.max_locations_per_policy = 150
        self.timeout_seconds = timeout_seconds
        
        # Get authentication token
        self.token = get_endor_token()
        
        # Load locations from file if provided
        self.locations = self._load_locations_from_file() if locations_file else []
        
        # Create log file for Excepted secrets
        epoch_time = str(int(time.time()))
        self.log_file = f"Except_secrets_by_location.excepted.{epoch_time}.log"
        
        # Write CSV header to log file
        try:
            with open(self.log_file, 'w') as f:
                f.write('"Namespace","Secret UUID","Description","Matched Location"\n')
        except Exception as e:
            if self.debug:
                print(f"Error creating log file header: {e}")

    def get_secrets(self) -> List[Dict[str, Any]]:
        """Get all secrets in the namespace or a specific project if UUID is provided."""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Request-Timeout": str(self.timeout_seconds)
            }

            url = f"{self.base_url}/v1/namespaces/{self.namespace}/findings"

            filter = "context.type==CONTEXT_TYPE_MAIN and spec.finding_categories contains ['FINDING_CATEGORY_SECRETS']"
            
            if self.project_uuid:
                # Get specific project
                filter += f" and spec.project_uuid=={self.project_uuid}"
                if self.debug:
                    print(f"Fetching specific project from: {url}")
                    
            all_secrets = []
            next_page_token = None
            page_count = 0
            
            while True:
                page_count += 1
                params = {
                    "list_parameters.filter": filter,
                    "list_parameters.page_size": 500,
                    "list_parameters.traverse": "true"
                }
                
                if next_page_token:
                    params["list_parameters.page_token"] = next_page_token
                
                if self.debug:
                    print(f"Fetching page {page_count}...")

                response = requests.get(url, headers=headers, params=params)
                
                if self.debug:
                    print(f"Response: {response.status_code}")
                    if response.status_code != 200:
                        print(f"Response: {response.json()}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    secrets_findings = response_data['list']['objects']
                    all_secrets.extend(secrets_findings)
                    
                    if self.debug:
                        print(f"Found {len(secrets_findings)} secrets findings on page {page_count}")
                    
                    # Check for next page token
                    next_page_token = response_data['list']['response'].get('next_page_token')
                    if not next_page_token:
                        break
                else:
                    print(f"Error fetching secrets: {response.status_code} - {response.text}")
                    return []
            
            if self.debug:
                print(f"Total found {len(all_secrets)} secrets findings across {page_count} pages")
            return all_secrets
                
        except Exception as e:
            print(f"Error fetching secrets: {e}")
            return []
    
    def _load_locations_from_file(self) -> List[str]:
        """Load locations from the specified file."""
        if not self.locations_file:
            return []
        
        try:
            with open(self.locations_file, 'r') as f:
                locations = [line.strip() for line in f if line.strip()]
            if self.debug:
                print(f"Loaded {len(locations)} locations from {self.locations_file}")
            return locations
        except Exception as e:
            print(f"Error loading locations from {self.locations_file}: {e}")
            return []
    
    def _should_except_secret(self, secret: Dict[str, Any]) -> bool:
        """Check if a secret should be Excepted based on its locations."""
        if not self.locations:
            # If no locations file provided, Except all secrets
            return True
        
        try:
            results = secret['spec']['finding_metadata']['source_policy_info']['results']
            for result in results:
                secret_location = result['fields']['Secret Location']
                if any(location in secret_location for location in self.locations):
                    if self.debug:
                        print(f"Secret location '{secret_location}' matches locations file")
                    return True
            return False
        except (KeyError, TypeError) as e:
            if self.debug:
                print(f"Error checking secret locations: {e}")
            return False
    
    def _get_matched_location(self, secret: Dict[str, Any]) -> str:
        """Get the location from the locations file that matches this secret."""
        if not self.locations:
            return "N/A"
        
        try:
            results = secret['spec']['finding_metadata']['source_policy_info']['results']
            for result in results:
                secret_location = result['fields']['Secret Location']
                for location in self.locations:
                    if location in secret_location:
                        return location
            return "Unknown"
        except (KeyError, TypeError):
            return "Error"

    def _log_Excepted_secret(self, secret: Dict[str, Any]) -> None:
        """Log a Excepted secret to the log file in CSV format."""
        try:
            matched_location = self._get_matched_location(secret)
            # Extract namespace from tenant_meta
            namespace = secret.get('tenant_meta', {}).get('namespace', 'Unknown')
            
            # Escape commas and quotes in the fields
            secret_uuid = secret['uuid'].replace(',', ';').replace('"', '""')
            description = secret['meta']['description'].replace(',', ';').replace('"', '""')
            namespace = namespace.replace(',', ';').replace('"', '""')
            matched_location = matched_location.replace(',', ';').replace('"', '""')
            
            with open(self.log_file, 'a') as f:
                f.write(f'"{namespace}","{secret_uuid}","{description}","{matched_location}"\n')
        except Exception as e:
            if self.debug:
                print(f"Error logging Excepted secret: {e}")

    def _collect_exception_locations(self, secrets: List[Dict[str, Any]]) -> List[str]:
        """Collect unique 'Secret Location' values from secrets that should be excepted."""
        unique_locations: List[str] = []
        seen = set()
        for secret in secrets:
            if not self._should_except_secret(secret):
                continue
            try:
                results = secret['spec']['finding_metadata']['source_policy_info']['results']
                for result in results:
                    secret_location = result['fields']['Secret Location']
                    if (not self.locations) or any(loc in secret_location for loc in self.locations):
                        if secret_location not in seen:
                            seen.add(secret_location)
                            unique_locations.append(secret_location)
            except (KeyError, TypeError):
                continue
        return unique_locations

    def _build_rule(self, locations: List[str]) -> str:
        """Build the Rego rule string containing provided locations array."""
        if not locations:
            locations_block = "locations := []"
        else:
            # Escape quotes inside each location string for Rego
            escaped = [loc.replace('"', '\\"') for loc in locations]
            # Join with proper formatting
            lines = []
            for idx, loc in enumerate(escaped):
                comma = "," if idx < len(escaped) - 1 else ""
                lines.append(f'    "{loc}"{comma}')
            locations_block = "locations := [\n" + "\n".join(lines) + " ]"
        rule = (
            "package main\n\n"
            "exclude_by_location[result] {\n"
            "  some i\n"
            "  data.resources.Finding[i].spec.finding_categories[_] == \"FINDING_CATEGORY_SECRETS\"\n"
            f"  {locations_block}\n"
            "  locations[_] == data.resources.Finding[i].spec.finding_metadata.source_policy_info.results[_].fields[\"Secret Location\"] \n\n"
            "  result = {\n"
            "    \"Endor\" : {\n"
            "      \"Finding\" : data.resources.Finding[i].uuid\n"
            "    }\n"
            "  }\n"
            "}"
        )
        return rule

    def _get_policy_by_exact_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Return existing policy dict by exact name if found, else None."""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            url = f"{self.base_url}/v1/namespaces/{self.namespace}/policies"
            params = {
                "list_parameters.filter": f"meta.name==\"{name}\"",
                "list_parameters.page_size": 1
            }
            response = requests.get(url, headers=headers, params=params)
            if self.debug:
                print(f"Lookup policy response: {response.status_code}")
            if response.status_code != 200:
                if self.debug:
                    print(f"Policy lookup error: {response.text}")
                return None
            data = response.json()
            objs = data.get('list', {}).get('objects', [])
            return objs[0] if objs else None
        except Exception as e:
            if self.debug:
                print(f"Error looking up policy: {e}")
            return None

    def _create_policy(self, name: str, rule: str) -> bool:
        """Create a new exception policy with the provided rule and name."""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            url = f"{self.base_url}/v1/namespaces/{self.namespace}/policies"
            payload = {
                    "meta": {
                        "description": "Exception Policy created by script",
                        "name": name,
                        "tags": []
                    },
                    "propagate": True,
                    "spec": {
                        "exception": {"reason": "EXCEPTION_REASON_OTHER"},
                        "disable": False,
                        "policy_type": "POLICY_TYPE_EXCEPTION",
                        "project_exceptions": [],
                        "project_selector": [],
                        "query_statements": ["data.main.exclude_by_location"],
                        "resource_kinds": ["Finding"],
                        "rule": rule,
                        "template_values": {}
                    }
                }
            
            if self.debug:
                print("Creating exception policy with payload:")
                print(json.dumps(payload, indent=2))
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code in (200, 201):
                if self.debug:
                    print("Policy created successfully")
                return True
            print(f"Error creating policy: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            print(f"Error creating policy: {e}")
            return False

    def _update_policy_rule(self, policy_uuid: str, name: str, rule: str) -> bool:
        """Update an existing policy's name and spec.rule using update_mask."""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            url = f"{self.base_url}/v1/namespaces/{self.namespace}/policies"
            payload = {
                "request": {
                    "update_mask": "meta.name,spec.rule,spec.policy_type"
                },
                "object": {
                    "uuid": policy_uuid,
                    "meta": {
                        "name": name,
                    },
                    "spec": {
                        "rule": rule,
                        "policy_type": "POLICY_TYPE_EXCEPTION",

                    }
                }
            }
            if self.debug:
                print("Updating exception policy with payload:")
                print(json.dumps(payload, indent=2))
            response = requests.patch(url, headers=headers, json=payload)
            if response.status_code == 200:
                if self.debug:
                    print("Policy updated successfully")
                return True
            print(f"Error updating policy: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            print(f"Error updating policy: {e}")
            return False

    @staticmethod
    def _chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    def _delete_policy(self, policy_uuid: str) -> bool:
        """Delete a policy by UUID."""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            url = f"{self.base_url}/v1/namespaces/{self.namespace}/policies"
            payload = {"object": {"uuid": policy_uuid}}
            response = requests.delete(url, headers=headers, json=payload)
            if response.status_code in (200, 204):
                if self.debug:
                    print(f"Policy deleted successfully: uuid={policy_uuid}")
                return True
            print(f"Error deleting policy: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            print(f"Error deleting policy: {e}")
            return False

    def except_secret(self, secret_finding: Dict[str, Any]) -> bool:
        """Except a secret finding."""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/v1/namespaces/{self.namespace}/findings"
            
            payload = {
                "request": {
                    "update_mask": "spec.Except,spec.finding_tags"
                },
                "object": {
                    "uuid": secret_finding['uuid'],
                    "spec": {
                        "dismiss": True,
                        "finding_tags":  secret_finding["spec"]["finding_tags"] + ["FINDING_TAGS_EXCEPTION"]
                    },
                    "tenant_meta": {
                        "namespace": self.namespace
                    }
                }
            }
            
            if self.debug:
                print(f"Excepting secret {secret_finding['uuid']}")
                print(f"URL: {url}")
                print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.patch(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                if self.debug:
                    print(f"Successfully Excepted secret {secret_finding['uuid']}")
                return True
            else:
                print(f"Error Excepting secret {secret_finding['uuid']}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error Excepting secret {secret_finding['uuid']}: {e}")
            return False

    def run(self) -> int:
        """Main execution method."""
        print(f"Starting secrets Exception script for namespace: {self.namespace}")
        print(f"Excepted secrets will be logged to: {self.log_file}")
        
        if self.dry_run:
            print("\n**** DRY RUN MODE  (use --no-dry-run to apply Exception Policy in Endor Labs) ****\n")
        
        # Get all projects
        secrets = self.get_secrets()
        if not secrets:
            print("No secrets found or error occurred")
            return 1
        
        print(f"Found {len(secrets)} secrets findings to process")
        
        # Decide which secrets to include and collect locations
        exception_locations = self._collect_exception_locations(secrets)
        print(f"Collected {len(exception_locations)} unique 'Secret Location' values for exception policy")

        # Chunk locations across multiple policies if needed
        location_chunks = self._chunk_list(exception_locations, self.max_locations_per_policy) or [[]]
        if self.debug:
            print(f"Locations will be split across {len(location_chunks)} policy(ies) with up to {self.max_locations_per_policy} per policy")

        if self.dry_run:
            for idx, locs in enumerate(location_chunks, start=1):
                policy_name = f"{self.policy_name_base} {idx}"
                rule = self._build_rule(locs)
                if self.debug:
                    print(f"Generated Rego rule for policy '{policy_name}':")
                    print(rule)
                existing_policy = self._get_policy_by_exact_name(policy_name)
                if existing_policy and existing_policy.get('uuid'):
                    print(f"Dry run - would update exception policy '{policy_name}' (uuid: {existing_policy.get('uuid')}) with update_mask spec.rule")
                else:
                    print(f"Dry run - would create exception policy '{policy_name}' (uuid: will be assigned) with update_mask spec.rule")
            # Cleanup extra policies beyond needed chunks
            cleanup_start = len(location_chunks) + 1
            while True:
                policy_name = f"{self.policy_name_base} {cleanup_start}"
                existing_policy = self._get_policy_by_exact_name(policy_name)
                if not existing_policy:
                    break
                print(f"Dry run - would delete extra exception policy '{policy_name}' (uuid: {existing_policy.get('uuid')})")
                cleanup_start += 1
            # Log all matched secrets even in dry-run for traceability
            success_count = 0
            skipped_count = 0
            for secret in secrets:
                if self._should_except_secret(secret):
                    self._log_Excepted_secret(secret)
                    success_count += 1
                else:
                    skipped_count += 1
            print(f"\nDry run completed: would have Excepted {success_count} secrets, skipped {skipped_count} secrets")
            return 0

        # Not dry run: create/update each policy chunk
        for idx, locs in enumerate(location_chunks, start=1):
            policy_name = f"{self.policy_name_base} {idx}"
            rule = self._build_rule(locs)
            existing_policy = self._get_policy_by_exact_name(policy_name)
            if existing_policy:
                policy_uuid = existing_policy.get('uuid')
                if not policy_uuid:
                    print(f"Error: Existing policy '{policy_name}' found but missing UUID")
                    return 1
                ok = self._update_policy_rule(policy_uuid, policy_name, rule)
                if not ok:
                    return 1
            else:
                ok = self._create_policy(policy_name, rule)
                if not ok:
                    return 1

        # Delete any extra policies beyond what is needed
        cleanup_start = len(location_chunks) + 1
        while True:
            policy_name = f"{self.policy_name_base} {cleanup_start}"
            existing_policy = self._get_policy_by_exact_name(policy_name)
            if not existing_policy:
                break
            policy_uuid = existing_policy.get('uuid')
            if not policy_uuid:
                if self.debug:
                    print(f"Skipping delete of '{policy_name}' because UUID is missing")
                cleanup_start += 1
                continue
            ok = self._delete_policy(policy_uuid)
            if not ok:
                return 1
            cleanup_start += 1

        # Log all matched secrets
        success_count = 0
        skipped_count = 0
        for secret in secrets:
            if self._should_except_secret(secret):
                self._log_Excepted_secret(secret)
                success_count += 1
            else:
                skipped_count += 1

        print(f"Successfully applied exception policy. Excepted {success_count} secrets, skipped {skipped_count} secrets")
        return 0

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Except secrets in Endor Labs given a set of locations')
    parser.add_argument('--namespace', required=True, help='Endor namespace')
    parser.add_argument('--project-uuid', help='Optional project UUID to filter secrets to a specific project')
    parser.add_argument('--locations-file', required=True, help='Path to file containing locations to Except')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--timeout', type=int, default=60, help='Timeout in seconds for listing secrets only (default: 60)')
    parser.add_argument('--no-dry-run', action='store_true', help='Proceed with dimiss actions (default is dry run)')
    args = parser.parse_args()

    # Load environment variables from .env file if it exists
    load_dotenv()

     # Create and run the secret Excepter
    secret_Excepter = SecretExcepter(
        namespace=args.namespace,
        debug=args.debug,
        dry_run=not args.no_dry_run,
        project_uuid=args.project_uuid,
        locations_file=args.locations_file,
        timeout_seconds=args.timeout
    )

    exit_code = secret_Excepter.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
