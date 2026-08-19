Step 1: create .env file  

API_KEY=<your_api_key_here>  
API_SECRET=<your_api_secret_here>  
ENDOR_NAMESPACE=<your_namespace>  

Step 2: run

```
python3 -m venv .venv  
source .venv/bin/activate  
pip install -r requirements.txt  
```

Step 3:
If you want to add tags to single project execute and it will prompt you for a project_uuid:
```
python3 project_tags.py

If you want to add tag to single package-version execute and it will prompt you for a package_uuid:

python3 package_tags.py
```



