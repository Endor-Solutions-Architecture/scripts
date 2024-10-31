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

It returns data in the form of a set of tuples, each being a distinct path "up" the tree from the finding, e.g.
```
{
    ('npm://next@12.3.4', 'npm://next-i18next@12.1.0', 'npm://startpage@0.1.0'),
    ('npm://next@12.3.4', 'npm://startpage@0.1.0')
}
 ```

 