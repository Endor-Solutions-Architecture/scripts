## Delete all orphaned package versions
This script will delete all package versions that belong to a non existing project in the namespace provided and including child namespaces in the .env file.

## SETUP

Step 1: create .env file and add these values (make sure your key has rights to delete package versions)

API_KEY=<your_api_key_here>  
API_SECRET=<your_api_secret_here>  
ENDOR_NAMESPACE=<your_namespace>  

Step 2: execute these commands

```
python3 -m venv venv
source venv/bin/activate  
pip install -r requirements.txt  
```

Step 3: run the script
```
python3 main.py 

No packages will be deleted. To delete orphaned packages, run the script with the --no-dry-run flag

python3 main.py --no-dry-run
```

## No Warranty

Please be advised that this software is provided on an "as is" basis, without warranty of any kind, express or implied. The authors and contributors make no representations or warranties of any kind concerning the safety, suitability, lack of viruses, inaccuracies, typographical errors, or other harmful components of this software. There are inherent dangers in the use of any software, and you are solely responsible for determining whether this software is compatible with your equipment and other software installed on your equipment.

By using this software, you acknowledge that you have read this disclaimer, understand it, and agree to be bound by its terms and conditions. You also agree that the authors and contributors of this software are not liable for any damages you may suffer as a result of using, modifying, or distributing this software.
