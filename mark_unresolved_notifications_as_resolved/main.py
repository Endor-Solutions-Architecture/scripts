import requests
import json
from dotenv import load_dotenv
import os

# Load the environment variables from the .env file
load_dotenv()

# Get the API key and secret from environment variables
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")
API_URL = 'https://api.endorlabs.com/v1'

def get_token():
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    url = f"{API_URL}/auth/api-key"
    payload = {
        "key": api_key,
        "secret": api_secret
    }
    headers = {
        "Content-Type": "application/json",
        "Request-Timeout": "60"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    
    if response.status_code == 200:
        token = response.json().get('token')
        return token
    else:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

API_TOKEN = get_token()
HEADERS = {
    "User-Agent": "curl/7.68.0",
    "Accept": "*/*",
    "Authorization": f"Bearer {API_TOKEN}",
    "Request-Timeout": "600"  # Set the request timeout to 60 seconds
}

def update_notifications_to_resolved(notifications_to_update):
    print("Updating notifications to resolved state one at a time...")
    for uuid in notifications_to_update:
        url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/notifications"
        data = {
            'request': {
                'update_mask': 'spec.state'
            },
            'object': {
                'uuid': uuid,
                'spec': {
                    'state': 'NOTIFICATION_STATE_RESOLVED'
                }
            }
        }
        response = requests.patch(url, headers=HEADERS, json=data, timeout=60)

        if response.status_code != 200:
            print(f"Failed to update notification {uuid}, Status Code: {response.status_code}, Response: {response.text}")
        else:
            print(f"Notification {uuid} updated to resolved.")

    print("All notifications processed.")

def get_notifications():
    print("Fetching notifications...")
    url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/notifications"
    print(f"URL: {url}")
    
    params = {
        'list_parameters.filter': 'spec.state!="NOTIFICATION_STATE_RESOLVED"',
        'list_parameters.mask': 'uuid,spec.state'
    }
    
    notifications_list = []
    next_page_id = None

    while True:
        if next_page_id:
            params['list_parameters.page_id'] = next_page_id

        response = requests.get(url, headers=HEADERS, params=params, timeout=60)

        if response.status_code != 200:
            print(f"Failed to get notifications, Status Code: {response.status_code}, Response: {response.text}")
            exit()

        response_data = response.json()
        notifications = response_data.get('list', {}).get('objects', [])
        for notification in notifications:
            notifications_list.append(notification['uuid'])

        next_page_id = response_data.get('list', {}).get('response', {}).get('next_page_id')
        if not next_page_id:
            break

    print(f"Total notifications fetched: {len(notifications_list)}")
    return notifications_list

def main():    
    notifications = get_notifications()
    update_notifications_to_resolved(notifications)
    

if __name__ == '__main__':
    main()