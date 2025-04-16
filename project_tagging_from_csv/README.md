Step 1: create .env file  

API_KEY=<your_api_key_here>  
API_SECRET=<your_api_secret_here>  
ENDOR_NAMESPACE=<your_namespace>  
GITORG=<your_git_org>

Step 2: run

```
python3 -m venv .venv  
source .venv/bin/activate  
pip install -r requirements.txt  
```

Step 3:
Make sure to have a CSV with no header row and format should be: column1 = git project name without the org, column2=tag(s) separated by commas:

Example csv format:

project1, tagABC  \n
project2, \n
project3,"PRO, DataTeam" \n


Make sure the project name does not include the git org name as this is declared on the .env file and later appended on the code to each project name per row. 

run:
```
python3 project_tags.py cvs_file.csv

```
