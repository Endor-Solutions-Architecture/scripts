## Get dependency paths for a finding
This script provides the list of dependency paths given a finding UUID.
It expects two arguments:
- namespace
- finding_uuid

and expects the following environment variables to be set:
- ENDOR_API_CREDENTIALS_KEY="<key_value>"
- ENDOR_API_CREDENTIALS_SECRET="<secret_value>"
 
and can be ran like this for example:

```
$ python dep_paths_for_finding.py <namespace> <finding_uuid>
```

Output is JSON, which contains the list of paths, with each node in the path, with the `dependency_name`, and `public` value.  public will either be `true` or `false`, false means it's a private dependency not a public one.

Each path is an ordered list starting with the dependency of the finding itself and traversing "up" to the package root.
```
{
    "6682b1cf7ed4297ef84cbba9": [
        [
            {
                "dependency_name": "npm://next@12.3.4",
                "public": true
            },
            {
                "dependency_name": "npm://next-i18next@12.1.0",
                "public": true
            },
            {
                "dependency_name": "npm://startpage@0.1.0",
                "public": false
            }
        ],
        [
            {
                "dependency_name": "npm://next@12.3.4",
                "public": true
            },
            {
                "dependency_name": "npm://startpage@0.1.0",
                "public": false
            }
        ]
    ]
}
 ```

 
