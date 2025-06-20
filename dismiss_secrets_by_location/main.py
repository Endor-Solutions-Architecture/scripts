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

class SecretDismisser:
    """Handles dismissing secrets in Endor Labs given a set of locations."""
    
    def __init__(self, namespace: str, debug: bool = False, dry_run: bool = True, project_uuid: str = None, locations_file: str = None):
        self.namespace = namespace
        self.debug = debug
        self.dry_run = dry_run
        self.project_uuid = project_uuid
        self.locations_file = locations_file
        self.locations = []
        self.base_url = "https://api.endorlabs.com"
        
        # Get authentication token
        self.token = get_endor_token()
        
        # Load locations from file if provided
        self.locations = self._load_locations_from_file() if locations_file else []
        
        # Create log file for dismissed secrets
        epoch_time = str(int(time.time()))
        self.log_file = f"dismiss_secrets_by_location.dismissed.{epoch_time}.log"
        
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
                "Content-Type": "application/json"
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
    
    def _should_dismiss_secret(self, secret: Dict[str, Any]) -> bool:
        """Check if a secret should be dismissed based on its locations."""
        if not self.locations:
            # If no locations file provided, dismiss all secrets
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

    def _log_dismissed_secret(self, secret: Dict[str, Any]) -> None:
        """Log a dismissed secret to the log file in CSV format."""
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
                print(f"Error logging dismissed secret: {e}")

    def dismiss_secret(self, secret_finding: Dict[str, Any]) -> bool:
        """Dismiss a secret finding."""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/v1/namespaces/{self.namespace}/findings"
            
            payload = {
                "request": {
                    "update_mask": "spec.dismiss,spec.finding_tags"
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
                print(f"Dismissing secret {secret_finding['uuid']}")
                print(f"URL: {url}")
                print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.patch(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                if self.debug:
                    print(f"Successfully dismissed secret {secret_finding['uuid']}")
                return True
            else:
                print(f"Error dismissing secret {secret_finding['uuid']}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error dismissing secret {secret_finding['uuid']}: {e}")
            return False

    def run(self) -> int:
        """Main execution method."""
        print(f"Starting secrets dismissal for namespace: {self.namespace}")
        print(f"Dismissed secrets will be logged to: {self.log_file}")
        
        if self.dry_run:
            print("\n**** DRY RUN MODE  (use --no-dry-run to apply dismissal in Endor Labs) ****\n")
        
        # Get all projects
        secrets = self.get_secrets()
        if not secrets:
            print("No secrets found or error occurred")
            return 1
        
        print(f"Found {len(secrets)} secrets findings to process")
        
        # Update each project
        success_count = 0
        skipped_count = 0
        for secret in secrets:
            if self._should_dismiss_secret(secret):
                if self.dry_run:
                    print(f"Dry run - would have dismissed secret: {secret['uuid']} ({secret['meta']['description']})")
                else:
                    print(f"Dismissing secret: {secret['uuid']} ({secret['meta']['description']})")
                    if not self.dismiss_secret(secret):
                        print(f"\nERROR: Failed to dismiss secret {secret['uuid']}\n")
                        continue
                self._log_dismissed_secret(secret)
                success_count += 1
            else:
                if self.debug:
                    print(f"Skipping secret: {secret['uuid']} (no matching locations)")
                skipped_count += 1

        if not self.dry_run:
            print(f"Successfully dismissed {success_count} secrets, skipped {skipped_count} secrets")
        else:
            print(f"\nDry run completed: would have dismissed {success_count} secrets, skipped {skipped_count} secrets")
        return 0

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Dismiss secrets in Endor Labs given a set of locations')
    parser.add_argument('--namespace', required=True, help='Endor namespace')
    parser.add_argument('--project-uuid', help='Optional project UUID to filter secrets to a specific project')
    parser.add_argument('--locations-file', required=True, help='Path to file containing locations to dismiss')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--no-dry-run', action='store_true', help='Proceed with dimiss actions (default is dry run)')
    args = parser.parse_args()

    # Load environment variables from .env file if it exists
    load_dotenv()

     # Create and run the secret dismisser
    secret_dismisser = SecretDismisser(
        namespace=args.namespace,
        debug=args.debug,
        dry_run=not args.no_dry_run,
        project_uuid=args.project_uuid,
        locations_file=args.locations_file
    )

    exit_code = secret_dismisser.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
