import subprocess

# List of project UUIDs to update
project_uuids = [
    "project_uuid1",
    "project_uuid2"
]

# Scan profile UUID to be used in the update command
scan_profile_uuid = "673cf04cc249a2703d5d8d4b"

def update_project(uuid, scan_uuid):
    """Executes the endorctl command for a given project UUID and scan profile UUID."""
    command = (
        f"endorctl api update -r Project --uuid={uuid} -d '{{\"spec\":{{\"scan_profile_uuid\": \"{scan_uuid}\"}}}}' "
        "--field-mask 'spec.scan_profile_uuid'"
    )
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Successfully updated project {uuid}:")
        print(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        print(f"Error updating project {uuid}: {e.stderr.decode()}")

def main():
    """Main function to update all project UUIDs."""
    for uuid in project_uuids:
        print(f"Updating project {uuid} with scan profile {scan_profile_uuid}...")
        update_project(uuid, scan_profile_uuid)

if __name__ == "__main__":
    main()
