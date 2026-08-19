import json
import pandas as pd

def read_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def json_to_dataframe(json_data):
    components = json_data.get('components', [])
    
    data = []
    for component in components:
        # Handle the licenses field
        licenses = component.get('licenses', [])
        license_names = [license.get('license', {}).get('name', '') for license in licenses]
        license_names_str = ", ".join(license_names)
        
        # Append the extracted data
        data.append({
            "Name": component.get("name", ""),
            "Version": component.get("version", ""),
            "Type": component.get("type", ""),
            "License": license_names_str
        })
        
    df = pd.DataFrame(data, columns=["Name", "Version", "Type", "License"])
    return df